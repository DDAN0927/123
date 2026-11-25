package com.travel.trip;

import com.travel.security.CurrentUser;
import com.travel.trip.TripDtos.ExpenseCreateReq;
import com.travel.trip.TripDtos.ExpenseUpdateReq;
import com.travel.trip.TripDtos.ExpenseView;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 预算记账接口：CRUD + 汇总。汇总也挂在行程详情里，这里单独给一个便于刷新。 */
@RestController
@RequestMapping("/api/trips/{tripId}/expenses")
public class ExpenseController {

    private final ExpenseService expenses;
    private final TripService trips;
    private final CurrentUser currentUser;

    public ExpenseController(ExpenseService expenses, TripService trips, CurrentUser currentUser) {
        this.expenses = expenses;
        this.trips = trips;
        this.currentUser = currentUser;
    }

    @GetMapping
    public Map<String, Object> list(@PathVariable String tripId) {
        String user = currentUser.username();
        List<ExpenseView> items = expenses.list(user, tripId);
        var trip = trips.get(user, tripId);
        return Map.of("expenses", items, "summary", trip.expenses());
    }

    @PostMapping
    public Map<String, Object> add(@PathVariable String tripId, @Valid @RequestBody ExpenseCreateReq req) {
        ExpenseView item = expenses.add(currentUser.username(), tripId, req);
        return Map.of("expense", item, "summary", trips.get(currentUser.username(), tripId).expenses());
    }

    @PatchMapping("/{id}")
    public Map<String, Object> update(@PathVariable String tripId, @PathVariable Long id, @RequestBody ExpenseUpdateReq req) {
        ExpenseView item = expenses.update(currentUser.username(), tripId, id, req);
        return Map.of("expense", item, "summary", trips.get(currentUser.username(), tripId).expenses());
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable String tripId, @PathVariable Long id) {
        expenses.delete(currentUser.username(), tripId, id);
        return Map.of("ok", true, "summary", trips.get(currentUser.username(), tripId).expenses());
    }

    /** 分类候选，前端下拉框直接用，避免两边各写一份。 */
    @GetMapping("/categories")
    public Map<String, Object> categories() {
        return Map.of("categories", ExpenseEntity.CATEGORIES);
    }
}
