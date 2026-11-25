package com.travel.common;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

/**
 * 请求体读不出来时必须是 400，不能是 500。
 *
 * <p>为什么值得单独一个测试类：登录接口是公网唯一入口，扫描器扫它的时候发的就是
 * 空 POST 或者一坨非 JSON。这类请求掉进 {@code Exception} 兜底会返回 500 并打一条
 * ERROR 堆栈——日志被刷满、监控报警，而实际上服务器一点问题都没有。
 *
 * <p>修复前实测：{@code emptyBodyIsBadRequest} 与 {@code nonJsonBodyIsBadRequest}
 * 都是 {@code expected:<400> but was:<500>}；另外两条本来就过（缺字段走校验、错口令走 401），
 * 说明差异只来自这个处理器。
 *
 * <p>这几条同时也是 S-03 限流过滤器的前置约束：过滤器要读 body 里的 username，
 * 读完还得让控制器读得到，并且空 body 不能被它变成 500。
 */
@SpringBootTest(
        properties = {
            "spring.datasource.url=jdbc:h2:mem:travel-err;DB_CLOSE_DELAY=-1;MODE=MySQL",
            "spring.jpa.hibernate.ddl-auto=create-drop",
            "app.jwt.secret=travel-copilot-test-secret-please-32bytes",
            "app.ai.internal-secret=travel-copilot-test-internal-secret",
            "app.ai.base-url=http://127.0.0.1:9",
            "app.ai.timeout-seconds=1",
            "app.seed-spots=false",
            "app.upload-dir=target/test-uploads"
        })
@AutoConfigureMockMvc
class GlobalExceptionHandlerTest {

    @Autowired
    private MockMvc mvc;

    @Test
    @DisplayName("空 body 的 POST /api/auth/login 返回 400，不是 500")
    void emptyBodyIsBadRequest() throws Exception {
        mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON).content(""))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detail").exists());
    }

    @Test
    @DisplayName("非 JSON 的 body 返回 400，不是 500")
    void nonJsonBodyIsBadRequest() throws Exception {
        mvc.perform(
                        post("/api/auth/login")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("this-is-not-json"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detail").exists());
    }

    @Test
    @DisplayName("合法 JSON 但缺字段，仍然 400（走校验那条路，不是 500）")
    void missingFieldsIsBadRequest() throws Exception {
        mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detail").exists());
    }

    @Test
    @DisplayName("正常请求不被新处理器影响：错口令仍是 401")
    void normalRequestStillUnauthorized() throws Exception {
        mvc.perform(
                        post("/api/auth/login")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"username\":\"nobody\",\"password\":\"wrong-pass\"}"))
                .andExpect(status().isUnauthorized());
    }
}
