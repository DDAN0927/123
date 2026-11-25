package com.travel.trip;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.travel.ai.AiClient.PlanItem;
import com.travel.common.BizException;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * 模板库展开的测试。
 *
 * <p>展开逻辑看着简单，但最容易出「明显不合理」的排法：2 天行程里出现第三天，
 * 或者最后一天还在「抵达」。这几条断言就是在钉这个边界。
 */
class TripTemplateServiceTest {

    private final TripTemplateService service = new TripTemplateService();

    @Test
    @DisplayName("1 天只有抵达日，没有返程也没有中间日")
    void oneDayIsArrivalOnly() {
        List<PlanItem> items = service.expand("classic", 1);
        assertThat(items).isNotEmpty();
        assertThat(items).allMatch(i -> i.day() == 1);
        assertThat(items).noneMatch(i -> i.title().contains("返程"));
    }

    @Test
    @DisplayName("2 天 = 抵达 + 返程，中间日不出现")
    void twoDaysIsArrivalPlusDeparture() {
        List<PlanItem> items = service.expand("classic", 2);
        assertThat(items.stream().map(PlanItem::day).distinct()).containsExactly(1, 2);
        assertThat(items.stream().filter(i -> i.day() == 2)).anyMatch(i -> i.title().contains("返程"));
    }

    @Test
    @DisplayName("4 天：中间日按模板循环，不会空着")
    void middleDaysCycle() {
        List<PlanItem> items = service.expand("classic", 4);
        assertThat(items.stream().map(PlanItem::day).distinct()).containsExactly(1, 2, 3, 4);
        // 每天至少 2 项，否则「中间那天」等于没排
        for (int day = 1; day <= 4; day++) {
            int d = day;
            assertThat(items.stream().filter(i -> i.day() == d).count()).isGreaterThanOrEqualTo(2);
        }
    }

    @Test
    @DisplayName("长行程也不越界：30 天全部有安排")
    void longTripCoversEveryDay() {
        List<PlanItem> items = service.expand("photo", 30);
        assertThat(items.stream().map(PlanItem::day).distinct()).hasSize(30);
        assertThat(items).allMatch(i -> i.day() >= 1 && i.day() <= 30);
    }

    @ParameterizedTest
    @ValueSource(strings = {"classic", "family", "photo", "food"})
    @DisplayName("每套模板都能展开，且每天都有时段与类型")
    void everyTemplateExpands(String key) {
        List<PlanItem> items = service.expand(key, 5);
        assertThat(items).isNotEmpty();
        assertThat(items).allMatch(i -> !i.slot().isBlank() && !i.kind().isBlank() && !i.title().isBlank());
    }

    @Test
    @DisplayName("未知模板报 400，不是 500")
    void unknownTemplateIsBadRequest() {
        assertThatThrownBy(() -> service.expand("nope", 3))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("没有这个模板");
    }

    @Test
    @DisplayName("天数越界被夹紧：0 天按 1 天，负数也一样")
    void daysAreClamped() {
        assertThat(service.expand("classic", 0).stream().map(PlanItem::day).distinct()).containsExactly(1);
        assertThat(service.expand("classic", -5).stream().map(PlanItem::day).distinct()).containsExactly(1);
    }

    @Test
    @DisplayName("模板列表带 key/name/description，前端卡片能直接用")
    void templatesAreListable() {
        assertThat(service.all()).hasSize(4);
        assertThat(service.all())
                .allMatch(t -> !t.key().isBlank() && !t.name().isBlank() && !t.description().isBlank());
    }
}
