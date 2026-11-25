package com.travel.security;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

/**
 * 默认（不配 CORS_ALLOWED_ORIGINS）时，任何跨源请求都不该拿到 ACAO。
 *
 * <p>以前这里是 {@code setAllowedOriginPatterns("*") + setAllowCredentials(true)}：
 * 前者会反射请求的 Origin，等于任何站点都能带凭证读响应。而本项目前端与接口同源、
 * 鉴权走 {@code X-Auth-Token} 头，这套配置根本没有使用方——纯白送的攻击面。
 */
@SpringBootTest(
        properties = {
            "spring.datasource.url=jdbc:h2:mem:travel-cors-off;DB_CLOSE_DELAY=-1;MODE=MySQL",
            "spring.jpa.hibernate.ddl-auto=create-drop",
            "app.jwt.secret=travel-copilot-test-secret-please-32bytes",
            "app.ai.internal-secret=travel-copilot-test-internal-secret",
            "app.ai.base-url=http://127.0.0.1:9",
            "app.ai.timeout-seconds=1",
            "app.seed-spots=false",
            "app.upload-dir=target/test-uploads"
        })
@AutoConfigureMockMvc
class CorsDisabledByDefaultTest {

    @Autowired
    private MockMvc mvc;

    @Test
    @DisplayName("跨源 GET 不再返回 Access-Control-Allow-Origin")
    void crossOriginGetHasNoCorsHeader() throws Exception {
        mvc.perform(get("/api/health").header("Origin", "https://evil.example"))
                .andExpect(status().isOk())
                .andExpect(header().doesNotExist("Access-Control-Allow-Origin"));
    }

    @Test
    @DisplayName("跨源预检请求也不放行（没有 ACAO、没有 allow-credentials）")
    void preflightIsNotAllowed() throws Exception {
        mvc.perform(
                        options("/api/chat")
                                .header("Origin", "https://evil.example")
                                .header("Access-Control-Request-Method", "POST"))
                .andExpect(header().doesNotExist("Access-Control-Allow-Origin"))
                .andExpect(header().doesNotExist("Access-Control-Allow-Credentials"));
    }
}
