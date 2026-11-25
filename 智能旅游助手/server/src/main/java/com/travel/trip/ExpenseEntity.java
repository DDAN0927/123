package com.travel.trip;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

/**
 * 一笔花费。
 *
 * <p>金额用 {@link BigDecimal}（列精度 10,2）而不是 double：
 * 记账场景里 {@code 0.1 + 0.2 != 0.3} 会被用户当成 bug，虽然只是浮点误差。
 */
@Entity
@Table(name = "trip_expenses", indexes = {@Index(name = "idx_exp_trip", columnList = "tripId,spentOn")})
public class ExpenseEntity {

    /** 分类固定这几项：自由输入最后会得到「吃」「吃饭」「餐饮」三个分类，统计就没意义了。 */
    public static final java.util.List<String> CATEGORIES =
            java.util.List.of("交通", "住宿", "餐饮", "门票", "购物", "其他");

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 32)
    private String tripId;

    @Column(nullable = false, length = 20)
    private String category = "其他";

    @Column(nullable = false, length = 120)
    private String title;

    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal amount;

    /** 记在哪一天；0 表示行前支出（机票、酒店预付这类）。 */
    @Column(nullable = false)
    private int dayIndex;

    private LocalDate spentOn;

    @Column(nullable = false)
    private Instant createdAt = Instant.now();

    protected ExpenseEntity() {}

    public ExpenseEntity(String tripId, String category, String title, BigDecimal amount, int dayIndex) {
        this.tripId = tripId;
        this.category = category;
        this.title = title;
        this.amount = amount;
        this.dayIndex = dayIndex;
    }

    public Long getId() {
        return id;
    }

    public String getTripId() {
        return tripId;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public void setAmount(BigDecimal amount) {
        this.amount = amount;
    }

    public int getDayIndex() {
        return dayIndex;
    }

    public void setDayIndex(int dayIndex) {
        this.dayIndex = dayIndex;
    }

    public LocalDate getSpentOn() {
        return spentOn;
    }

    public void setSpentOn(LocalDate spentOn) {
        this.spentOn = spentOn;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
