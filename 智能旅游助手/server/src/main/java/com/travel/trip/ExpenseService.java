package com.travel.trip;

import com.travel.common.BizException;
import com.travel.trip.TripDtos.BudgetView;
import com.travel.trip.TripDtos.ExpenseCreateReq;
import com.travel.trip.TripDtos.ExpenseUpdateReq;
import com.travel.trip.TripDtos.ExpenseView;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 预算记账。
 *
 * <p>记账的价值不在「记」，在「随时知道还剩多少」：所以每次返回行程详情都带上
 * {@link BudgetView}，而不是让前端再发一个请求。
 *
 * <p>分类是固定枚举（交通/住宿/餐饮/门票/购物/其他）。开放自由输入的话，
 * 一周后就会出现「吃」「吃饭」「餐饮」三个分类，统计页直接失去意义。
 */
@Service
public class ExpenseService {

    private final ExpenseRepository expenses;
    private final TripRepository trips;

    public ExpenseService(ExpenseRepository expenses, TripRepository trips) {
        this.expenses = expenses;
        this.trips = trips;
    }

    @Transactional(readOnly = true)
    public List<ExpenseView> list(String username, String tripId) {
        requireTrip(tripId, username);
        return expenses.findByTripIdOrderByDayIndexAscIdAsc(tripId).stream()
                .map(e -> new ExpenseView(e.getId(), e.getCategory(), e.getTitle(), e.getAmount(), e.getDayIndex(),
                        e.getSpentOn() == null ? null : e.getSpentOn().toString()))
                .toList();
    }

    @Transactional
    public ExpenseView add(String username, String tripId, ExpenseCreateReq req) {
        TripEntity trip = requireTrip(tripId, username);
        ExpenseEntity e = new ExpenseEntity(tripId, category(req.category()), TripService.trim(req.title(), 120),
                money(req.amount()), clampDay(req.dayIndex(), trip.getDays()));
        e.setSpentOn(TripService.parseDate(req.spentOn(), true));
        ExpenseEntity saved = expenses.save(e);
        trip.touch();
        trips.save(trip);
        return new ExpenseView(saved.getId(), saved.getCategory(), saved.getTitle(), saved.getAmount(),
                saved.getDayIndex(), saved.getSpentOn() == null ? null : saved.getSpentOn().toString());
    }

    @Transactional
    public ExpenseView update(String username, String tripId, Long id, ExpenseUpdateReq req) {
        requireTrip(tripId, username);
        ExpenseEntity e = expenses.findByIdAndTripId(id, tripId).orElseThrow(() -> BizException.notFound("这笔记录不存在"));
        if (req.category() != null) {
            e.setCategory(category(req.category()));
        }
        if (req.title() != null && !req.title().isBlank()) {
            e.setTitle(TripService.trim(req.title(), 120));
        }
        if (req.amount() != null) {
            e.setAmount(money(req.amount()));
        }
        if (req.dayIndex() != null) {
            e.setDayIndex(clampDay(req.dayIndex(), 30));
        }
        if (req.spentOn() != null) {
            e.setSpentOn(TripService.parseDate(req.spentOn(), true));
        }
        ExpenseEntity saved = expenses.save(e);
        return new ExpenseView(saved.getId(), saved.getCategory(), saved.getTitle(), saved.getAmount(),
                saved.getDayIndex(), saved.getSpentOn() == null ? null : saved.getSpentOn().toString());
    }

    @Transactional
    public void delete(String username, String tripId, Long id) {
        requireTrip(tripId, username);
        ExpenseEntity e = expenses.findByIdAndTripId(id, tripId).orElseThrow(() -> BizException.notFound("这笔记录不存在"));
        expenses.delete(e);
    }

    /** 预算执行情况。预算为 0（未设置）时不计算百分比，避免除零与「已超支 100%」的误报。 */
    @Transactional(readOnly = true)
    public BudgetView budget(String tripId, int budget) {
        List<ExpenseEntity> all = expenses.findByTripIdOrderByDayIndexAscIdAsc(tripId);
        BigDecimal spent = all.stream().map(ExpenseEntity::getAmount).reduce(BigDecimal.ZERO, BigDecimal::add);

        Map<String, BigDecimal> byCategory = new LinkedHashMap<>();
        for (String c : ExpenseEntity.CATEGORIES) {
            byCategory.put(c, BigDecimal.ZERO);
        }
        for (ExpenseEntity e : all) {
            byCategory.merge(e.getCategory(), e.getAmount(), BigDecimal::add);
        }
        byCategory.values().removeIf(v -> v.compareTo(BigDecimal.ZERO) == 0);

        Map<Integer, BigDecimal> daySum = new LinkedHashMap<>();
        for (ExpenseEntity e : all) {
            daySum.merge(e.getDayIndex(), e.getAmount(), BigDecimal::add);
        }
        List<Map<String, Object>> byDay = new ArrayList<>();
        daySum.forEach((day, amount) -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("day", day);
            m.put("amount", amount);
            byDay.add(m);
        });

        BigDecimal remaining = BigDecimal.valueOf(budget).subtract(spent);
        double percent = budget <= 0 ? 0 : spent.multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(budget), 1, RoundingMode.HALF_UP).doubleValue();
        return new BudgetView(budget, spent.setScale(2, RoundingMode.HALF_UP),
                remaining.setScale(2, RoundingMode.HALF_UP), percent, byCategory, byDay);
    }

    private TripEntity requireTrip(String tripId, String username) {
        return trips.findByIdAndUsername(tripId, username)
                .orElseThrow(() -> BizException.notFound("行程不存在或无权访问"));
    }

    private String category(String raw) {
        String c = raw == null ? "" : raw.trim();
        if (!ExpenseEntity.CATEGORIES.contains(c)) {
            throw BizException.badRequest("分类需为：" + String.join(" / ", ExpenseEntity.CATEGORIES));
        }
        return c;
    }

    private BigDecimal money(BigDecimal amount) {
        if (amount == null || amount.signum() < 0) {
            throw BizException.badRequest("金额不能为负");
        }
        if (amount.compareTo(BigDecimal.valueOf(1_000_000)) > 0) {
            throw BizException.badRequest("单笔金额过大，请检查是否输错");
        }
        return amount.setScale(2, RoundingMode.HALF_UP);
    }

    private int clampDay(Integer day, int days) {
        int d = day == null ? 0 : day;
        return Math.max(0, Math.min(d, Math.max(days, 1)));
    }

    /** 供测试与导出复用：按日期分组时的默认日期（行程未填日期时用今天）。 */
    static LocalDate defaultDate(LocalDate start, int dayIndex) {
        LocalDate base = start == null ? LocalDate.now() : start;
        return dayIndex <= 0 ? base.minusDays(1) : base.plusDays(dayIndex - 1L);
    }
}
