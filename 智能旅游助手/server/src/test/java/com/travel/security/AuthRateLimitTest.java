package com.travel.security;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.travel.user.UserEntity;
import com.travel.user.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

/**
 * 登录 / 注册限流的端到端验证。
 *
 * <p>每个用例用**各自的用户名**，因为限流状态是过滤器 Bean 里的内存表、同一个 Spring
 * 上下文内共享——共用一个名字会互相污染，导致用例顺序一变就红。
 *
 * <p>注意这里测不到「窗口滑过之后放行」与「锁 60 秒后解锁」：那要真等 5 分钟 / 1 分钟。
 * 那两条在 {@link AuthRateLimitUnitTest} 里用可替换的 {@code Clock} 覆盖。
 */
@SpringBootTest(
        properties = {
            "spring.datasource.url=jdbc:h2:mem:travel-ratelimit;DB_CLOSE_DELAY=-1;MODE=MySQL",
            "spring.jpa.hibernate.ddl-auto=create-drop",
            "app.jwt.secret=travel-copilot-test-secret-please-32bytes",
            "app.ai.internal-secret=travel-copilot-test-internal-secret",
            "app.ai.base-url=http://127.0.0.1:9",
            "app.ai.timeout-seconds=1",
            "app.seed-spots=false",
            "app.allow-registration=true",
            "app.upload-dir=target/test-uploads"
        })
@AutoConfigureMockMvc
class AuthRateLimitTest {

    private static final String PASSWORD = "pw123456";

    @Autowired
    private MockMvc mvc;

    @Autowired
    private UserRepository users;

    @Autowired
    private PasswordEncoder encoder;

    private void ensureUser(String name) {
        if (!users.existsByUsername(name)) {
            users.save(new UserEntity(name, encoder.encode(PASSWORD), "user"));
        }
    }

    /**
     * 登录请求。
     *
     * <p>{@code servletPath} 必须显式设置：限流器用 {@code getServletPath()} 认路径
     * （已解码、已去 context-path），而 MockMvc 的请求替身默认把它留成空串 —— 不设的话
     * 限流器认为"这不是登录接口"，整条链跑下来一次都不会记账，用例会以错误理由变绿/变红。
     */
    private MockHttpServletRequestBuilder loginAs(String user, String password, String ip) {
        return post("/api/auth/login")
                .servletPath("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"" + user + "\",\"password\":\"" + password + "\"}")
                .with(
                        request -> {
                            request.setRemoteAddr(ip);
                            return request;
                        });
    }

    @Test
    @DisplayName("同一「用户名|IP」5 分钟内第 11 次请求返回 429，并带 Retry-After")
    void eleventhAttemptIsRateLimited() throws Exception {
        ensureUser("rl_window");
        // 用「正确口令」打满 10 次，避开账号锁（锁在 5 次失败时触发，会先返回 429）
        for (int i = 0; i < 10; i++) {
            mvc.perform(loginAs("rl_window", PASSWORD, "10.1.0.1")).andExpect(status().isOk());
        }
        mvc.perform(loginAs("rl_window", PASSWORD, "10.1.0.1"))
                .andExpect(status().isTooManyRequests())
                .andExpect(header().exists("Retry-After"))
                .andExpect(jsonPath("$.detail").exists());
    }

    @Test
    @DisplayName("桶按用户名隔离：同 IP 下另一个人不受影响")
    void otherUserOnSameIpIsNotAffected() throws Exception {
        ensureUser("rl_noisy");
        ensureUser("rl_quiet");
        for (int i = 0; i < 10; i++) {
            mvc.perform(loginAs("rl_noisy", PASSWORD, "10.1.0.2")).andExpect(status().isOk());
        }
        mvc.perform(loginAs("rl_noisy", PASSWORD, "10.1.0.2")).andExpect(status().isTooManyRequests());
        // 同一个 IP，换个人：照常放行
        mvc.perform(loginAs("rl_quiet", PASSWORD, "10.1.0.2")).andExpect(status().isOk());
    }

