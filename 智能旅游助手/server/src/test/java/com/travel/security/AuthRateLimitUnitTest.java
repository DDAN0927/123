package com.travel.security;

import static org.assertj.core.api.Assertions.assertThat;

import jakarta.servlet.FilterChain;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

/**
 * 限流器的时间相关行为：窗口滑过、锁到期、键归一化、超大 body。
 *
 * <p>这些用例**不起 Spring**，直接 new 出过滤器并替换内部的 {@code Clock}——
 * 「等 5 分钟」「等 60 秒」在集成测试里没法测，不测又等于把最容易写错的两条逻辑
 * （窗口边界、锁过期）留给线上。
 */
class AuthRateLimitUnitTest {

    private static final long T0 = 1_700_000_000_000L;

    private static AuthRateLimitFilter filterAt(long millis) {
        AuthRateLimitFilter filter = new AuthRateLimitFilter();
        filter.setClock(Clock.fixed(Instant.ofEpochMilli(millis), ZoneOffset.UTC));
        return filter;
    }

    /**
     * 构造一个登录请求。
     *
     * <p>{@code setServletPath} 不是可选的：过滤器用 {@code getServletPath()} 认路径
     * （它已解码、已去 context-path），而 {@link MockHttpServletRequest} 的 servletPath
     * 默认是空串 —— 不设的话过滤器会认为"这不是登录接口"，用例就测不到任何限流。
     */
    private static MockHttpServletRequest loginReq(String username) {
        MockHttpServletRequest req = new MockHttpServletRequest("POST", "/api/auth/login");
        req.setServletPath("/api/auth/login");
        req.setRemoteAddr("10.0.0.1");
        req.setContentType("application/json");
        req.setContent(
                ("{\"username\":\"" + username + "\",\"password\":\"pw\"}")
                        .getBytes(StandardCharsets.UTF_8));
        return req;
    }

    /** 固定返回某个状态码的链路，用来模拟「控制器判成功 / 判失败」。 */
    private static FilterChain chainReturning(int status) {
        return (req, res) -> ((MockHttpServletResponse) res).setStatus(status);
    }

    @Test
    @DisplayName("窗口滑过 5 分钟后重新放行")
    void windowSlidesAfterFiveMinutes() throws Exception {
        AuthRateLimitFilter filter = filterAt(T0);
        for (int i = 0; i < 10; i++) {
            MockHttpServletResponse res = new MockHttpServletResponse();
            filter.doFilterInternal(loginReq("alice"), res, chainReturning(200));
            assertThat(res.getStatus()).isEqualTo(200);
        }

        MockHttpServletResponse blocked = new MockHttpServletResponse();
        filter.doFilterInternal(loginReq("alice"), blocked, chainReturning(200));
        assertThat(blocked.getStatus()).isEqualTo(429);
        assertThat(blocked.getHeader("Retry-After")).isNotBlank();

        // 推进到窗口之外：旧记录应被清掉，重新放行
        filter.setClock(Clock.fixed(Instant.ofEpochMilli(T0 + 5 * 60_000L + 1_000L), ZoneOffset.UTC));
        MockHttpServletResponse after = new MockHttpServletResponse();
        filter.doFilterInternal(loginReq("alice"), after, chainReturning(200));
        assertThat(after.getStatus()).isEqualTo(200);
    }

    @Test
    @DisplayName("锁 60 秒后自动解锁")
    void lockExpiresAfterSixtySeconds() throws Exception {
        AuthRateLimitFilter filter = filterAt(T0);
        for (int i = 0; i < 5; i++) {
            MockHttpServletResponse res = new MockHttpServletResponse();
            filter.doFilterInternal(loginReq("bob"), res, chainReturning(401));
            assertThat(res.getStatus()).isEqualTo(401);
        }

        MockHttpServletResponse locked = new MockHttpServletResponse();
        filter.doFilterInternal(loginReq("bob"), locked, chainReturning(200));
        assertThat(locked.getStatus()).isEqualTo(429);
        assertThat(locked.getContentAsString()).contains("锁定");

        filter.setClock(Clock.fixed(Instant.ofEpochMilli(T0 + 61_000L), ZoneOffset.UTC));
        MockHttpServletResponse after = new MockHttpServletResponse();
        filter.doFilterInternal(loginReq("bob"), after, chainReturning(200));
        assertThat(after.getStatus()).isEqualTo(200);
    }

