package com.travel;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

/**
 * 任务书五个模块的端到端验证：景点库 / 偏好标签匹配 / 游记 / 图片上传 / 排期冲突。
 *
 * <p>这些用例是「答辩时能当场跑给人看」的那几条路径，所以断言写的是用户可见的结果
 * （筛出来的条数、推荐的命中数、冲突提示的措辞），不是内部实现。
 */
@SpringBootTest(
        properties = {
            "spring.datasource.url=jdbc:h2:mem:travel-feat;DB_CLOSE_DELAY=-1;MODE=MySQL",
            "spring.jpa.hibernate.ddl-auto=create-drop",
            "app.jwt.secret=travel-copilot-test-secret-please-32bytes",
            // 启动守卫要求内部密钥非空（不再有内置默认值）
            "app.ai.internal-secret=travel-copilot-test-internal-secret",
            "app.admin.username=admin",
            "app.admin.password=admin123",
            // 本类要注册新用户；生产默认已改为关闭开放注册
            "app.allow-registration=true",
            "app.ai.base-url=http://127.0.0.1:9",
            "app.ai.timeout-seconds=1",
            "app.seed-spots=false",
            "app.upload-dir=target/test-uploads"
        })
@AutoConfigureMockMvc
class SpotNoteFeatureTest {

    @Autowired
    private MockMvc mvc;

    @Autowired
    private ObjectMapper om;

    private String json(Object body) {
        try {
            return om.writeValueAsString(body);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> body(MvcResult r) {
        try {
            return om.readValue(r.getResponse().getContentAsString(StandardCharsets.UTF_8), Map.class);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private String register(String username) throws Exception {
        MvcResult r = mvc.perform(post("/api/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("username", username, "password", "pw123456"))))
                .andExpect(status().isOk())
                .andReturn();
        return (String) body(r).get("token");
    }

    /** 景点库维护是管理员操作，测试里统一用管理员令牌写入。 */
    private String adminToken() throws Exception {
        MvcResult r = mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("username", "admin", "password", "admin123"))))
                .andExpect(status().isOk())
                .andReturn();
        return (String) body(r).get("token");
    }

    private void addSpot(String token, Map<String, Object> spot) throws Exception {
        mvc.perform(post("/api/spots")
                        .header("X-Auth-Token", token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(spot)))
                .andExpect(status().isOk());
    }

    // ---------------------------------------------------------------- 景点库

    @Test
    @DisplayName("景点条件检索：分类 / 标签 / 免费 三个条件同时生效")
    void spotFiltersWork() throws Exception {
        String token = register("spotuser1");
        String admin = adminToken();
        addSpot(admin, Map.of("city", "杭州", "name", "西湖", "category", "公园", "ticket_price", 0));
        addSpot(admin, Map.of("city", "杭州", "name", "浙江省博物馆", "category", "场馆", "ticket_price", 0));
        addSpot(admin, Map.of("city", "杭州", "name", "宋城", "category", "街区", "ticket_price", 320));

        Map<?, ?> freePark = body(mvc.perform(get("/api/spots")
                        .header("X-Auth-Token", token)
                        .param("city", "杭州").param("category", "公园").param("free", "true"))
                .andExpect(status().isOk()).andReturn());
        assertThat((Integer) freePark.get("total")).isEqualTo(1);

        Map<?, ?> indoor = body(mvc.perform(get("/api/spots")
                        .header("X-Auth-Token", token)
                        .param("city", "杭州").param("tag", "室内"))
                .andExpect(status().isOk()).andReturn());
        assertThat((Integer) indoor.get("total")).isEqualTo(1);

        Map<?, ?> paid = body(mvc.perform(get("/api/spots")
                        .header("X-Auth-Token", token)
                        .param("city", "杭州").param("free", "false"))
                .andExpect(status().isOk()).andReturn());
        assertThat((Integer) paid.get("total")).isEqualTo(1);
    }

    /** 普通用户不能维护景点库：写接口是管理员专属。 */
    @Test
    @DisplayName("非管理员新增景点被拒绝（403）")
    void spotWriteRequiresAdmin() throws Exception {
        String token = register("spotuser2");
        mvc.perform(post("/api/spots")
                        .header("X-Auth-Token", token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("city", "杭州", "name", "灵隐寺", "category", "古迹"))))
                .andExpect(status().isForbidden());
    }

    // ---------------------------------------------------------------- 偏好与推荐

    @Test
    @DisplayName("偏好标签保存后，推荐按命中数排序且过滤掉零命中")
    void preferenceDrivesRecommendation() throws Exception {
        String token = register("prefuser");
        String admin = adminToken();
        addSpot(admin, Map.of("city", "成都", "name", "成都博物馆", "category", "场馆", "ticket_price", 0));
        addSpot(admin, Map.of("city", "成都", "name", "青城山", "category", "自然", "ticket_price", 80));
        addSpot(admin, Map.of("city", "成都", "name", "宽窄巷子", "category", "街区", "ticket_price", 0));

        mvc.perform(put("/api/auth/preferences")
                        .header("X-Auth-Token", token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("tags", List.of("室内", "免费")))))
                .andExpect(status().isOk());

        Map<?, ?> rec = body(mvc.perform(get("/api/spots/recommend")
                        .header("X-Auth-Token", token).param("city", "成都"))
                .andExpect(status().isOk()).andReturn());
        List<?> items = (List<?>) rec.get("items");
        assertThat(items).isNotEmpty();
        Map<?, ?> first = (Map<?, ?>) items.get(0);
        assertThat(first.get("name")).isEqualTo("成都博物馆");
        assertThat((Integer) first.get("match_count")).isEqualTo(2);
    }

    @Test
    @DisplayName("偏好最多 8 个，超出报 400 并说明原因")
    void preferenceLimit() throws Exception {
        String token = register("prefuser2");
        mvc.perform(put("/api/auth/preferences")
                        .header("X-Auth-Token", token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("tags", List.of("a", "b", "c", "d", "e", "f", "g", "h", "i")))))
                .andExpect(status().isBadRequest());
    }