    @Test
    @DisplayName("连续失败 5 次后锁定：第 6 次即使密码正确也返回 429，且文案是「锁定」不是「密码错」")
    void lockoutBeatsCorrectPassword() throws Exception {
        ensureUser("rl_locked");
        for (int i = 0; i < 5; i++) {
            mvc.perform(loginAs("rl_locked", "wrong-pass", "10.1.0.3"))
                    .andExpect(status().isUnauthorized());
        }
        mvc.perform(loginAs("rl_locked", PASSWORD, "10.1.0.3"))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("锁定")));
    }

    @Test
    @DisplayName("代理场景：getRemoteAddr() 恒定时，被限流的人不影响另一个人")
    void constantRemoteAddrStillIsolatesUsers() throws Exception {
        ensureUser("rl_proxy_a");
        ensureUser("rl_proxy_b");
        // 模拟平台代理：所有人看到的 remoteAddr 都是同一个值
        String proxyIp = "172.16.0.9";
        for (int i = 0; i < 5; i++) {
            mvc.perform(loginAs("rl_proxy_a", "wrong-pass", proxyIp))
                    .andExpect(status().isUnauthorized());
        }
        mvc.perform(loginAs("rl_proxy_a", PASSWORD, proxyIp)).andExpect(status().isTooManyRequests());
        // 关键断言：IP 相同，但用户名不同 → 必须仍然是正常路径（401 而不是 429）
        mvc.perform(loginAs("rl_proxy_b", "wrong-pass", proxyIp)).andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("两次输错后输对：正常登录，不被误伤，且失败计数清零")
    void successAfterTwoFailuresIsFine() throws Exception {
        ensureUser("rl_typo");
        mvc.perform(loginAs("rl_typo", "wrong-pass", "10.1.0.4")).andExpect(status().isUnauthorized());
        mvc.perform(loginAs("rl_typo", "wrong-pass", "10.1.0.4")).andExpect(status().isUnauthorized());
        mvc.perform(loginAs("rl_typo", PASSWORD, "10.1.0.4")).andExpect(status().isOk());
        // 清零之后再错 4 次也不该被锁（如果没清零，加上前面的 2 次就会锁）
        for (int i = 0; i < 4; i++) {
            mvc.perform(loginAs("rl_typo", "wrong-pass", "10.1.0.4")).andExpect(status().isUnauthorized());
        }
    }

    @Test
    @DisplayName("注册按 IP 限流：同一 IP 换着名字注册，第 11 次返回 429")
    void registerIsLimitedPerIp() throws Exception {
        for (int i = 0; i < 10; i++) {
            mvc.perform(
                            post("/api/auth/register")
                                    .servletPath("/api/auth/register")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content("{\"username\":\"rl_reg" + i + "\",\"password\":\"pw123456\"}")
                                    .with(
                                            request -> {
                                                request.setRemoteAddr("10.1.0.5");
                                                return request;
                                            }))
                    .andExpect(status().isOk());
        }
        mvc.perform(
                        post("/api/auth/register")
                                .servletPath("/api/auth/register")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"username\":\"rl_reg_extra\",\"password\":\"pw123456\"}")
                                .with(
                                        request -> {
                                            request.setRemoteAddr("10.1.0.5");
                                            return request;
                                        }))
                .andExpect(status().isTooManyRequests());
    }

    @Test
    @DisplayName("空 body 仍是 400（过滤器读了 body，控制器还能读，且不是 500）")
    void emptyBodyStillBadRequest() throws Exception {
        mvc.perform(
                        post("/api/auth/login")
                                .servletPath("/api/auth/login")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("")
                                .with(
                                        request -> {
                                            request.setRemoteAddr("10.1.0.6");
                                            return request;
                                        }))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("超长 body（>8KB）不缓存、不 OOM，返回 400")
    void oversizedBodyIsRejectedWithoutBuffering() throws Exception {
        // 9KB 的非 JSON：超过 8KB 上限 → 过滤器不包装、不读进内存 → username 为 null，
        // 键退化成 anon|IP；body 原样交给控制器，由它按「不是合法 JSON」返回 400。
        String huge = "x".repeat(9000);
        mvc.perform(
                        post("/api/auth/login")
                                .servletPath("/api/auth/login")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(huge)
                                .with(
                                        request -> {
                                            request.setRemoteAddr("10.1.0.7");
                                            return request;
                                        }))
                .andExpect(status().isBadRequest());
        // 同一个 IP 上正常的请求不受影响
        ensureUser("rl_after_huge");
        mvc.perform(loginAs("rl_after_huge", PASSWORD, "10.1.0.7")).andExpect(status().isOk());
    }
}
