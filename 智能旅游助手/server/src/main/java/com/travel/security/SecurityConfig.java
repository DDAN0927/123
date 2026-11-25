package com.travel.security;

import jakarta.servlet.http.HttpServletResponse;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

/**
 * 无状态鉴权配置。
 *
 * <p>规则顺序有讲究（先匹配先生效）：公开页 → 公开接口 → 其余 {@code /api/**} 需登录。
 * 静态资源必须显式放行，否则官网首屏会 401。
 */
@Configuration
public class SecurityConfig {

    private final JwtAuthFilter jwtAuthFilter;
    private final AuthRateLimitFilter authRateLimitFilter;

    /**
     * 允许跨源访问的白名单；空表示**完全不注册 CORS**（默认）。
     *
     * <p>以前这里无条件 {@code setAllowedOriginPatterns("*") + setAllowCredentials(true)}：
     * 前者会**反射请求的 Origin**，两者一起用等于「任何站点都能带凭证读响应」。
     * 本项目前端与接口同源（都由本进程托管）、鉴权走 {@code X-Auth-Token} 头而不是
     * cookie，所以这套配置没有任何使用方，纯粹是白送的攻击面。
     */
    private final List<String> allowedOrigins;

    public SecurityConfig(
            JwtAuthFilter jwtAuthFilter,
            AuthRateLimitFilter authRateLimitFilter,
            @Value("${CORS_ALLOWED_ORIGINS:}") String allowedOriginsRaw) {
        this.jwtAuthFilter = jwtAuthFilter;
        this.authRateLimitFilter = authRateLimitFilter;
        this.allowedOrigins = parseOrigins(allowedOriginsRaw);
    }

