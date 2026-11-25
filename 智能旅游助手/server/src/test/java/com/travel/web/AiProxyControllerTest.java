package com.travel.web;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.sun.net.httpserver.HttpServer;
import com.travel.user.UserEntity;
import java.io.IOException;
import java.net.InetSocketAddress;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * 反代必须把 POST 的请求体原样转出去。
 *
 * <p>这组用例是补一次真实事故：线上「问一句」永远返回 422「body Field required」，
 * 而 GET 类接口（知识库覆盖边界）一切正常，所以人工点几下很容易漏掉。
 * 根因是 JDK 的 {@code HttpClient} 默认尝试 h2c 升级，uvicorn 不实现 h2c，请求体就丢了。
 *
 * <p>所以这里除了断言「body 到了」，还断言「没有带 Upgrade 头」——
 * 后者才是当初真正出错的地方，只断言 body 的话，用一个宽容的 stub 是测不出来的。
 */
@SpringBootTest(
        properties = {
            "app.ai.internal-secret=test-secret",
            // 启动守卫要求显式配置 JWT 密钥（不再有内置默认值）
            "app.jwt.secret=travel-copilot-test-secret-please-32bytes",
            // 用内存库：本类会建测试用户，绝不能写进真实的 data/travel-server 文件库
            "spring.datasource.url=jdbc:h2:mem:travel-proxy;DB_CLOSE_DELAY=-1;MODE=MySQL",
            "spring.jpa.hibernate.ddl-auto=create-drop",
            // 本类不测景点库，跳过 8000+ 条种子数据（省 ~1.7s 且少一堆日志）
            "app.seed-spots=false"
        })
@AutoConfigureMockMvc
class AiProxyControllerTest {

    private static HttpServer stub;

    private static volatile String seenMethod;
    private static volatile String seenPath;
    private static volatile String seenBody;
    private static volatile String seenContentType;
    private static volatile String seenUpgrade;
    private static volatile String seenSecret;
    /** 用 List 而不是 String：要能断言「同名头只有一条」，取首值看不出重复。 */
    private static volatile java.util.List<String> seenUserNames;
    private static volatile java.util.List<String> seenUserRoles;
    private static volatile java.util.List<String> seenSecrets;
    /** 客户端 IP 头：下游按 XFF 首段分桶限流，所以这几个头必须由本服务重写，不能被透传。 */
    private static volatile java.util.List<String> seenForwardedFor;
    private static volatile java.util.List<String> seenRealIp;
    private static volatile java.util.List<String> seenForwarded;

    static {
        try {
            stub = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            stub.createContext(
                    "/",
                    ex -> {
                        seenMethod = ex.getRequestMethod();
                        seenPath = ex.getRequestURI().getPath();
                        seenBody = new String(ex.getRequestBody().readAllBytes(), UTF_8);
                        seenContentType = ex.getRequestHeaders().getFirst("Content-Type");
                        seenUpgrade = ex.getRequestHeaders().getFirst("Upgrade");
                        seenSecret = ex.getRequestHeaders().getFirst("X-Internal-Secret");
                        seenUserNames = ex.getRequestHeaders().get("X-User-Name");
                        seenUserRoles = ex.getRequestHeaders().get("X-User-Role");
                        seenSecrets = ex.getRequestHeaders().get("X-Internal-Secret");
                        seenForwardedFor = ex.getRequestHeaders().get("X-Forwarded-For");
                        seenRealIp = ex.getRequestHeaders().get("X-Real-IP");
                        seenForwarded = ex.getRequestHeaders().get("Forwarded");
                        byte[] out = "{\"ok\":true}".getBytes(UTF_8);
                        ex.getResponseHeaders().add("Content-Type", "application/json");
                        ex.sendResponseHeaders(200, out.length);
                        ex.getResponseBody().write(out);
                        ex.close();
                    });
            stub.start();
        } catch (IOException e) {
            throw new IllegalStateException("起不了 AI stub", e);
        }
    }

    @DynamicPropertySource
    static void aiBaseUrl(DynamicPropertyRegistry registry) {
        registry.add("app.ai.base-url", () -> "http://127.0.0.1:" + stub.getAddress().getPort());
    }

    @AfterAll
    static void stop() {
        stub.stop(0);
    }

    @Autowired private MockMvc mvc;

    @Autowired private com.travel.security.JwtService jwt;

    @Autowired private com.travel.user.UserRepository users;

    @Autowired private org.springframework.security.crypto.password.PasswordEncoder encoder;