    @Test
    @DisplayName("用户名先 trim：\" bob \" 与 \"bob\" 必须共用一个桶，否则加空格就绕过锁定")
    void paddedUsernameSharesTheSameBucket() throws Exception {
        AuthRateLimitFilter filter = filterAt(T0);
        for (int i = 0; i < 5; i++) {
            MockHttpServletResponse res = new MockHttpServletResponse();
            filter.doFilterInternal(loginReq("  bob  "), res, chainReturning(401));
            assertThat(res.getStatus()).isEqualTo(401);
        }
        // 换成没有空格的名字打正确口令：应该已经被锁住
        MockHttpServletResponse locked = new MockHttpServletResponse();
        filter.doFilterInternal(loginReq("bob"), locked, chainReturning(200));
        assertThat(locked.getStatus()).isEqualTo(429);
    }

    @Test
    @DisplayName("超过 8KB 的 body 不被缓存，且下游仍能完整读到")
    void oversizedBodyIsNotBuffered() throws Exception {
        AuthRateLimitFilter filter = filterAt(T0);
        MockHttpServletRequest req = new MockHttpServletRequest("POST", "/api/auth/login");
        req.setServletPath("/api/auth/login");
        req.setRemoteAddr("10.0.0.9");
        req.setContentType("application/json");
        byte[] huge = "x".repeat(9000).getBytes(StandardCharsets.UTF_8);
        req.setContent(huge);

        int[] seenByDownstream = {0};
        FilterChain reading = (rq, rs) -> {
            seenByDownstream[0] = rq.getInputStream().readAllBytes().length;
            ((MockHttpServletResponse) rs).setStatus(400);
        };

        MockHttpServletResponse res = new MockHttpServletResponse();
        filter.doFilterInternal(req, res, reading);
        assertThat(res.getStatus()).isEqualTo(400);
        // 关键：过滤器没把流读干，控制器还能读到完整 body
        assertThat(seenByDownstream[0]).isEqualTo(huge.length);
    }

    @Test
    @DisplayName("只拦登录与注册的 POST，其它请求直接放过")
    void onlyGuardsLoginAndRegister() {
        AuthRateLimitFilter filter = new AuthRateLimitFilter();

        MockHttpServletRequest options = mock("GET", "/api/auth/options");
        assertThat(filter.shouldNotFilter(options)).isTrue();

        MockHttpServletRequest me = mock("GET", "/api/auth/me");
        assertThat(filter.shouldNotFilter(me)).isTrue();

        MockHttpServletRequest changePwd = mock("POST", "/api/auth/change-password");
        assertThat(filter.shouldNotFilter(changePwd)).isTrue();

        MockHttpServletRequest login = mock("POST", "/api/auth/login");
        assertThat(filter.shouldNotFilter(login)).isFalse();

        MockHttpServletRequest register = mock("POST", "/api/auth/register");
        assertThat(filter.shouldNotFilter(register)).isFalse();

        // 编码过的路径必须与明文路径等价：MVC 解码后照样路由到登录接口，
        // 过滤器若按原始 URI 判断就会整段跳过（S-03 实测绕过）。
        MockHttpServletRequest encoded = mock("POST", "/api/auth/login");
        encoded.setServletPath("/api/auth/login");
        encoded.setRequestURI("/api/auth/%6Cogin");
        assertThat(filter.shouldNotFilter(encoded)).isFalse();

        // 配了 context-path 的部署：servletPath 不含前缀，判断结果必须不变。
        MockHttpServletRequest withContext = mock("POST", "/api/auth/login");
        withContext.setContextPath("/travel");
        withContext.setServletPath("/api/auth/login");
        withContext.setRequestURI("/travel/api/auth/login");
        assertThat(filter.shouldNotFilter(withContext)).isFalse();
    }

    /** 一个"路径正确"的替身：servletPath 与 requestURI 同时设置，贴近真实容器。 */
    private static MockHttpServletRequest mock(String method, String path) {
        MockHttpServletRequest req = new MockHttpServletRequest(method, path);
        req.setServletPath(path);
        return req;
    }
}