    /** 逗号分隔；只接受 http(s):// 开头的精确 origin，其余静默丢弃（写错了不该拦住启动）。 */
    private static List<String> parseOrigins(String raw) {
        if (raw == null || raw.isBlank()) {
            return List.of();
        }
        return Arrays.stream(raw.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .filter(s -> s.startsWith("http://") || s.startsWith("https://"))
                .toList();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        // 默认不注册 CORS：同源部署不需要它。只有显式配了 CORS_ALLOWED_ORIGINS 才挂白名单。
        // 注意这跟「允许被魔搭 iframe 嵌入」不是一回事 —— 那个靠下面的 CSP frame-ancestors。
        if (!allowedOrigins.isEmpty()) {
            http.cors(cors -> cors.configurationSource(corsSource()));
        }
        http.csrf(csrf -> csrf.disable())
                // 允许被魔搭创空间（www.modelscope.cn）用 iframe 嵌入。
                // Spring Security 默认发 X-Frame-Options: DENY，浏览器会直接拒绝渲染，
                // 表现是「线上点开链接一片空白」——而且服务端日志里一条错误都没有，
                // 只有浏览器控制台有一行 Refused to display。curl 完全看不出来。
                // 用 CSP frame-ancestors 代替 X-Frame-Options：能精确列出允许的父页面，
                // 比 DENY / SAMEORIGIN 这种二选一更合适（父页面是平台的壳，跨源）。
                .headers(h -> h
                        .frameOptions(f -> f.disable())
                        .contentSecurityPolicy(c -> c.policyDirectives(
                                "frame-ancestors 'self' https://modelscope.cn https://*.modelscope.cn https://*.ms.show")))
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(
                        auth ->
                                auth.requestMatchers(
                                                "/",
                                                "/index.html",
                                                "/features.html",
                                                "/trips.html",
                                                "/spots.html",
                                                "/share.html",
                                                "/favicon.ico",
                                                "/assets/**",
                                                "/error")
                                        .permitAll()
                                        // 分享页：token 本身就是凭证，不需要登录。
                                        // "/s" 要单独列：/s/** 在 Spring 6 的 PathPattern 下
                                        // 不匹配裸 /s（漏了它，无 token 的 /s 会掉进 401）
                                        .requestMatchers("/s", "/s/**", "/api/share/**")
                                        .permitAll()
                                        // 图片回读：<img src> 带不了自定义请求头，只能匿名；
                                        // 文件名是 16 字节随机串，等于「知道链接才能看」
                                        .requestMatchers(HttpMethod.GET, "/api/uploads/**")
                                        .permitAll()
                                        .requestMatchers(HttpMethod.POST, "/api/auth/login", "/api/auth/register")
                                        .permitAll()
                                        .requestMatchers(
                                                HttpMethod.GET,
                                                "/api/config",
                                                "/api/auth/options",
                                                "/api/health",
                                                "/api/knowledge/coverage",
                                                "/api/templates",
                                                "/api/agents")
                                        .permitAll()
                                        // 对话允许匿名（与原服务一致：官网演示不需要注册）
                                        .requestMatchers("/api/chat", "/api/chat/stream", "/api/chat/feedback")
                                        .permitAll()
                                        // 运营管理接口：入口处就要求 admin 角色。
                                        // 真正的权限判定在 Python 侧（require_admin），这里再加一道
                                        // 是为了「下游判断失效时不至于直接裸奔」——反代曾经因为身份头
                                        // 可被覆盖而让普通用户拿到管理权限，边界上多一道闸能挡住整类问题。
                                        .requestMatchers("/api/admin/**")
                                        .hasRole("ADMIN")
                                        .requestMatchers("/api/**")
                                        .authenticated()
                                        .anyRequest()
                                        .permitAll())
                .exceptionHandling(
                        ex ->
                                ex.authenticationEntryPoint(
                                                (req, res, e) -> {
                                                    // 拒绝原因放在响应头里：线上平台拿不到应用日志，
                                                    // 只凭「401」无法区分「没带 token」「签名不对」「用户没了」
                                                    // 「世代不符」——这四种的处理方式完全不同。
                                                    Object why = req.getAttribute(JwtAuthFilter.REASON_ATTR);
                                                    if (why != null) {
                                                        res.setHeader("X-Auth-Reason", why.toString());
                                                    }
                                                    writeJson(res, 401, "未登录或登录已过期");
                                                })
                                        .accessDeniedHandler((req, res, e) -> writeJson(res, 403, "需要管理员权限")))
                // 限流必须排在 JWT 之前：爆破请求不该先做一次 JWT 校验、再查一次用户表。
                // 注意顺序不能反：先把 jwtAuthFilter 插进链（这一步才会给它的类登记序号），
                // 再以它为锚点插限流器；反过来会抛
                // 「The Filter class JwtAuthFilter does not have a registered order」。
                .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class)
                .addFilterBefore(authRateLimitFilter, JwtAuthFilter.class);
        return http.build();
    }

    private void writeJson(HttpServletResponse res, int status, String detail) throws java.io.IOException {
        res.setStatus(status);
        res.setCharacterEncoding(StandardCharsets.UTF_8.name());
        res.setContentType(MediaType.APPLICATION_JSON_VALUE);
        res.getWriter().write("{\"detail\":\"" + detail + "\"}");
    }

    private CorsConfigurationSource corsSource() {
        CorsConfiguration cfg = new CorsConfiguration();
        // 精确值，绝不用 setAllowedOriginPatterns：那个会反射请求的 Origin，
        // 与 allowCredentials 一起用等于「任何站点都能带凭证读响应」。
        cfg.setAllowedOrigins(allowedOrigins);
        cfg.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        // 不用 "*"：本项目只用到这三种头，列清楚比放开好排查。
        cfg.setAllowedHeaders(List.of("Content-Type", "X-Auth-Token", "Authorization"));
        // 鉴权走 X-Auth-Token 头、没有 cookie，所以不需要凭证模式。
        // 以后若改成 cookie 会话，这里**必须**同步改回 true，否则浏览器会拒发跨源请求。
        cfg.setAllowCredentials(false);
        cfg.setMaxAge(3600L);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", cfg);
        return source;
    }
}