    @BeforeEach
    void reset() {
        seenMethod = null;
        seenPath = null;
        seenBody = null;
        seenContentType = null;
        seenUpgrade = null;
        seenSecret = null;
        seenUserNames = null;
        seenUserRoles = null;
        seenSecrets = null;
        seenForwardedFor = null;
        seenRealIp = null;
        seenForwarded = null;
    }

    /** 造一个真实用户并签发 token（走真实 JwtAuthFilter 路径，不 mock 鉴权）。 */
    private String token(String username, String role) {
        users.findByUsername(username)
                .orElseGet(() -> users.save(new UserEntity(username, encoder.encode("pw123456"), role)));
        return jwt.issue(username, role, 0L);
    }

    @Test
    @DisplayName("POST 的 JSON body 原样转给 AI 服务")
    void forwardsPostBody() throws Exception {
        String payload = "{\"message\":\"故宫门票多少钱\"}";
        mvc.perform(
                        post("/api/chat")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(payload))
                .andExpect(status().isOk());

        assertThat(seenMethod).isEqualTo("POST");
        assertThat(seenPath).isEqualTo("/api/chat");
        assertThat(seenBody).isEqualTo(payload);
        assertThat(seenContentType).contains("application/json");
        assertThat(seenSecret).isEqualTo("test-secret");
    }

    @Test
    @DisplayName("不能带 h2c 升级头：uvicorn 不实现 h2c，会把请求体丢掉")
    void doesNotUpgradeToH2c() throws Exception {
        mvc.perform(post("/api/chat").contentType(MediaType.APPLICATION_JSON).content("{\"message\":\"hi\"}"))
                .andExpect(status().isOk());

        assertThat(seenUpgrade).isNull();
    }

    // ------------------------------------------------------------ 身份头不可伪造

    @Test
    @DisplayName("客户端自带的身份头被丢弃：下游只看到本服务注入的那一条")
    void forgedIdentityHeadersAreDropped() throws Exception {
        String token = token("proxyuser", "user");
        mvc.perform(
                        post("/api/chat")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"message\":\"hi\"}")
                                .header("X-Auth-Token", token)
                                // 攻击载荷：客户端自称管理员，并试图覆盖内部密钥
                                .header("X-User-Name", "admin")
                                .header("X-User-Role", "admin")
                                .header("X-Internal-Secret", "forged"))
                .andExpect(status().isOk());

        // 每个身份头都必须**只有一条**：追加语义会让下游取到客户端那个值（这就是原漏洞）
        assertThat(seenUserNames).containsExactly("proxyuser");
        assertThat(seenUserRoles).containsExactly("user");
        assertThat(seenSecrets).containsExactly("test-secret");
    }

    @Test
    @DisplayName("客户端伪造的 X-Forwarded-For 被丢弃并重写为真实来源：换头开不了新限流桶")
    void forgedForwardedForIsDroppedAndRewritten() throws Exception {
        mvc.perform(
                        post("/api/chat")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"message\":\"hi\"}")
                                // 攻击载荷：下游按 XFF 首段分桶，换一个值就是一个新桶
                                .header("X-Forwarded-For", "6.6.6.6")
                                .header("X-Real-IP", "7.7.7.7")
                                .header("Forwarded", "for=8.8.8.8"))
                .andExpect(status().isOk());

        // 必须**只有一条**且等于真实来源：追加语义会让下游取到 6.6.6.6（原漏洞），
        // 而不丢弃 X-Real-IP / Forwarded 的话，下游在 XFF 缺失时会退到它们（等于没修）。
        assertThat(seenForwardedFor).containsExactly("127.0.0.1");
        assertThat(seenRealIp).isNull();
        assertThat(seenForwarded).isNull();
    }

    @Test
    @DisplayName("普通用户伪造身份头打管理接口：入口处就 403，请求根本不会到反代")
    void forgedHeadersCannotReachAdminApi() throws Exception {
        String token = token("proxyuser2", "user");
        mvc.perform(
                        get("/api/admin/stats")
                                .header("X-Auth-Token", token)
                                .header("X-User-Name", "admin")
                                .header("X-User-Role", "admin"))
                .andExpect(status().isForbidden());

        assertThat(seenPath).isNull();
    }

    @Test
    @DisplayName("管理员访问管理接口仍然 200：守卫没有误伤正常用户")
    void adminStillReachesAdminApi() throws Exception {
        String token = token("proxyadmin", "admin");
        mvc.perform(get("/api/admin/stats").header("X-Auth-Token", token))
                .andExpect(status().isOk());

        assertThat(seenPath).isEqualTo("/api/admin/stats");
        assertThat(seenUserRoles).containsExactly("admin");
    }
}
