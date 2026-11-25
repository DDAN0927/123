package com.travel.spot;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.util.List;

/** 景点模块的请求 / 响应体。字段名同样走全局 SNAKE_CASE。 */
public final class SpotDtos {

    private SpotDtos() {}

    public record SpotView(
            Long id,
            String city,
            String name,
            String category,
            List<String> tags,
            BigDecimal ticketPrice,
            Integer suggestMinutes,
            String address,
            Double lng,
            Double lat,
            String rating,
            String openTime,
            String source,
            /** 仅在「推荐」接口里有值：与用户偏好标签的命中数。 */
            Integer matchCount) {}

    public record UpsertReq(
            @NotBlank(message = "城市不能为空") @Size(max = 40) String city,
            @NotBlank(message = "景点名不能为空") @Size(max = 120) String name,
            @Size(max = 20) String category,
            List<String> tags,
            @Min(value = 0, message = "门票不能为负") BigDecimal ticketPrice,
            @Min(value = 5, message = "建议时长至少 5 分钟") @Max(value = 1440, message = "建议时长最多 1440 分钟")
                    Integer suggestMinutes,
            @Size(max = 200) String address,
            Double lng,
            Double lat,
            @Size(max = 10) String rating,
            @Size(max = 40) String openTime) {}

    public record PageView(List<SpotView> items, long total, int page, int size) {}

    /** 筛选面板用：分类、标签、城市清单与总量。 */
    public record MetaView(List<String> categories, List<String> tags, List<String> cities, long total) {}

    public record PreferenceReq(@Size(max = 8, message = "最多选 8 个偏好") List<String> tags) {}
}
