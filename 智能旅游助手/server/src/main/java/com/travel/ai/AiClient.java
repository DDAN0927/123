package com.travel.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.travel.common.BizException;
import com.travel.config.AppProperties;
import com.travel.trip.TripDtos.ItemView;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/**
 * 调用 Python AI 能力服务（RAG + 多 Agent 编排）。
 *
 * <p>为什么不让 SpringBoot 自己调大模型：检索增强与多智能体协作的编排（LangGraph）
 * 已经在一个服务里成型，重写一遍既慢又容易把指标做坏。业务与 AI 分开后，
 * AI 侧可以独立换模型、独立扩容，SpringBoot 也不必背上向量检索这类重型依赖。
 *
 * <p>安全：内网调用带 {@code X-Internal-Secret}，Python 侧只在密钥匹配时才信任
 * {@code X-User-Name}。这样 AI 服务不对外暴露鉴权逻辑，也不会被外部伪造身份。
 */
@Service
public class AiClient {

    private static final Logger log = LoggerFactory.getLogger(AiClient.class);

    /** 模型返回的单条安排。 */
    public record PlanItem(int day, String slot, String kind, String title, String note) {}

    private final AppProperties props;
    private final ObjectMapper mapper = new ObjectMapper();
    private final RestClient client;

    public AiClient(AppProperties props) {
        this.props = props;
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        Duration timeout = Duration.ofSeconds(props.ai().timeoutSeconds());
        f.setConnectTimeout(5_000);
        f.setReadTimeout((int) timeout.toMillis());
        this.client = RestClient.builder().requestFactory(f).build();
    }

    public List<PlanItem> plan(String city, int days, int budget) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("city", city);
        body.put("days", days);
        body.put("budget", budget);
        return post("/api/ai/plan", body);
    }

    public List<PlanItem> revise(String city, int days, String instruction, List<ItemView> current) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (ItemView it : current) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("day", it.dayIndex());
            m.put("slot", it.slot());
            m.put("kind", it.kind());
            m.put("title", it.title());
            m.put("note", it.note());
            items.add(m);
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("city", city);
        body.put("days", days);
        body.put("instruction", instruction);
        body.put("items", items);
        return post("/api/ai/revise", body);
    }

    private List<PlanItem> post(String path, Map<String, Object> body) {
        String url = props.ai().baseUrl() + path;
        try {
            String resp =
                    client.post()
                            .uri(url)
                            .header("X-Internal-Secret", props.ai().internalSecret())
                            .contentType(MediaType.APPLICATION_JSON)
                            .body(body)
                            .retrieve()
                            .body(String.class);
            JsonNode root = mapper.readTree(resp);
            List<PlanItem> out = new ArrayList<>();
            for (JsonNode n : root.path("items")) {
                out.add(
                        new PlanItem(
                                n.path("day").asInt(1),
                                n.path("slot").asText(""),
                                n.path("kind").asText("spot"),
                                n.path("title").asText(""),
                                n.path("note").asText("")));
            }
            if (out.isEmpty()) {
                throw BizException.badRequest("AI 服务没有返回可用安排，请稍后重试或手动添加");
            }
            return out;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.warn("调用 AI 服务失败 {}：{}", url, e.getMessage());
            throw BizException.badRequest("AI 服务暂时不可用（" + e.getClass().getSimpleName() + "），可先手动添加条目");
        }
    }
}
