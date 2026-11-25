package com.travel.trip;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

/**
 * 行程条目。一张表两种语义：
 * <ul>
 *   <li>{@code dayIndex = 0} —— 行前清单（能打勾、可随时增减）；</li>
 *   <li>{@code dayIndex = 1..N} —— 第 N 天的安排。</li>
 * </ul>
 * 用同一个字段区分而不是开两张表：行前清单和行程条目都要「勾选 / 改标题 / 删一条」，
 * 两套表就是两套接口。
 */
@Entity
@Table(name = "trip_items", indexes = {@Index(name = "idx_items_trip", columnList = "tripId,dayIndex,sort")})
public class TripItemEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 32)
    private String tripId;

    @Column(nullable = false)
    private int dayIndex;

    /** 行前清单里当「分组名」用（证件/衣物/电子…），行程里当「上午/下午」用。 */
    @Column(length = 20)
    private String slot;

    @Column(nullable = false, length = 20)
    private String kind = "spot";

    @Column(nullable = false, length = 120)
    private String title;

    @Column(length = 500)
    private String note;

    @Column(nullable = false)
    private boolean done;

    @Column(nullable = false)
    private int sort;

    protected TripItemEntity() {}

    public TripItemEntity(String tripId, int dayIndex, String slot, String kind, String title, int sort) {
        this.tripId = tripId;
        this.dayIndex = dayIndex;
        this.slot = slot;
        this.kind = kind;
        this.title = title;
        this.sort = sort;
    }

    public Long getId() {
        return id;
    }

    public String getTripId() {
        return tripId;
    }

    public int getDayIndex() {
        return dayIndex;
    }

    public void setDayIndex(int dayIndex) {
        this.dayIndex = dayIndex;
    }

    public String getSlot() {
        return slot;
    }

    public void setSlot(String slot) {
        this.slot = slot;
    }

    public String getKind() {
        return kind;
    }

    public void setKind(String kind) {
        this.kind = kind;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getNote() {
        return note;
    }

    public void setNote(String note) {
        this.note = note;
    }

    public boolean isDone() {
        return done;
    }

    public void setDone(boolean done) {
        this.done = done;
    }

    public int getSort() {
        return sort;
    }

    public void setSort(int sort) {
        this.sort = sort;
    }
}
