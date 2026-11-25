package com.travel.security;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * 显式配了白名单时，只有白名单里的 origin 拿到 ACAO。
 *
 * <p>这个类单独一个 Spring 上下文，因为它要改 {@code CORS_ALLOWED_ORIGINS}——
 * 与 {@link CorsDisabledByDefaultTest} 的默认配置不能共用。
 */
@SpringBootTest(
        properties = {
            "spring.datasource.url=jdbc:h2:mem:travel-cors-on;DB_CLOSE_DELAY=-1;MODE=MySQL",
            "spring.jpa.hibernate.ddl-auto=create-drop",
            "app.jwt.secret=travel-copilot-test-secret-please-32bytes",
            "app.ai.internal-secret=travel-copilot-test-internal-secret",
            "app.ai.base-url=http://127.0.0.1:9",
            "app.ai.timeout-seconds=1",
            "app.seed-spots=false",
            "app.upload-dir=target/test-uploads"
        })
@AutoConfigureMockMvc
class CorsWhitelistTest {

    @DynamicPropertySource
    static void corsOrigins(DynamicPropertyRegistry registry) {
        registry.add("CORS_ALLOWED_ORIGINS", () -> "https://ok.example, https://also.example");
    }

    @Autowired
    private MockMvc mvc;

    @Test
    @DisplayName("白名单内的 origin 拿到自己的 ACAO")
    void whitelistedOriginIsAllowed() throws Exception {
        mvc.perform(get("/api/health").header("Origin", "https://ok.example"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "https://ok.example"));
    }

    @Test
    @DisplayName("逗号分隔的第二项也生效（顺带验证 trim）")
    void secondWhitelistedOriginIsAllowed() throws Exception {
        mvc.perform(get("/api/health").header("Origin", "https://also.example"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "https://also.example"));
    }

    @Test
    @DisplayName("白名单外的 origin 拿不到 ACAO")
    void nonWhitelistedOriginIsRejected() throws Exception {
        mvc.perform(get("/api/health").header("Origin", "https://evil.example"))
                .andExpect(header().doesNotExist("Access-Control-Allow-Origin"));
    }

    @Test
    @DisplayName("即使命中白名单，也不开凭证模式（不用 cookie）")
    void credentialsAreNotAllowed() throws Exception {
        mvc.perform(get("/api/health").header("Origin", "https://ok.example"))
                .andExpect(header().doesNotExist("Access-Control-Allow-Credentials"));
    }
}
