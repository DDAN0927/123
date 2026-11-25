package com.travel.stats;

import java.math.BigDecimal;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * 跨表统计（MyBatis-Plus，任务书 2(1)）。
 *
 * <p>为什么这两条查询不走 JPA：它们要的是「按城市分组后左连接汇总」，
 * 用 JPQL 也能写，但 {@code left join ... on ... group by} 加上空值兜底之后，
 * 可读性远不如一句 SQL。SQL 写在这里，改起来不用重新理解实体关系。
 *
 * <p>SQL 在 {@code resources/mapper/CityStatsMapper.xml}。
 */
@Mapper
public interface CityStatsMapper {

    /** 当前用户每个城市的行程数与总花费（没有花费的行程也要出现，所以是 left join）。 */
    List<CityStat> statsByCity(@Param("username") String username);

    /** 当前用户按「城市 + 分类」的花费分布，用于跨行程的花费对比。 */
    List<CategoryStat> statsByCategory(@Param("username") String username);

    record CityStat(String city, Integer tripCount, Integer dayCount, BigDecimal totalAmount, Integer itemCount) {}

    record CategoryStat(String city, String category, BigDecimal amount, Integer tripCount) {}
}
