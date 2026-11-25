package com.travel.trip;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/** 行程相关的请求与响应体。字段名统一走全局 SNAKE_CASE，前端拿到的就是 day_index / start_date。 */
public final class TripDtos {

    private TripDtos() {}

    // ---------------------------------------------------------------- 请求

    public record CreateReq(
            @NotBlank(message = "目的地不能为空") @Size(max = 40) String city,
            String startDate,
            @Min(value = 1, message = "至少 1 天") @Max(value = 30, message = "最多 30 天") Integer days,
            @Min(value = 0, message = "预算不能为负") Integer budget,
            @Size(max = 80) String title,
            @Size(max = 500) String note) {}

    /** 部分更新：只改传进来的字段（null = 不改）。 */
    public record UpdateReq(
            @Size(max = 40) String city,
            String startDate,
            @Min(1) @Max(30) Integer days,
            @Min(0) Integer budget,
            @Size(max = 80) String title,
            @Size(max = 500) String note) {}

    public record ItemCreateReq(
            @NotBlank(message = "内容不能为空") @Size(max = 120) String title,
            @Min(0) @Max(30) Integer dayIndex,
            @Size(max = 20) String slot,
            String kind,
            @Size(max = 500) String note) {}

    public record ItemUpdateReq(@Size(max = 120) String title, @Size(max = 500) String note, @Size(max = 20) String slot, Boolean done) {}

    public record ExpenseCreateReq(
            @NotBlank(message = "分类不能为空") String category,
            @NotBlank(message = "说明不能为空") @Size(max = 120) String title,
            @NotNull(message = "金额不能为空") BigDecimal amount,
            @Min(0) @Max(30) Integer dayIndex,
            String spentOn) {}

    public record ExpenseUpdateReq(String category, @Size(max = 120) String title, BigDecimal amount, Integer dayIndex, String spentOn) {}

    /** 自然语言改行程，例如「第三天想去室内，下雨了」。 */
    public record ReviseReq(@NotBlank(message = "请说明要改什么") @Size(max = 200) String instruction) {}

    public record TemplateApplyReq(String city) {}

    /** 示例行程：城市与天数都可省略，默认北京 3 天。 */
    public record SampleReq(@Size(max = 40) String city, @Min(1) @Max(7) Integer days) {}

    // ---------------------------------------------------------------- 响应

    public record ItemView(Long id, int dayIndex, String slot, String kind, String title, String note, boolean done) {}

    public record DayView(int day, List<ItemView> items) {}

    public record ProgressView(int done, int total, int percent) {}

    public record ExpenseView(Long id, String category, String title, BigDecimal amount, int dayIndex, String spentOn) {}

    /** 预算执行情况：总额、已花、剩余、按分类与按天的分布。 */
    public record BudgetView(
            int budget, BigDecimal spent, BigDecimal remaining, double percent, Map<String, BigDecimal> byCategory, List<Map<String, Object>> byDay) {}

    public record TripView(
            String id,
            String city,
            String title,
            String startDate,
            int days,
            int budget,
            String note,
            Integer countdown,
            String phase,
            ProgressView progress,
            List<ItemView> prep,
            List<DayView> itinerary,
            String shareToken,
            BudgetView expenses,
            boolean readonly,
            /**
             * 排期冲突提示（任务书 2(2)）：同天同时段撞车、超出天数、同日重复、单日过满。
             *
             * <p>只提示不拦截：用户有时就是想上午去两个挨着的景点，
             * 强行 400 会让人反复试错才找到「系统允许的写法」。
             */
            List<String> conflicts) {}

    public record WeatherRow(String date, int tmin, int tmax, int code, String cond, Integer precip, Integer wind) {}

    public record WeatherView(boolean supported, String reason, String source, List<WeatherRow> rows, List<String> advice) {}

    public record PackingView(String source, List<Map<String, Object>> groups, List<WeatherRow> weather, List<String> advice) {}

    public record ShareView(String shareToken, String url) {}
}
