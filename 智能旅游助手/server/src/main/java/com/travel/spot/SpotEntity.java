package com.travel.spot;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * 景点（任务书 1(3) 要求的「景点表」）。
 *
 * <p>为什么单独建表而不是继续用前端常量 / 攻略 Markdown：攻略正文是给 RAG 检索用的长文本，
 * 它回答不了「杭州有哪些免费的室内景点，两小时能逛完」——这类条件检索需要结构化字段。
 * 两者分工：{@code spots} 负责筛选，{@code knowledge_base/} 负责讲清楚这个地方值不值得去。
 *
 * <p>{@code tags} 用逗号分隔的短标签而不是关联表：标签是展示与匹配用的，不需要按标签建索引，
 * 一张 {@code spot_tags} 关联表会让「查一个景点」变成两次 join，收益不抵成本。
 * 代价是标签不能改名——真需要改名时写一条 UPDATE ... REPLACE 就够了。
 */
@Entity
@Table(
        name = "spots",
        indexes = {@Index(name = "idx_spot_city", columnList = "city"), @Index(name = "idx_spot_category", columnList = "category")},
        uniqueConstraints = {@UniqueConstraint(name = "uk_spot_city_name", columnNames = {"city", "name"})})
public class SpotEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 40)
    private String city;

    @Column(nullable = false, length = 120)
    private String name;

    /** 自然 / 人文 / 场馆 / 街区 / 亲子 / 地标 / 美食 —— 与高德快照的 k 字段对齐。 */
    @Column(length = 20)
    private String category;

    /** 逗号分隔：场馆,室内,免费,亲子。匹配推荐与筛选都读它。 */
    @Column(length = 200)
    private String tags;

    /**
     * 门票价（元）。{@code null} = 未录入，不是 0。
     *
     * <p>把「没查到」写成 0 会让「免费景点」筛选结果里混进收费景点，
     * 用户按免费筛出来到门口才发现要买票，比不提供这个筛选更糟。
     */
    @Column(precision = 10, scale = 2)
    private BigDecimal ticketPrice;

    /** 建议游玩时长（分钟）。 */
    private Integer suggestMinutes;

    @Column(length = 200)
    private String address;

    private Double lng;

    private Double lat;

    /** 平台评分（字符串，保留「4.5」这种一位小数原样）。 */
    @Column(length = 10)
    private String rating;

    @Column(length = 40)
    private String openTime;

    /** 数据来源：amap（快照导入）/ manual（后台录入）。 */
    @Column(nullable = false, length = 20)
    private String source = "manual";

    @Column(nullable = false)
    private Instant createdAt = Instant.now();

    protected SpotEntity() {}

    public SpotEntity(String city, String name, String category) {
        this.city = city;
        this.name = name;
        this.category = category;
    }

    public Long getId() {
        return id;
    }

    public String getCity() {
        return city;
    }

    public void setCity(String city) {
        this.city = city;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getTags() {
        return tags;
    }

    public void setTags(String tags) {
        this.tags = tags;
    }

    public BigDecimal getTicketPrice() {
        return ticketPrice;
    }

    public void setTicketPrice(BigDecimal ticketPrice) {
        this.ticketPrice = ticketPrice;
    }

    public Integer getSuggestMinutes() {
        return suggestMinutes;
    }

    public void setSuggestMinutes(Integer suggestMinutes) {
        this.suggestMinutes = suggestMinutes;
    }

    public String getAddress() {
        return address;
    }

    public void setAddress(String address) {
        this.address = address;
    }

    public Double getLng() {
        return lng;
    }

    public void setLng(Double lng) {
        this.lng = lng;
    }

    public Double getLat() {
        return lat;
    }

    public void setLat(Double lat) {
        this.lat = lat;
    }

    public String getRating() {
        return rating;
    }

    public void setRating(String rating) {
        this.rating = rating;
    }

    public String getOpenTime() {
        return openTime;
    }

    public void setOpenTime(String openTime) {
        this.openTime = openTime;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
