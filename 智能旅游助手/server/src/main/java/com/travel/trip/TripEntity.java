package com.travel.trip;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "trips", indexes = {@Index(name = "idx_trips_user", columnList = "username")})
public class TripEntity {

    /** 12 位十六进制，与旧 Python 版本保持一致（前端会把它拼进 URL）。 */
    @Id
    @Column(length = 32)
    private String id;

    @Column(nullable = false, length = 40)
    private String username;

    @Column(nullable = false, length = 40)
    private String city;

    @Column(nullable = false, length = 80)
    private String title;

    private LocalDate startDate;

    @Column(nullable = false)
    private int days = 3;

    /** 人均预算（元）。0 表示未设置。 */
    @Column(nullable = false)
    private int budget;

    @Column(length = 500)
    private String note;

    /** 分享令牌：非空即可通过 /api/share/{token} 只读访问；随时可作废。 */
    @Column(unique = true, length = 40)
    private String shareToken;

    @Column(nullable = false)
    private Instant createdAt = Instant.now();

    @Column(nullable = false)
    private Instant updatedAt = Instant.now();

    protected TripEntity() {}

    public TripEntity(String id, String username, String city, String title) {
        this.id = id;
        this.username = username;
        this.city = city;
        this.title = title;
    }

    public String getId() {
        return id;
    }

    public String getUsername() {
        return username;
    }

    public String getCity() {
        return city;
    }

    public void setCity(String city) {
        this.city = city;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public LocalDate getStartDate() {
        return startDate;
    }

    public void setStartDate(LocalDate startDate) {
        this.startDate = startDate;
    }

    public int getDays() {
        return days;
    }

    public void setDays(int days) {
        this.days = days;
    }

    public int getBudget() {
        return budget;
    }

    public void setBudget(int budget) {
        this.budget = budget;
    }

    public String getNote() {
        return note;
    }

    public void setNote(String note) {
        this.note = note;
    }

    public String getShareToken() {
        return shareToken;
    }

    public void setShareToken(String shareToken) {
        this.shareToken = shareToken;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void touch() {
        this.updatedAt = Instant.now();
    }
}
