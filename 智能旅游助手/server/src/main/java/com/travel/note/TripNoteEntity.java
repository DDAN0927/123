package com.travel.note;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;
import java.time.Instant;

/**
 * 游记（任务书 1(3) 要求的「游记表」）。
 *
 * <p>游记挂在行程上而不是独立成篇：用户写游记的入口就是「这趟行程结束了，回顾一下」，
 * 独立成篇要先选城市再选日期，写完还得自己想标题——比直接在行程里写多三步。
 *
 * <p>{@code images} 存逗号分隔的相对地址（{@code /api/uploads/xxx.jpg}），
 * 不存二进制：图片进数据库会让备份从几百 KB 变成几百 MB，而且每次读都要过一遍 JDBC。
 * 图片文件落在 {@code $DATA_DIR/uploads}，与数据库一起被持久化卷带着走。
 */
@Entity
@Table(name = "trip_notes", indexes = {@Index(name = "idx_note_trip", columnList = "tripId,createdAt")})
public class TripNoteEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 32)
    private String tripId;

    @Column(nullable = false, length = 40)
    private String username;

    @Column(nullable = false, length = 80)
    private String title;

    /** 正文。用 Lob 而不是 varchar(8000)：一篇游记配几张图后很容易过万字符。 */
    @Lob
    @Column(nullable = false)
    private String content;

    /** 逗号分隔的图片地址。 */
    @Column(length = 1000)
    private String images;

    @Column(nullable = false)
    private Instant createdAt = Instant.now();

    @Column(nullable = false)
    private Instant updatedAt = Instant.now();

    protected TripNoteEntity() {}

    public TripNoteEntity(String tripId, String username, String title, String content) {
        this.tripId = tripId;
        this.username = username;
        this.title = title;
        this.content = content;
    }

    public void touch() {
        this.updatedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getTripId() {
        return tripId;
    }

    public String getUsername() {
        return username;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public String getImages() {
        return images;
    }

    public void setImages(String images) {
        this.images = images;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
