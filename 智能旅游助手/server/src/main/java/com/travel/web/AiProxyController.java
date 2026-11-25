package com.travel.web;

import com.travel.config.AppProperties;
import com.travel.security.AuthUser;
import com.travel.security.CurrentUser;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 把 AI 相关请求转发给 Python 服务（RAG + 多 Agent）。
 *
 * <p>为什么用「通配前缀 + 原始字节透传」而不是一个个接口写转发：
 * AI 侧的接口还会长（内容库、知识库上传、SSE 流式对话），每加一个就要在 Java 里
 * 再写一遍转发方法，纯属重复劳动；而且 multipart 上传如果自己重新组装很容易坏。
 * 这里保持 method / header / body 原样，只有身份是 SpringBoot 验完再注入的。
 *
 * <p>身份怎么传：{@code X-Internal-Secret} + {@code X-User-Name} + {@code X-User-Role}。
 * Python 侧只在密钥匹配时才信任这几个头，所以外部无法伪造（外部请求带不了正确密钥）。
 */
@RestController
public class AiProxyController {

    private static final Logger log = LoggerFactory.getLogger(AiProxyController.class);

    /** 这些前缀归 AI 服务：对话、知识库、内容库、收藏、运营统计。 */
    private static final List<String> PREFIXES =
            List.of("/api/chat", "/api/agents", "/api/knowledge", "/api/notes", "/api/favorites", "/api/admin");

    /** 逐跳头：转发会破坏连接语义，必须剔除。 */
    private static final Set<String> HOP_BY_HOP =
            Set.of("host", "connection", "content-length", "transfer-encoding", "keep-alive", "upgrade",
                    "proxy-authenticate", "proxy-authorization", "te", "trailer");

    /**
     * 身份头：由本服务验完 JWT 之后注入，**客户端自带的一律丢弃**。
     *
     * <p>为什么必须在这里显式剔除，而不是「反正后面会再覆盖一次」：
     * {@link HttpRequest.Builder#header} 是**追加**语义（不是覆盖），同一个名字会出现
     * 两个值；而下游 FastAPI 的 {@code Headers.get()} 取的是**第一个**值。于是客户端
     * 只要自带 {@code X-User-Name: admin}，下游看到的就是 {@code admin}，本服务注入的
     * 真实用户名反而排在后面被忽略 —— 任何登录用户都能自称管理员。
     *
     * <p>所以这里做两件事：① 复制阶段跳过这三个头；② 注入阶段用
     * {@link HttpRequest.Builder#setHeader}（覆盖语义）而不是 {@code header}。
     * 两道保险各自独立成立，任一处被误改回原样都不会立刻破防。
     */
    private static final Set<String> IDENTITY_HEADERS =
            Set.of("x-user-name", "x-user-role", "x-internal-secret");

    /**
     * 客户端 IP 头：客户端带来的**一律丢弃**，由本服务用 {@code getRemoteAddr()} 重写。
     *
     * <p>为什么必须丢弃而不是"反正下游会用对的那个"：下游 FastAPI 在
     * {@code trust_proxy_headers=true} 时按 {@code X-Forwarded-For} 的**首段**分桶限流
     * （{@code app/ratelimit.py} 的 {@code client_ip}）。以前这些头被原样透传，于是
     * 客户端每换一个伪造的 XFF 就得到一个全新的限流桶 —— 单 IP 限流等于不存在，
     * 实测：伪造 7.7.7.1 连打 3 次才 429（那是它自己 2 次/分钟的上限），换 7.7.7.2
     * 立刻又能打 3 次。全局限流是唯一的兜底，而它是个能被一条请求打满的开关。
     *
     * <p>本服务是**唯一**公网入口，所以 {@code getRemoteAddr()} 就是真实客户端地址，
     * 由它重写 XFF 之后，下游看到的这个头才是可信的。三个头都丢，是因为下游
     * 在 XFF 缺失时会退到 {@code X-Real-IP}，只丢一个等于没丢。
     */
    private static final Set<String> CLIENT_IP_HEADERS =
            Set.of("x-forwarded-for", "x-real-ip", "forwarded");

    private final AppProperties props;
    private final CurrentUser currentUser;
    private final HttpClient http;

