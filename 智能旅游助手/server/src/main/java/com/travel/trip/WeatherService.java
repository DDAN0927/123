package com.travel.trip;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.travel.config.AppProperties;
import com.travel.trip.TripDtos.WeatherRow;
import java.time.Duration;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/**
 * 行程期间天气：open-meteo（免费、无需 Key）。
 *
 * <p>坐标来自 {@link CityGeoService}（即地图那份 355 城数据），所以覆盖范围从原来
 * Python 侧硬编码的 20 城扩到 355 城。查不到坐标的城市明确返回 supported=false，
 * 不做假数据 —— 编一个温度比说「查不到」更糟。
 *
 * <p>窗口：open-meteo 只给未来 16 天，超出范围的行程由调用方退化为季节估算。
 */
@Service
public class WeatherService {

    private static final Logger log = LoggerFactory.getLogger(WeatherService.class);

    private static final Map<Integer, String> WMO = new LinkedHashMap<>();

    static {
        WMO.put(0, "晴");
        WMO.put(1, "大致晴朗");
        WMO.put(2, "多云");
        WMO.put(3, "阴");
        WMO.put(45, "有雾");
        WMO.put(48, "雾凇");
        WMO.put(51, "小毛毛雨");
        WMO.put(53, "毛毛雨");
        WMO.put(55, "大毛毛雨");
        WMO.put(61, "小雨");
        WMO.put(63, "中雨");
        WMO.put(65, "大雨");
        WMO.put(66, "冻雨");
        WMO.put(67, "强冻雨");
        WMO.put(71, "小雪");
        WMO.put(73, "中雪");
        WMO.put(75, "大雪");
        WMO.put(77, "雪粒");
        WMO.put(80, "小阵雨");
        WMO.put(81, "阵雨");
        WMO.put(82, "强阵雨");
        WMO.put(85, "小阵雪");
        WMO.put(86, "阵雪");
        WMO.put(95, "雷阵雨");
        WMO.put(96, "雷阵雨伴冰雹");
        WMO.put(99, "强雷阵雨伴冰雹");
    }

    private final CityGeoService geo;
    private final AppProperties props;
    private final ObjectMapper mapper = new ObjectMapper();
    private final RestClient client;

    public WeatherService(CityGeoService geo, AppProperties props) {
        this.geo = geo;
        this.props = props;
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        Duration timeout = Duration.ofSeconds(props.weather().timeoutSeconds());
        f.setConnectTimeout((int) timeout.toMillis());
        f.setReadTimeout((int) timeout.toMillis());
        this.client = RestClient.builder().requestFactory(f).build();
    }

    public String condition(int code) {
        return WMO.getOrDefault(code, "未知天气");
    }

    /** 取行程期间的预报；坐标缺失或网络失败都返回空列表（调用方据此降级）。 */
    public List<WeatherRow> forecast(String city, int days, LocalDate startDate) {
        Optional<double[]> center = geo.center(city);
        if (center.isEmpty()) {
            return List.of();
        }
        double lat = center.get()[0];
        double lon = center.get()[1];
        String url =
                props.weather().baseUrl()
                        + "?latitude=" + lat
                        + "&longitude=" + lon
                        + "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
                        + "precipitation_probability_max,wind_speed_10m_max"
                        + "&timezone=auto&forecast_days=16";
        try {
            String body = client.get().uri(url).retrieve().body(String.class);
            JsonNode daily = mapper.readTree(body).path("daily");
            JsonNode dates = daily.path("time");
            List<WeatherRow> rows = new ArrayList<>();
            for (int i = 0; i < dates.size(); i++) {
                String date = dates.get(i).asText();
                if (startDate != null && date.compareTo(startDate.toString()) < 0) {
                    continue;
                }
                int code = daily.path("weather_code").get(i).asInt();
                rows.add(
                        new WeatherRow(
                                date,
                                (int) Math.round(daily.path("temperature_2m_min").get(i).asDouble()),
                                (int) Math.round(daily.path("temperature_2m_max").get(i).asDouble()),
                                code,
                                condition(code),
                                daily.path("precipitation_probability_max").get(i).isNull()
                                        ? null
                                        : daily.path("precipitation_probability_max").get(i).asInt(),
                                (int) Math.round(daily.path("wind_speed_10m_max").get(i).asDouble())));
            }
            int limit = Math.max(1, Math.min(days, 16));
            return rows.size() > limit ? rows.subList(0, limit) : rows;
        } catch (Exception e) {
            log.warn("天气查询失败（{}）：{}", city, e.getMessage());
            return List.of();
        }
    }

    /** 把预报压成几条能直接执行的建议（穿衣 / 雨具 / 防晒 / 大风）。 */
    public List<String> advice(List<WeatherRow> rows) {
        if (rows.isEmpty()) {
            return List.of();
        }
        int hi = rows.stream().mapToInt(WeatherRow::tmax).max().orElse(0);
        int lo = rows.stream().mapToInt(WeatherRow::tmin).min().orElse(0);
        int wet = rows.stream().mapToInt(r -> r.precip() == null ? 0 : r.precip()).max().orElse(0);
        int windy = rows.stream().mapToInt(r -> r.wind() == null ? 0 : r.wind()).max().orElse(0);

        List<String> out = new ArrayList<>();
        if (hi - lo >= 12) {
            out.add("行程期间温差达 " + (hi - lo) + "℃，早晚要加一件外套（" + lo + "~" + hi + "℃）");
        } else if (lo <= 5) {
            out.add("最低 " + lo + "℃，需要厚外套或羽绒，注意保暖");
        } else if (hi >= 30) {
            out.add("最高 " + hi + "℃，注意防暑补水，避开正午长时间户外");
        } else {
            out.add("气温 " + lo + "~" + hi + "℃，常规春秋装即可");
        }
        if (wet >= 50) {
            out.add("降水概率最高 " + wet + "%，务必带伞，户外行程留一个备选方案");
        } else if (wet >= 30) {
            out.add("可能有阵雨（最高 " + wet + "%），带把折叠伞更稳妥");
        }
        if (hi >= 28) {
            out.add("紫外线较强，防晒霜、帽子、太阳镜建议备齐");
        }
        if (windy >= 30) {
            out.add("最大风速 " + windy + "km/h，高空项目、索道、游船可能临时停运，出发前确认");
        }
        List<String> rainDays =
                rows.stream().filter(r -> r.precip() != null && r.precip() >= 60).map(WeatherRow::date).toList();
        if (!rainDays.isEmpty()) {
            out.add("高概率降雨日：" + String.join("、", rainDays) + "，可考虑安排室内景点");
        }
        return out;
    }
}
