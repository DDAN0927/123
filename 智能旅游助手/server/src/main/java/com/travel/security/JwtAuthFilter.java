package com.travel.security;

import com.travel.user.UserEntity;
import com.travel.user.UserRepository;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.Optional;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 从请求头取 token 并放进 SecurityContext。
 *
 * <p>两种携带方式都支持，原因与原 Python 服务一致：
 * <ul>
 *   <li>{@code Authorization: Bearer <token>} —— 标准做法；</li>
 *   <li>{@code X-Auth-Token: <token>} —— 兜底。部分云平台边缘 WAF 会把带
 *       {@code Authorization: Bearer} 的请求当成 SDK 直连直接 403，
 *       与 token 内容无关。</li>
 * </ul>
 *
 * <p>这里不抛异常：无 token / token 非法都放行，交给 SecurityConfig 的
 * {@code authenticated()} 规则决定是否 401。这样公开接口（官网、分享页）不会被误拦。
 *
 * <p>「改密即踢线」：JWT 本身无法撤销，所以每个用户带一个整数「会话世代」，
 * token 里记着签发时的世代，与用户当前世代不一致即视为失效。用世代而不是时间戳，
 * 是因为 JWT 的 {@code iat} 只有秒级精度 —— 同一秒内改密再签发的 token
 * 会永远躲过时间比较，等于泄露的 token 永久有效。
 */
@Component
public class JwtAuthFilter extends OncePerRequestFilter {

    /** 请求属性名：401 时由 SecurityConfig 写进响应头 {@code X-Auth-Reason}。 */
    public static final String REASON_ATTR = "travel.auth.reason";

    private final JwtService jwtService;
    private final UserRepository users;

    public JwtAuthFilter(JwtService jwtService, UserRepository users) {
        this.jwtService = jwtService;
        this.users = users;
    }

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain chain)
            throws ServletException, IOException {
        String token = extractToken(request);
        if (token == null || token.isBlank()) {
            request.setAttribute(REASON_ATTR, "no-token");
            chain.doFilter(request, response);
            return;
        }
        JwtService.Parsed parsed = jwtService.verify(token);
        if (parsed == null) {
            request.setAttribute(REASON_ATTR, "bad-token");
            chain.doFilter(request, response);
            return;
        }
        if (SecurityContextHolder.getContext().getAuthentication() == null) {
            AuthUser user = parsed.user();
            String reason = whyNotValid(user.username(), parsed.epoch());
            if (reason == null) {
                var authorities = List.of(new SimpleGrantedAuthority("ROLE_" + user.role().toUpperCase()));
                var auth = new UsernamePasswordAuthenticationToken(user, null, authorities);
                SecurityContextHolder.getContext().setAuthentication(auth);
            } else {
                request.setAttribute(REASON_ATTR, reason);
            }
        }
        chain.doFilter(request, response);
    }

    /**
     * 用户仍存在，且 token 的会话世代与当前一致（改密后世代 +1，旧 token 全部失效）。
     *
     * @return null 表示有效；否则返回拒绝原因（写进响应头 {@code X-Auth-Reason}）
     */
    private String whyNotValid(String username, long epoch) {
        Optional<UserEntity> user = users.findByUsername(username);
        if (user.isEmpty()) {
            return "user-missing";
        }
        return user.get().epoch() == epoch ? null : "epoch-mismatch";
    }

    /**
     * 取 token。
     *
     * <p><b>先 {@code X-Auth-Token}，再 {@code Authorization}</b>。反过来会在某些云平台上出问题：
     * 边缘网关自己可能给上游补一个 {@code Authorization}，那样我们就会拿到网关的凭证而不是用户的，
     * 表现为「刚签发的 token 立刻 401」，且本地永远复现不了。
     */
    private String extractToken(HttpServletRequest request) {
        String direct = request.getHeader("X-Auth-Token");
        if (direct != null && !direct.isBlank()) {
            return direct.trim();
        }
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            String token = header.substring(7).trim();
            if (!token.isEmpty()) {
                return token;
            }
        }
        return null;
    }
}