    public AiProxyController(AppProperties props, CurrentUser currentUser) {
        this.props = props;
        this.currentUser = currentUser;
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .followRedirects(HttpClient.Redirect.NEVER)
                // 必须锁 HTTP/1.1：JDK 的 HttpClient 默认会尝试 h2c 升级，发出
                // `Upgrade: h2c` + `Connection: Upgrade`。uvicorn（h11）不实现 h2c，
                // 会把这个请求当成协议升级处理，**请求体就丢了**——表现为 FastAPI 报
                // 「body Field required」。这个坑本地和线上一样存在，只是本地没测 POST 才发现。
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    @RequestMapping({"/api/chat/**", "/api/agents", "/api/knowledge/**", "/api/notes/**",
            "/api/favorites/**", "/api/admin/**"})
    public void proxy(HttpServletRequest req, HttpServletResponse res) throws Exception {
        String path = req.getRequestURI();
        if (PREFIXES.stream().noneMatch(path::startsWith)) {
            res.sendError(404);
            return;
        }
        String query = req.getQueryString();
        URI target = URI.create(props.ai().baseUrl() + path + (query == null ? "" : "?" + query));

        byte[] body = req.getInputStream().readAllBytes();
        log.debug("[proxy] {} {} body={}B ct={}", req.getMethod(), path, body.length, req.getContentType());
        HttpRequest.Builder builder = HttpRequest.newBuilder(target)
                .timeout(Duration.ofSeconds(props.ai().timeoutSeconds()))
                .method(req.getMethod(), body.length == 0
                        ? HttpRequest.BodyPublishers.noBody()
                        : HttpRequest.BodyPublishers.ofByteArray(body));

        Enumeration<String> names = req.getHeaderNames();
        while (names.hasMoreElements()) {
            String name = names.nextElement();
            String lower = name.toLowerCase(Locale.ROOT);
            if (HOP_BY_HOP.contains(lower)) {
                continue;
            }
            // 身份头只能由下面注入，客户端带来的同名头必须丢弃（见 IDENTITY_HEADERS 注释）
            if (IDENTITY_HEADERS.contains(lower)) {
                continue;
            }
            // 客户端 IP 头同样只能由下面重写（见 CLIENT_IP_HEADERS 注释）
            if (CLIENT_IP_HEADERS.contains(lower)) {
                continue;
            }
            // 原始鉴权头不外传：AI 侧只认内部信任头，减少一条伪造路径
            if (lower.equals("authorization") || lower.equals("x-auth-token")) {
                continue;
            }
            for (String value : Collections.list(req.getHeaders(name))) {
                builder.header(name, value);
            }
        }

        // setHeader（覆盖）而不是 header（追加）：追加会让下游看到两个值，取首值即被绕过
        builder.setHeader("X-Internal-Secret", props.ai().internalSecret());
        // 客户端 IP 由本服务重写。上游 XFF 已在复制阶段丢弃，这里 setHeader 是覆盖语义，
        // 两道保险各自独立成立（与身份头同一套理由）。
        String clientIp = req.getRemoteAddr();
        builder.setHeader("X-Forwarded-For", clientIp == null || clientIp.isBlank() ? "unknown" : clientIp);
        AuthUser user = currentUser.optional();
        if (user != null) {
            builder.setHeader("X-User-Name", user.username());
            builder.setHeader("X-User-Role", user.role());
        }

        HttpResponse<InputStream> resp;
        try {
            resp = http.send(builder.build(), HttpResponse.BodyHandlers.ofInputStream());
        } catch (Exception e) {
            log.warn("AI 服务不可达（{}）：{}", target, e.getMessage());
            res.setStatus(502);
            res.setContentType("application/json;charset=UTF-8");
            res.getWriter().write("{\"detail\":\"AI 服务暂时不可用，请稍后重试\"}");
            return;
        }

        res.setStatus(resp.statusCode());
        resp.headers().firstValue("content-type").ifPresent(ct -> res.setContentType(ct));
        resp.headers().firstValue("cache-control").ifPresent(cc -> res.setHeader("Cache-Control", cc));
        // Retry-After 必须一起转发：下游 429 会带它（例如匿名桶建议 55 秒后重试），
        // 不转发的话客户端只看到「429」而不知道等多久，只能立刻重试 —— 正好把桶打得更满。
        resp.headers().firstValue("retry-after").ifPresent(ra -> res.setHeader("Retry-After", ra));
        res.setHeader("X-Accel-Buffering", "no"); // 让反代不要缓冲，SSE 才能逐字出

        // 边读边写：对话是 SSE 流式返回，攒完再写会让用户盯着空白等十几秒
        try (InputStream in = resp.body(); OutputStream out = res.getOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                out.write(buf, 0, n);
                out.flush();
            }
        }
    }
}
