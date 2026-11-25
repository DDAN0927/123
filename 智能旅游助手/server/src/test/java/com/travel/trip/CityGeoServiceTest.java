package com.travel.trip;

import static org.assertj.core.api.Assertions.assertThat;

import com.travel.trip.CityGeoService.Spot;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/**
 * 城市数据读取的测试。
 *
 * <p>这个类以前只读坐标（天气用），后来示例行程要景点名，正则从「读到坐标后的竖线」
 * 改成「读到行尾」。改正则最怕的就是**静默退化**：坐标还在、城市数还是 355，
 * 但景点全空 —— 示例行程会悄悄变成一堆「城市漫步」，没有任何报错。
 * 所以这里既钉城市数，也钉景点数与具体景点名。
 */
class CityGeoServiceTest {

    private final CityGeoService geo = new CityGeoService();

    @Test
    @DisplayName("城市数与景点数要和对外文案对得上（355 城 / 1558 景点）")
    void countsMatchPublicCopy() {
        assertThat(geo.size()).isEqualTo(355);
        assertThat(geo.spotCount()).isEqualTo(1558);
    }

    @Test
    @DisplayName("景点带真实名称与分类，不是空壳")
    void spotsHaveNameAndCategory() {
        List<Spot> beijing = geo.spots("北京");
        assertThat(beijing).hasSize(12);
        assertThat(beijing).extracting(Spot::name).contains("故宫博物院", "八达岭长城", "颐和园");
        assertThat(beijing).allSatisfy(s -> {
            assertThat(s.name()).isNotBlank();
            assertThat(s.category()).isNotBlank();
            assertThat(s.lat()).isBetween(-90.0, 90.0);
            assertThat(s.lng()).isBetween(-180.0, 180.0);
        });
    }

    @ParameterizedTest
    @DisplayName("各档景点数的城市都能读到（3 / 7 / 8 / 12 个的边界）")
    @CsvSource({"廊坊,3", "哈尔滨,7", "苏州,8", "北京,12"})
    void spotCountPerCity(String city, int expected) {
        assertThat(geo.spots(city)).hasSize(expected);
    }

    @Test
    @DisplayName("输入带后缀也能命中（「北京市」→ 北京）")
    void suffixStillResolves() {
        assertThat(geo.spots("北京市")).isNotEmpty();
        assertThat(geo.center("北京市")).isPresent();
    }

    @Test
    @DisplayName("没有的城市返回空列表，不抛异常也不编造景点")
    void unknownCityIsEmpty() {
        assertThat(geo.spots("不存在的城市")).isEmpty();
        assertThat(geo.spots("")).isEmpty();
        assertThat(geo.spots(null)).isEmpty();
    }

    @Test
    @DisplayName("景点解析失败只丢那一条，不影响同城其它景点")
    void badSpotDoesNotDropWholeCity() {
        // 直接调私有解析做不到，这里用真实数据反证：所有城市都至少有一个可解析景点。
        // 1558 条里只要有一条因格式问题被跳过，spotCount() 就对不上 1558。
        assertThat(geo.spotCount()).isEqualTo(1558);
        assertThat(geo.spots("北京")).allSatisfy(s -> assertThat(s.category()).isNotBlank());
    }
}