    // ---------------------------------------------------------------- 游记与图片

    @Test
    @DisplayName("游记：建 → 查 → 改 → 删，且别人的行程看不到")
    void noteCrudAndOwnership() throws Exception {
        String owner = register("noteuser1");
        String other = register("noteuser2");
        String tripId = createTrip(owner);

        MvcResult created = mvc.perform(post("/api/trips/" + tripId + "/notes")
                        .header("X-Auth-Token", owner)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("title", "第一天", "content", "早上去了西湖，人很多。"))))
                .andExpect(status().isOk()).andReturn();
        long noteId = ((Number) ((Map<?, ?>) body(created).get("note")).get("id")).longValue();

        mvc.perform(get("/api/trips/" + tripId + "/notes").header("X-Auth-Token", owner))
                .andExpect(status().isOk());
        // 别人的行程：404，不是 403（403 等于告诉对方这个 id 存在）
        mvc.perform(get("/api/trips/" + tripId + "/notes").header("X-Auth-Token", other))
                .andExpect(status().isNotFound());

        mvc.perform(put("/api/trips/" + tripId + "/notes/" + noteId)
                        .header("X-Auth-Token", owner)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("content", "晚上又去了一次，安静多了。"))))
                .andExpect(status().isOk());

        mvc.perform(delete("/api/trips/" + tripId + "/notes/" + noteId).header("X-Auth-Token", owner))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("图片上传后能用返回的地址原样读回")
    void uploadAndReadBack() throws Exception {
        String token = register("imguser");
        byte[] png = new byte[] {
            (byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 0x0D, 'I', 'H', 'D', 'R'
        };
        MockMultipartFile file = new MockMultipartFile("file", "a.png", "image/png", png);
        MvcResult r = mvc.perform(multipart("/api/uploads").file(file).header("X-Auth-Token", token))
                .andExpect(status().isOk())
                .andReturn();
        String url = (String) body(r).get("url");
        assertThat(url).startsWith("/api/uploads/").endsWith(".png");
        // 回读是匿名的：<img src> 带不了自定义请求头
        mvc.perform(get(url)).andExpect(status().isOk());
    }

    @Test
    @DisplayName("非图片文件被拒绝")
    void uploadRejectsNonImage() throws Exception {
        String token = register("imguser2");
        MockMultipartFile file = new MockMultipartFile("file", "a.txt", "text/plain", "hi".getBytes());
        mvc.perform(multipart("/api/uploads").file(file).header("X-Auth-Token", token))
                .andExpect(status().isBadRequest());
    }

    // ---------------------------------------------------------------- 排期冲突

    @Test
    @DisplayName("同一天同一时段放两个景点 → 返回冲突提示（不拦截保存）")
    void conflictHint() throws Exception {
        String token = register("conflictuser");
        String tripId = createTrip(token);
        for (String name : List.of("西湖", "灵隐寺")) {
            mvc.perform(post("/api/trips/" + tripId + "/items")
                            .header("X-Auth-Token", token)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(json(Map.of("title", name, "day_index", 1, "slot", "上午"))))
                    .andExpect(status().isOk());
        }
        Map<?, ?> trip = body(mvc.perform(get("/api/trips/" + tripId).header("X-Auth-Token", token))
                .andExpect(status().isOk()).andReturn());
        Map<?, ?> inner = (Map<?, ?>) trip.get("trip");
        List<?> conflicts = (List<?>) inner.get("conflicts");
        assertThat(conflicts).isNotEmpty();
        assertThat(String.valueOf(conflicts.get(0))).contains("第 1 天").contains("上午");
    }

    private String createTrip(String token) throws Exception {
        MvcResult r = mvc.perform(post("/api/trips")
                        .header("X-Auth-Token", token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("city", "杭州", "days", 3, "budget", 2000))))
                .andExpect(status().isOk())
                .andReturn();
        return (String) ((Map<?, ?>) body(r).get("trip")).get("id");
    }
}
