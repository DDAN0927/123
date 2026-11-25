package com.travel;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.forwardedUrl;
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
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

/**
 * 端到端接口测试（MockMvc + 内存 H2）。
 *
 * <p>单元测试证明「每个零件对」，这里证明「装起来还对」。覆盖的是几条一旦坏了
 * 整条链路就废掉的路径：登录 → 建行程 → 记一笔账 → 分享 → 导出。
 *
 * <p>用内存库而不是文件库：测试之间互不影响，跑完不留垃圾。
 * AI 相关接口指向一个必然连不上的端口 —— 这里要验的是「AI 挂了主流程还能用」，
 * 不是 AI 本身（那部分在 Python 侧用 pytest 覆盖）。
 */
@SpringBootTest(
        properties = {
            "spring.datasource.url=jdbc:h2:mem:travel-it;DB_CLOSE_DELAY=-1;MODE=MySQL",
            "spring.jpa.hibernate.ddl-auto=create-drop",
            "app.jwt.secret=travel-copilot-test-secret-please-32bytes",
            // 启动守卫要求内部密钥非空（不再有内置默认值）
            "app.ai.internal-secret=travel-copilot-test-internal-secret",
            "app.admin.username=admin",
            "app.admin.password=admin123",
            // 本类要注册新用户；生产默认已改为关闭开放注册
            "app.allow-registration=true",
            // 本类 29 个用例每个都要注册一个新账号，全部来自同一个 remoteAddr（MockMvc
            // 默认 127.0.0.1），会撞上注册限流（生产默认 10 次/小时/IP）。这里只为测试
            // 调高，生产默认值不动——限流本身的行为在 AuthRateLimitTest 里单独验证。
            "app.auth-rate-limit.register-per-hour=1000",
            "app.ai.base-url=http://127.0.0.1:9",
            "app.ai.timeout-seconds=1",
            "app.seed-spots=false"
        })
@AutoConfigureMockMvc
class TripFlowIntegrationTest {

    @Autowired
    private MockMvc mvc;

    @Autowired
    private ObjectMapper om;

