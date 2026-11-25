package com.travel.spot;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.InputStream;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * 景点库种子导入。
 *
 * <p>三个约束决定了它长这样：
 * <ol>
 *   <li><b>不能阻塞启动</b>：8274 条批量插入在 1 核容器上要几十秒，而平台判活只看端口。
 *       放在 {@link ApplicationReadyEvent} 的守护线程里，网站先能用，景点库随后填满。</li>
 *   <li><b>用 JdbcTemplate 而不是 JPA</b>：主键是 IDENTITY，Hibernate 只能逐条 insert
 *       且每条都要回读主键；批量 500 条一起发，快一个数量级。</li>
 *   <li><b>只在空表时导入</b>：重复导入会把管理员手工改过的门票、时长覆盖掉。</li>
 * </ol>
 */
@Component
public class SpotSeeder {

    private static final Logger log = LoggerFactory.getLogger(SpotSeeder.class);
    private static final String SEED = "seed/spots.json";

    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final ObjectMapper json;

    /** 测试里关掉：8274 条批量插入会让每个 @SpringBootTest 多花 20 秒。 */
    @org.springframework.beans.factory.annotation.Value("${app.seed-spots:true}")
    private boolean enabled;

    public SpotSeeder(JdbcTemplate jdbc, TransactionTemplate tx, ObjectMapper json) {
        this.jdbc = jdbc;
        this.tx = tx;
        this.json = json;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void onReady() {
        if (!enabled) {
            return;
        }
        Thread t = new Thread(this::seedIfEmpty, "spot-seeder");
        t.setDaemon(true);
        t.start();
    }

    void seedIfEmpty() {
        try {
            Long count = jdbc.queryForObject("select count(*) from spots", Long.class);
            if (count != null && count > 0) {
                log.info("景点库已有 {} 条，跳过种子导入", count);
                return;
            }
            Map<String, List<List<Object>>> data;
            try (InputStream in = new ClassPathResource(SEED).getInputStream()) {
                data = json.readValue(in, new TypeReference<Map<String, List<List<Object>>>>() {});
            }
            long start = System.currentTimeMillis();
            Integer inserted = tx.execute(status -> insertAll(data));
            log.info("景点库种子导入完成：{} 条 / {} 城，耗时 {} ms", inserted, data.size(), System.currentTimeMillis() - start);
        } catch (Exception e) {
            // 导入失败不能让主流程挂掉：景点库为空时页面显示「暂无数据」，其余功能照常
            log.warn("景点库种子导入失败：{}", e.toString());
        }
    }

    private Integer insertAll(Map<String, List<List<Object>>> data) {
        String sql =
                "insert into spots (city, name, category, tags, ticket_price, suggest_minutes, address, lng, lat, rating, open_time, source, created_at)"
                        + " values (?,?,?,?,?,?,?,?,?,?,?,?,?)";
        List<Object[]> args = new ArrayList<>();
        Timestamp now = Timestamp.from(Instant.now());
        for (Map.Entry<String, List<List<Object>>> e : data.entrySet()) {
            String city = e.getKey();
            List<Object> seen = new ArrayList<>();
            for (List<Object> r : e.getValue()) {
                String name = str(r, 0);
                if (name.isEmpty() || seen.contains(name)) {
                    continue;
                }
                seen.add(name);
                String category = str(r, 1).isEmpty() ? "地标" : str(r, 1);
                // 街区（步行街 / 历史街区）没有闸机，门票恒为 0；其余分类的门票快照里没有，
                // 留 null 表示「未录入」，交给管理员在后台补——不猜，猜错了用户到门口才发现
                java.math.BigDecimal ticket = "街区".equals(category) ? java.math.BigDecimal.ZERO : null;
                args.add(new Object[] {
                    city,
                    name,
                    category,
                    SpotTags.join(SpotTags.derive(category, name, ticket)),
                    ticket,
                    SpotTags.suggestMinutes(category),
                    emptyToNull(str(r, 4)),
                    dbl(r, 2),
                    dbl(r, 3),
                    emptyToNull(str(r, 5)),
                    normalizeOpenTime(str(r, 6)),
                    "amap",
                    now
                });
            }
        }
        int[] res = jdbc.batchUpdate(sql, args);
        return res.length;
    }

    private static String str(List<Object> r, int i) {
        if (r.size() <= i || r.get(i) == null) {
            return "";
        }
        return String.valueOf(r.get(i)).trim();
    }

    private static String emptyToNull(String v) {
        return v.isEmpty() ? null : v;
    }

    /**
     * 高德的 open_time 是「多个时段用空格拼起来」的，最长见过 131 字符
     * （{@code 08:30-18:00 07:30-19:00 08:30-18:30 …}）。直接入库会撑爆 VARCHAR(40)。
     *
     * <p>只保留第一段：这一段的含义是「旺季工作日」的开放时间，对游客足够，
     * 全部塞进来在卡片上会折成三行还读不出重点。
     */
    private static String normalizeOpenTime(String v) {
        if (v == null || v.isEmpty()) {
            return null;
        }
        String s = v.trim();
        if (s.length() <= 40) {
            return s;
        }
        int i = s.indexOf(' ');
        String first = i > 0 ? s.substring(0, i) : s;
        return first.length() <= 40 ? first : first.substring(0, 40);
    }

    private static Double dbl(List<Object> r, int i) {
        if (r.size() <= i || r.get(i) == null) {
            return null;
        }
        try {
            return Double.valueOf(String.valueOf(r.get(i)));
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
