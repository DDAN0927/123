package com.travel.trip;

import static org.assertj.core.api.Assertions.assertThat;

import com.travel.trip.TripDtos.WeatherRow;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 装备清单分档测试。
 *
 * <p>分错档等于给错建议：让去三亚的人带羽绒服，或者让去哈尔滨的人只带薄外套。
 * 所以温度分档、纬度修正、海滨/高原专项都要钉住。
 */
class PackingServiceTest {

    private final PackingService service = new PackingService(new CityGeoService());

    private static WeatherRow row(int tmin, int tmax, Integer precip) {
        return new WeatherRow("2026-11-01", tmin, tmax, 0, "晴", precip, 10);
    }

    private static String allItems(List<Map<String, Object>> groups) {
        StringBuilder sb = new StringBuilder();
        for (Map<String, Object> g : groups) {
            sb.append(g.get("group")).append('\n');
            for (Object it : (List<?>) g.get("items")) {
                sb.append(it).append('\n');
            }
        }
        return sb.toString();
    }

    // ---------------------------------------------------------------- 分档

    @Test
    @DisplayName("有预报时按最高温分档，边界值不越档")
    void bandFollowsForecast() {
        assertThat(service.band(0, 1, 45.0)).isEqualTo("severe_cold");
        assertThat(service.band(10, 1, 45.0)).isEqualTo("cold");
        assertThat(service.band(20, 4, 30.0)).isEqualTo("cool");
        assertThat(service.band(28, 4, 30.0)).isEqualTo("mild");
        assertThat(service.band(29, 7, 30.0)).isEqualTo("hot");
    }

    @Test
    @DisplayName("没有预报时按月份 + 纬度估算，北方同月低一档")
    void bandFallsBackToSeasonAndLatitude() {
        assertThat(service.band(null, 1, 45.0)).isEqualTo("severe_cold"); // 1 月哈尔滨
        assertThat(service.band(null, 1, 30.0)).isEqualTo("cold"); // 1 月杭州
        assertThat(service.band(null, 7, 45.0)).isEqualTo("hot");
        assertThat(service.band(null, 10, 45.0)).isEqualTo("cool");
        assertThat(service.band(null, 10, 30.0)).isEqualTo("mild");
    }

    @Test
    @DisplayName("纬度未知时按南方的较暖档处理，不能崩")
    void bandWithoutLatitude() {
        assertThat(service.band(null, 1, null)).isEqualTo("cold");
        assertThat(service.band(null, 10, null)).isEqualTo("mild");
    }

    // ---------------------------------------------------------------- 清单内容

    @Test
    @DisplayName("高温目的地不会出现羽绒服，且带防晒")
    void hotDestinationHasNoDownJacket() {
        List<Map<String, Object>> groups =
                service.build("三亚", 3, LocalDate.of(2026, 7, 10), List.of(row(27, 33, 10)));
        String items = allItems(groups);
        assertThat(items).doesNotContain("羽绒服");
        assertThat(items).contains("防晒");
        assertThat(items).contains("泳衣"); // 海滨专项
    }

    @Test
    @DisplayName("严寒目的地要羽绒服、手套、暖宝宝")
    void coldDestinationHasWinterGear() {
        List<Map<String, Object>> groups =
                service.build("哈尔滨", 3, LocalDate.of(2026, 1, 10), List.of(row(-18, -5, 0)));
        String items = allItems(groups);
        assertThat(items).contains("羽绒服").contains("手套").contains("暖宝宝");
        assertThat(items).doesNotContain("泳衣");
    }

    @Test
    @DisplayName("高原目的地加防晒与氧气")
    void plateauDestinationHasExtraItems() {
        String items = allItems(service.build("拉萨", 3, LocalDate.of(2026, 8, 1), List.of(row(12, 22, 10))));
        assertThat(items).contains("高倍防晒").contains("便携氧气");
    }

    @Test
    @DisplayName("降水概率高才提示雨具，低于 40% 不吓人")
    void rainAdviceDependsOnProbability() {
        String wet = allItems(service.build("杭州", 3, LocalDate.of(2026, 4, 1), List.of(row(12, 20, 60))));
        String dry = allItems(service.build("杭州", 3, LocalDate.of(2026, 4, 1), List.of(row(12, 20, 5))));
        assertThat(wet).contains("雨具").contains("防水鞋套");
        assertThat(dry).doesNotContain("防水鞋套");
    }

    @Test
    @DisplayName("没有预报时明确写「按季节估算」，不做假精确")
    void noForecastIsLabelledAsEstimate() {
        List<Map<String, Object>> groups = service.build("北京", 3, LocalDate.of(2026, 11, 1), List.of());
        String items = allItems(groups);
        assertThat(items).contains("估算");
        assertThat(items).contains("出发前 3 天请再看一次天气");
    }

    @Test
    @DisplayName("换洗套数按天数算，但最多 5 套（再多也洗得上）")
    void washCountIsCapped() {
        assertThat(allItems(service.build("北京", 3, LocalDate.of(2026, 11, 1), List.of())))
                .contains("换洗内衣袜子 3 套");
        assertThat(allItems(service.build("北京", 10, LocalDate.of(2026, 11, 1), List.of())))
                .contains("换洗内衣袜子 5 套");
    }

    @Test
    @DisplayName("5 天以上加折叠行李袋")
    void longTripGetsExtraBag() {
        assertThat(allItems(service.build("北京", 6, LocalDate.of(2026, 11, 1), List.of()))).contains("折叠行李袋");
        assertThat(allItems(service.build("北京", 3, LocalDate.of(2026, 11, 1), List.of()))).doesNotContain("折叠行李袋");
    }

    @Test
    @DisplayName("分组顺序固定：证件在最前，预订在最后")
    void groupOrderIsStable() {
        List<Map<String, Object>> groups = service.build("北京", 3, LocalDate.of(2026, 11, 1), List.of());
        assertThat(groups.get(0).get("group")).isEqualTo("证件与票据");
        assertThat(groups.get(groups.size() - 1).get("group")).isEqualTo("说明");
        assertThat(groups.stream().map(g -> g.get("group")))
                .contains("衣物与鞋", "电子设备", "洗护与药品", "行前预订");
    }
}
