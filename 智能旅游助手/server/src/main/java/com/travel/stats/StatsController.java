package com.travel.stats;

import com.travel.security.CurrentUser;
import com.travel.stats.CityStatsMapper.CategoryStat;
import com.travel.stats.CityStatsMapper.CityStat;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 跨行程统计（MyBatis-Plus 多表关联查询的落地接口）。
 *
 * <p>与 {@code /api/trips/{id}} 里那份预算汇总的区别：那份只回答「这一趟花了多少」，
 * 这份回答「我这些年/这几次旅行，钱都花在哪些城市、哪些类目上」。
 */
@RestController
@RequestMapping("/api/stats")
public class StatsController {

    private final CityStatsMapper mapper;
    private final CurrentUser currentUser;

    public StatsController(CityStatsMapper mapper, CurrentUser currentUser) {
        this.mapper = mapper;
        this.currentUser = currentUser;
    }

    @GetMapping("/cities")
    public Map<String, Object> cities() {
        List<CityStat> rows = mapper.statsByCity(currentUser.username());
        return Map.of("cities", rows, "total", rows.size());
    }

    @GetMapping("/categories")
    public Map<String, Object> categories() {
        List<CategoryStat> rows = mapper.statsByCategory(currentUser.username());
        return Map.of("rows", rows, "total", rows.size());
    }
}