    // ---------------------------------------------------------------- 工具

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
        MvcResult r =
                mvc.perform(
                                post("/api/auth/register")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(json(Map.of("username", username, "password", "pw123456"))))
                        .andExpect(status().isOk())
                        .andReturn();
        return (String) body(r).get("token");
    }

    private String createTrip(String token, String city, int days, int budget) throws Exception {
        MvcResult r =
                mvc.perform(
                                post("/api/trips")
                                        .header("X-Auth-Token", token)
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(json(Map.of("city", city, "days", days, "budget", budget, "start_date", "2026-11-01"))))
                        .andExpect(status().isOk())
                        .andReturn();
        return (String) ((Map<?, ?>) body(r).get("trip")).get("id");
    }

    // ---------------------------------------------------------------- 公开面

    @Test
    @DisplayName("/api/config 与 /api/health 不需要登录")
    void publicEndpointsAreOpen() throws Exception {
        mvc.perform(get("/api/config")).andExpect(status().isOk());
        mvc.perform(get("/api/health")).andExpect(status().isOk()).andExpect(content().string(org.hamcrest.Matchers.containsString("spring-boot")));
    }

    /**
     * 地图 Key 必须有值：环境变量没配时也要回落到项目默认值。
     *
     * <p>这条守的是一个很隐蔽的线上故障——同一个仓库部署两个站点，一个能看地图、
     * 一个显示「地图加载失败」，因为其中一个平台后台没配 AMAP_KEY，而代码默认给空串。
     * 空串会让前端直接渲染 AMAP_FAIL_HTML，而且不报任何服务端错误。
     */
    @Test
    @DisplayName("/api/config 下发的高德 Key 与安全密钥不能为空")
    void amapConfigHasDefaults() throws Exception {
        MvcResult r = mvc.perform(get("/api/config")).andExpect(status().isOk()).andReturn();
        Map<?, ?> cfg = body(r);
        assertThat((String) cfg.get("amap_key")).isNotBlank();
        assertThat((String) cfg.get("amap_security_js_code")).isNotBlank();
    }

    /** 缺失的静态资源是 404，不是 500：原来会掉进 Exception 兜底，打 ERROR 堆栈。 */
    @Test
    @DisplayName("不存在的页面返回 404 而不是 500")
    void missingResourceIs404() throws Exception {
        mvc.perform(get("/nope-page.html")).andExpect(status().isNotFound());
        mvc.perform(get("/assets/js/nope.js")).andExpect(status().isNotFound());
    }

    /**
     * 必须允许被平台壳嵌入。
     *
     * <p>Spring Security 默认发 {@code X-Frame-Options: DENY}，而魔搭创空间是把应用
     * iframe 嵌在 www.modelscope.cn 里的 —— 于是浏览器直接拒绝渲染，线上打开是一片空白，
     * 服务端日志一条错误都没有（curl 也看不出来，因为它不发 Sec-Fetch-* 头、不触发嵌套）。
     */
    @Test
    @DisplayName("页面允许被平台壳 iframe 嵌入（不能是 X-Frame-Options: DENY）")
    void allowsPlatformFraming() throws Exception {
        // 用接口而不是 /map.html：测试的工作目录是 server/，静态资源根目录
        // （file:./frontend/static/）在这个 cwd 下不存在，取页面会 404。
        // 安全响应头由过滤器统一加，随便挑一个能命中的路径即可。
        MvcResult r = mvc.perform(get("/api/health")).andExpect(status().isOk()).andReturn();
        assertThat(r.getResponse().getHeader("X-Frame-Options")).isNotEqualTo("DENY");
        assertThat(r.getResponse().getHeader("Content-Security-Policy")).contains("frame-ancestors");
    }

    @Test
    @DisplayName("行程接口未登录返回 401，不是 500 也不是空列表")
    void tripsRequireLogin() throws Exception {
        mvc.perform(get("/api/trips")).andExpect(status().isUnauthorized());
    }

    // ---------------------------------------------------------------- 认证

    @Test
    @DisplayName("注册后能拿到 token，并能用它读 /me")
    void registerThenMe() throws Exception {
        String token = register("alice");
        assertThat(token).isNotBlank();
        MvcResult r =
                mvc.perform(get("/api/auth/me").header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();
        assertThat(body(r).get("username")).isEqualTo("alice");
        assertThat(body(r).get("role")).isEqualTo("user");
    }

    @Test
    @DisplayName("Authorization: Bearer 与 X-Auth-Token 两种头都认")
    void bothAuthHeadersWork() throws Exception {
        String token = register("bob");
        mvc.perform(get("/api/auth/me").header("Authorization", "Bearer " + token)).andExpect(status().isOk());
        mvc.perform(get("/api/auth/me").header("X-Auth-Token", token)).andExpect(status().isOk());
    }

    @Test
    @DisplayName("密码错误返回 401，不泄露「用户是否存在」")
    void wrongPasswordIs401() throws Exception {
        register("carol");
        mvc.perform(
                        post("/api/auth/login")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("username", "carol", "password", "wrong-pw"))))
                .andExpect(status().isUnauthorized());
        mvc.perform(
                        post("/api/auth/login")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("username", "no-such-user", "password", "wrong-pw"))))
                .andExpect(status().isUnauthorized());
    }

    // ---------------------------------------------------------------- 行程

    @Test
    @DisplayName("建行程 → 加条目 → 勾选，进度跟着变")
    void tripCrudFlow() throws Exception {
        String token = register("dave");
        String tid = createTrip(token, "北京", 3, 3000);

        MvcResult r =
                mvc.perform(
                                post("/api/trips/" + tid + "/items")
                                        .header("X-Auth-Token", token)
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(json(Map.of("title", "身份证", "day_index", 0, "kind", "doc"))))
                        .andExpect(status().isOk())
                        .andReturn();
        // 加条目的返回是 {"trip": {...}}（不是 {"item": ...}）：前端加完要立刻重渲染整页
        List<?> prep = (List<?>) ((Map<?, ?>) body(r).get("trip")).get("prep");
        long itemId = ((Number) ((Map<?, ?>) prep.get(0)).get("id")).longValue();

        MvcResult patched =
                mvc.perform(
                                patch("/api/trips/" + tid + "/items/" + itemId)
                                        .header("X-Auth-Token", token)
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(json(Map.of("done", true))))
                        .andExpect(status().isOk())
                        .andReturn();
        Map<?, ?> progress = (Map<?, ?>) ((Map<?, ?>) body(patched).get("trip")).get("progress");
        assertThat(((Number) progress.get("done")).intValue()).isEqualTo(1);
        assertThat(((Number) progress.get("percent")).intValue()).isEqualTo(100);

        mvc.perform(delete("/api/trips/" + tid).header("X-Auth-Token", token)).andExpect(status().isOk());
        mvc.perform(get("/api/trips/" + tid).header("X-Auth-Token", token)).andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("别人的行程一律 404，不是 403（不暴露「存在但不是你的」）")
    void otherUsersTripIs404() throws Exception {
        String owner = register("erin");
        String tid = createTrip(owner, "杭州", 2, 0);
        String other = register("frank");
        mvc.perform(get("/api/trips/" + tid).header("X-Auth-Token", other)).andExpect(status().isNotFound());
        mvc.perform(delete("/api/trips/" + tid).header("X-Auth-Token", other)).andExpect(status().isNotFound());
        // 原主人不受影响
        mvc.perform(get("/api/trips/" + tid).header("X-Auth-Token", owner)).andExpect(status().isOk());
    }

    @Test
    @DisplayName("天数越界被 400 拦下，错误信息可读")
    void badDaysIs400() throws Exception {
        String token = register("grace");
        MvcResult r =
                mvc.perform(
                                post("/api/trips")
                                        .header("X-Auth-Token", token)
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(json(Map.of("city", "北京", "days", 0))))
                        .andExpect(status().isBadRequest())
                        .andReturn();
        assertThat(String.valueOf(body(r).get("detail"))).contains("天");
    }

    // ---------------------------------------------------------------- 记账

    @Test
    @DisplayName("记一笔账后，详情里的已花/剩余/百分比一起变")
    void expenseUpdatesBudget() throws Exception {
        String token = register("heidi");
        String tid = createTrip(token, "北京", 3, 3000);

        mvc.perform(
                        post("/api/trips/" + tid + "/expenses")
                                .header("X-Auth-Token", token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("category", "门票", "title", "故宫门票", "amount", 60, "day_index", 1))))
                .andExpect(status().isOk());

        MvcResult r =
                mvc.perform(get("/api/trips/" + tid).header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();
        Map<?, ?> exp = (Map<?, ?>) ((Map<?, ?>) body(r).get("trip")).get("expenses");
        assertThat(((Number) exp.get("spent")).doubleValue()).isEqualTo(60.0);
        assertThat(((Number) exp.get("remaining")).doubleValue()).isEqualTo(2940.0);
        assertThat(((Number) exp.get("percent")).doubleValue()).isEqualTo(2.0);
        // 泛型擦除后 Map<?,?> 的 key 是 capture，containsKey(String) 编译不过，所以显式转一次
        @SuppressWarnings("unchecked")
        Map<String, Object> byCategory = (Map<String, Object>) exp.get("by_category");
        assertThat(byCategory).containsKey("门票");
    }

    @Test
    @DisplayName("分类不在枚举里返回 400，避免出现「吃/吃饭/餐饮」三套口径")
    void unknownCategoryIs400() throws Exception {
        String token = register("ivan");
        String tid = createTrip(token, "北京", 3, 0);
        mvc.perform(
                        post("/api/trips/" + tid + "/expenses")
                                .header("X-Auth-Token", token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("category", "吃饭", "title", "午饭", "amount", 30))))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("预算为 0 时不算百分比（否则会出现「已超支 100%」的误报）")
    void zeroBudgetHasNoPercent() throws Exception {
        String token = register("judy");
        String tid = createTrip(token, "北京", 3, 0);
        mvc.perform(
                        post("/api/trips/" + tid + "/expenses")
                                .header("X-Auth-Token", token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("category", "交通", "title", "地铁", "amount", 10))))
                .andExpect(status().isOk());
        MvcResult r = mvc.perform(get("/api/trips/" + tid).header("X-Auth-Token", token)).andReturn();
        Map<?, ?> exp = (Map<?, ?>) ((Map<?, ?>) body(r).get("trip")).get("expenses");
        assertThat(((Number) exp.get("percent")).doubleValue()).isZero();
        assertThat(((Number) exp.get("remaining")).doubleValue()).isEqualTo(-10.0);
    }

    // ---------------------------------------------------------------- 分享与导出

    @Test
    @DisplayName("分享：生成链接后匿名可读且只读；取消后立即失效")
    void shareIsReadonlyAndRevocable() throws Exception {
        String token = register("ken");
        String tid = createTrip(token, "北京", 2, 1000);
        mvc.perform(
                        post("/api/trips/" + tid + "/items")
                                .header("X-Auth-Token", token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("title", "故宫", "day_index", 1, "kind", "spot"))))
                .andExpect(status().isOk());

        MvcResult r =
                mvc.perform(post("/api/trips/" + tid + "/share").header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();
        String shareToken = (String) body(r).get("share_token");
        assertThat((String) body(r).get("url")).isEqualTo("/s/" + shareToken);

        // 匿名读取
        MvcResult anon = mvc.perform(get("/api/share/" + shareToken)).andExpect(status().isOk()).andReturn();
        Map<?, ?> shared = (Map<?, ?>) body(anon).get("trip");
        assertThat(shared.get("readonly")).isEqualTo(true);
        assertThat((List<?>) shared.get("itinerary")).isNotEmpty();

        // 取消分享后链接失效
        mvc.perform(delete("/api/trips/" + tid + "/share").header("X-Auth-Token", token)).andExpect(status().isOk());
        mvc.perform(get("/api/share/" + shareToken)).andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("/s/{token} 真的转发到分享页，而不是把 \"forward:\" 字符串当响应体吐出去")
    void sharePageForwardsToHtml() throws Exception {
        String token = register("olive");
        String tid = createTrip(token, "北京", 2, 0);
        MvcResult r =
                mvc.perform(post("/api/trips/" + tid + "/share").header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();
        String shareToken = (String) body(r).get("share_token");

        // 回归点：本类是 @RestController，如果 sharePage 直接 return "forward:/share.html"，
        // 这个字符串会被当成响应体写出去（浏览器上只有一行 "forward:/share.html"），
        // forwardedUrl 也会是 null。所以这里必须断言「发生了转发」而不是「返回了 200」。
        mvc.perform(get("/s/" + shareToken))
                .andExpect(status().isOk())
                .andExpect(forwardedUrl("/share.html"));
    }

    @Test
    @DisplayName("/s 与 /s/（无 token）也转发到分享页，而不是吐裸 404 JSON")
    void sharePageWithoutTokenForwardsToHtml() throws Exception {
        // 回归点：{token} 变量不匹配空段，/s 落不到上面的映射时会走默认错误页，
        // 用户看到的是 {"detail":"Not Found"} 裸 JSON —— 没有页面、没有样式、没有人话。
        // 修法是补 /s 与 /s/ 两条 forward 映射，让页面自己的「链接不完整」分支接管；
        // 这里沿用上一条用例的口径：断言「发生了转发」而不是「返回了 200」。
        mvc.perform(get("/s")).andExpect(status().isOk()).andExpect(forwardedUrl("/share.html"));
        mvc.perform(get("/s/")).andExpect(status().isOk()).andExpect(forwardedUrl("/share.html"));
    }

    @Test
    @DisplayName("分享 token 猜不到：不是自增也不是行程 id")
    void shareTokenIsNotGuessable() throws Exception {        String token = register("laura");
        String tid = createTrip(token, "北京", 2, 0);
        MvcResult r = mvc.perform(post("/api/trips/" + tid + "/share").header("X-Auth-Token", token)).andReturn();
        String shareToken = (String) body(r).get("share_token");
        assertThat(shareToken).isNotEqualTo(tid).hasSizeGreaterThanOrEqualTo(16);
    }

    @Test
    @DisplayName("导出 .ics：Content-Type 是 text/calendar，内容是合法 VCALENDAR")
    void exportIcs() throws Exception {
        String token = register("mike");
        String tid = createTrip(token, "北京", 2, 0);
        mvc.perform(
                        post("/api/trips/" + tid + "/items")
                                .header("X-Auth-Token", token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("title", "故宫", "day_index", 1, "slot", "上午", "kind", "spot"))))
                .andExpect(status().isOk());

        MvcResult r =
                mvc.perform(get("/api/trips/" + tid + "/export/ics").header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();
        assertThat(r.getResponse().getContentType()).contains("text/calendar");
        String ics = r.getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(ics).contains("BEGIN:VCALENDAR").contains("END:VCALENDAR").contains("故宫");
        assertThat(r.getResponse().getHeader("Content-Disposition")).contains(".ics");
    }

    @Test
    @DisplayName("导出打印版：返回 HTML，带标题与每天的小节")
    void exportPrintableHtml() throws Exception {
        String token = register("nina");
        String tid = createTrip(token, "北京", 2, 0);
        mvc.perform(
                        post("/api/trips/" + tid + "/items")
                                .header("X-Auth-Token", token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("title", "故宫", "day_index", 1, "kind", "spot"))))
                .andExpect(status().isOk());
        MvcResult r =
                mvc.perform(get("/api/trips/" + tid + "/export/print").header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();
        assertThat(r.getResponse().getContentType()).contains("text/html");
        String html = r.getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(html).contains("北京").contains("故宫").contains("<h2>第 1 天</h2>");
    }

    @Test
    @DisplayName("导出别人的行程 404，不会把别人的行程单导出去")
    void exportOtherUsersTripIs404() throws Exception {
        String owner = register("oscar");
        String tid = createTrip(owner, "北京", 2, 0);
        String other = register("peggy");
        mvc.perform(get("/api/trips/" + tid + "/export/ics").header("X-Auth-Token", other))
                .andExpect(status().isNotFound());
        mvc.perform(get("/api/trips/" + tid + "/export/print").header("X-Auth-Token", other))
                .andExpect(status().isNotFound());
    }

    // ---------------------------------------------------------------- 模板

    @Test
    @DisplayName("模板列表公开可读，套用后行程里有对应天数的安排")
    void templateListAndApply() throws Exception {
        MvcResult list = mvc.perform(get("/api/templates")).andExpect(status().isOk()).andReturn();
        assertThat((List<?>) body(list).get("templates")).hasSize(4);

        String token = register("quinn");
        String tid = createTrip(token, "北京", 4, 0);
        MvcResult applied =
                mvc.perform(post("/api/trips/" + tid + "/templates/classic").header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();
        assertThat(((Number) body(applied).get("items")).intValue()).isGreaterThan(0);

        MvcResult detail = mvc.perform(get("/api/trips/" + tid).header("X-Auth-Token", token)).andReturn();
        List<?> itinerary = (List<?>) ((Map<?, ?>) body(detail).get("trip")).get("itinerary");
        assertThat(itinerary).hasSize(4); // 4 天各有安排
    }

    @Test
    @DisplayName("套用未知模板返回 400，不是 500")
    void unknownTemplateIs400() throws Exception {
        String token = register("rose");
        String tid = createTrip(token, "北京", 3, 0);
        mvc.perform(post("/api/trips/" + tid + "/templates/nope").header("X-Auth-Token", token))
                .andExpect(status().isBadRequest());
    }

    // ---------------------------------------------------------------- AI 降级

    @Test
    @DisplayName("AI 服务连不上时，生成行程返回 400 且提示可手动添加，不 500")
    void aiDownDegradesGracefully() throws Exception {
        String token = register("sam");
        String tid = createTrip(token, "北京", 2, 0);
        MvcResult r =
                mvc.perform(post("/api/trips/" + tid + "/plan").header("X-Auth-Token", token))
                        .andExpect(status().isBadRequest())
                        .andReturn();
        assertThat(String.valueOf(body(r).get("detail"))).isNotBlank();
        // 降级后行程本身仍然可读可写
        mvc.perform(get("/api/trips/" + tid).header("X-Auth-Token", token)).andExpect(status().isOk());
    }

    @Test
    @DisplayName("改密后旧 token 立即失效，接口同时返回一个新 token 让当前设备不掉线")
    void changePasswordKicksOldToken() throws Exception {
        String token = register("tina");
        MvcResult r =
                mvc.perform(
                                post("/api/auth/change-password")
                                        .header("X-Auth-Token", token)
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(json(Map.of("old_password", "pw123456", "new_password", "pw654321"))))
                        .andExpect(status().isOk())
                        .andReturn();

        // 旧 token 立刻失效（用会话世代而不是时间戳，所以不需要等一秒）
        mvc.perform(get("/api/auth/me").header("X-Auth-Token", token)).andExpect(status().isUnauthorized());

        // 改密接口给的新 token 可用
        String fresh = (String) body(r).get("token");
        assertThat(fresh).isNotBlank().isNotEqualTo(token);
        mvc.perform(get("/api/auth/me").header("X-Auth-Token", fresh)).andExpect(status().isOk());

        // 新密码能登录，旧密码不能
        mvc.perform(
                        post("/api/auth/login")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("username", "tina", "password", "pw123456"))))
                .andExpect(status().isUnauthorized());
        mvc.perform(
                        post("/api/auth/login")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("username", "tina", "password", "pw654321"))))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("原密码不对时改密失败，且旧 token 仍然可用（不能把人误踢下线）")
    void wrongOldPasswordDoesNotKick() throws Exception {
        String token = register("ursula");
        mvc.perform(
                        post("/api/auth/change-password")
                                .header("X-Auth-Token", token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("old_password", "not-my-password", "new_password", "pw654321"))))
                .andExpect(status().isBadRequest());
        mvc.perform(get("/api/auth/me").header("X-Auth-Token", token)).andExpect(status().isOk());
    }

    // ---------------------------------------------------------------- 示例行程

    @SuppressWarnings("unchecked")
    private List<String> sampleTitles(Map<String, Object> trip) {
        List<Map<String, Object>> days = (List<Map<String, Object>>) trip.get("itinerary");
        return days.stream()
                .flatMap(d -> ((List<Map<String, Object>>) d.get("items")).stream())
                .map(i -> String.valueOf(i.get("title")))
                .toList();
    }

    @Test
    @DisplayName("载入示例行程：一次建完，条目里是地图数据里的真实景点名")
    void sampleTripHasRealSpots() throws Exception {
        String token = register("samuel");
        MvcResult r =
                mvc.perform(
                                post("/api/trips/sample")
                                        .header("X-Auth-Token", token)
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(json(Map.of("city", "北京"))))
                        .andExpect(status().isOk())
                        .andReturn();

        Map<String, Object> b = body(r);
        assertThat(b.get("reused")).isEqualTo(false);
        Map<String, Object> trip = (Map<String, Object>) b.get("trip");
        assertThat(trip.get("city")).isEqualTo("北京");
        assertThat(String.valueOf(trip.get("title"))).contains("示例行程");
        assertThat(trip.get("days")).isEqualTo(3);

        // 空骨架（「核心景点（提前预约）」）不算通过 —— 示例行程的价值就在于景点名是真的
        List<String> titles = sampleTitles(trip);
        assertThat(titles).hasSizeGreaterThanOrEqualTo(8);
        assertThat(titles).contains("故宫博物院", "抵达 + 酒店寄存行李", "返程");

        // 花费也要有，否则预算面板是空的，演示时看着像没做
        Map<String, Object> expenses = (Map<String, Object>) trip.get("expenses");
        assertThat(expenses.get("spent")).isNotNull();
        assertThat(expenses.get("spent").toString()).startsWith("280");
    }

    @Test
    @DisplayName("重复载入返回同一份，不会堆出十几份示例行程")
    void sampleTripIsIdempotent() throws Exception {
        String token = register("samuel2");
        MvcResult first =
                mvc.perform(post("/api/trips/sample").header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();
        MvcResult second =
                mvc.perform(post("/api/trips/sample").header("X-Auth-Token", token))
                        .andExpect(status().isOk())
                        .andReturn();

        assertThat(body(second).get("reused")).isEqualTo(true);
        assertThat(((Map<?, ?>) body(second).get("trip")).get("id"))
                .isEqualTo(((Map<?, ?>) body(first).get("trip")).get("id"));

        MvcResult list = mvc.perform(get("/api/trips").header("X-Auth-Token", token)).andExpect(status().isOk()).andReturn();
        assertThat((List<?>) body(list).get("trips")).hasSize(1);
    }

    @Test
    @DisplayName("没有地图数据的城市明确报错，不生成一份空行程")
    void sampleTripRejectsUnknownCity() throws Exception {
        String token = register("samuel3");
        mvc.perform(
                        post("/api/trips/sample")
                                .header("X-Auth-Token", token)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json(Map.of("city", "不存在的城市"))))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("示例行程也要登录，不能匿名往别人库里写")
    void sampleTripRequiresLogin() throws Exception {
        mvc.perform(post("/api/trips/sample")).andExpect(status().isUnauthorized());
    }
}
