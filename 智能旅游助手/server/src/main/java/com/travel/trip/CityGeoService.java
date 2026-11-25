package com.travel.trip;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * 城市坐标：直接读前端地图用的 {@code geo-data.js}，不另建一份城市表。
 *
 * <p>为什么值得这么绕：项目里已经有两套城市数据（地图 355 城、攻略库 6 城），
 * 再加第三份「后端城市坐标表」迟早会打架 —— 加了新城市忘了同步，天气就查不到。
 * 前端那份是唯一事实来源，后端只读它。
 *
 * <p>顺带的收益：天气覆盖从原来硬编码的 20 城扩到 355 城。
 */
@Service
public class CityGeoService {

    private static final Logger log = LoggerFactory.getLogger(CityGeoService.class);

    /** 城市|拼音首字母|纬度,经度|景点... */
    private static final Pattern ROW =
            Pattern.compile("\"([^\"|\\\\]+)\\|([^|]*)\\|(-?\\d+(?:\\.\\d+)?),(-?\\d+(?:\\.\\d+)?)\\|([^\"]*)\"");

    /** 前端那份数据的相对路径。第二个候选是给 `mvn test` / 从 server/ 启动时用的。 */
    private static final String[] CANDIDATES = {
        "frontend/static/assets/js/geo-data.js", "../frontend/static/assets/js/geo-data.js"
    };

    private final Map<String, double[]> centers = new LinkedHashMap<>();

    /** 城市 → 景点列表。景点名与分类都是地图数据里的真实值，不是模型生成的。 */
    private final Map<String, List<Spot>> spots = new LinkedHashMap<>();

    /**
     * 一个景点。
     *
     * <p>{@code category} 取值见 {@code geo-data.js}：地标 / 古迹 / 公园 / 街区 / 商圈 /
     * 自然 / 乐园 / 亲子 / 体验 / 场馆 / 美食。示例行程靠它决定这一条算景点还是算吃饭。
     */
    public record Spot(String name, double lat, double lng, String category) {}

    public CityGeoService() {
        for (String cand : CANDIDATES) {
            Path p = Path.of(cand);
            if (Files.exists(p)) {
                load(p);
                return;
            }
        }
        // 一个都没找到也要能起来：天气与装备会退化为季节估算，不该让整个应用起不来
        log.warn("未找到城市坐标数据 {}，天气与装备将退化为季节估算", String.join(" / ", CANDIDATES));
    }

    private void load(Path file) {
        if (!Files.exists(file)) {
            log.warn("未找到城市坐标数据 {}，天气与装备将退化为季节估算", file);
            return;
        }
        try {
            String text = Files.readString(file, StandardCharsets.UTF_8);
            Matcher m = ROW.matcher(text);
            while (m.find()) {
                String city = m.group(1);
                centers.put(city, new double[] {Double.parseDouble(m.group(3)), Double.parseDouble(m.group(4))});
                spots.put(city, parseSpots(m.group(5)));
            }
            int spotCount = spots.values().stream().mapToInt(List::size).sum();
            log.info("已载入 {} 个城市坐标、{} 个景点（来源：geo-data.js）", centers.size(), spotCount);
        } catch (IOException e) {
            log.warn("城市坐标读取失败：{}", e.getMessage());
        }
    }

    /**
     * 解析「景点名,纬度,经度,分类」用 {@code |} 分隔的串。
     *
     * <p>单条脏数据只丢那一条，不让整座城市的景点全没：地图数据是人手维护的，
     * 漏个逗号就整城消失，这种失败方式在线上极难发现（示例行程会静默退化成通用占位）。
     */
    private List<Spot> parseSpots(String raw) {
        if (raw == null || raw.isBlank()) {
            return List.of();
        }
        List<Spot> out = new ArrayList<>();
        for (String seg : raw.split("\\|")) {
            String[] f = seg.split(",");
            if (f.length < 4) {
                continue;
            }
            try {
                out.add(new Spot(f[0].trim(), Double.parseDouble(f[1]), Double.parseDouble(f[2]), f[3].trim()));
            } catch (NumberFormatException ignored) {
                log.debug("跳过无法解析的景点：{}", seg);
            }
        }
        return out;
    }

    public int size() {
        return centers.size();
    }

    /**
     * 精确名 → 包含匹配（最长优先，避免「鞍山」命中「马鞍山」）。
     *
     * <p>返回命中的**键**而不是坐标：坐标和景点都要按同一个键取，两处各写一遍
     * 匹配逻辑迟早会出现「坐标取到了 A 城、景点取到了 B 城」。
     */
    private Optional<String> resolve(String city) {
        String name = city == null ? "" : city.trim();
        if (name.isEmpty()) {
            return Optional.empty();
        }
        if (centers.containsKey(name)) {
            return Optional.of(name);
        }
        Map<Integer, String> hits = new HashMap<>();
        centers.keySet()
                .forEach(
                        key -> {
                            if (name.contains(key)) {
                                hits.put(key.length(), key);
                            }
                        });
        return hits.isEmpty()
                ? Optional.empty()
                : Optional.of(hits.get(hits.keySet().stream().max(Integer::compare).orElse(0)));
    }

    public Optional<double[]> center(String city) {
        return resolve(city).map(centers::get);
    }

    /** 该城市的景点（真实名称与分类，来自地图数据）。城市不存在或没有景点时返回空列表。 */
    public List<Spot> spots(String city) {
        return resolve(city).map(k -> spots.getOrDefault(k, List.<Spot>of())).orElse(List.of());
    }

    /**
     * 全部城市的景点总数。
     *
     * <p>对外文案写的是「355 城 / 1558 个景点」，这个数字必须能被反算出来 ——
     * 前端改数据、后端读错一行，文案就开始骗人。测试拿它和文案对账。
     */
    public int spotCount() {
        return spots.values().stream().mapToInt(List::size).sum();
    }

    public boolean contains(String city) {
        return resolve(city).isPresent();
    }
}
