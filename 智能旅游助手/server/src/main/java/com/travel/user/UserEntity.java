package com.travel.user;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "users")
public class UserEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 40)
    private String username;

    /** BCrypt 哈希，永不返回给前端（见 {@link UserEntity#toView()}）。 */
    @Column(nullable = false, length = 100)
    private String passwordHash;

    @Column(nullable = false, length = 16)
    private String role = "user";

    @Column(nullable = false)
    private Instant createdAt = Instant.now();

    /**
     * 最近一次改密时间。仅作审计展示。
     *
     * @deprecated 不要再用它判断 token 是否有效：JWT 的 {@code iat} 只有秒级精度，
     *     同一秒内改密 + 签发的 token 会永远躲过比对（等于泄露的 token 永久有效）。
     *     改用 {@link #getTokenEpoch()}。
     */
    @Deprecated
    private Instant passwordChangedAt;

    /**
     * 会话世代：改密时 +1，token 里带着签发那一刻的世代，对不上即失效。
     *
     * <p>为什么不用时间戳：JWT 的 {@code iat} 只到秒，而「改密」与「改密后登录」
     * 常常落在同一秒。用时间比较就不得不再留一个容差窗口，而那个窗口正好是漏洞。
     * 世代是个整数，相等就是相等，没有精度问题。
     *
     * <p>用包装类型而不是 {@code long}：老库里的用户行没有这一列，
     * {@code ddl-auto: update} 给非空表加 NOT NULL 列会失败。null 一律当 0 处理。
     */
    private Long tokenEpoch;

    /**
     * 偏好标签，逗号分隔（如「亲子,室内,免费」）。
     *
     * <p>不建关联表：偏好是「用户身上的一小撮短词」，读的时候永远跟着用户一起读，
     * 拆表只会多一次 join。用可空字符串而不是 NOT NULL：老库里的用户行没有这一列，
     * 给非空表加 NOT NULL 列会让 {@code ddl-auto: update} 直接失败。
     */
    @Column(length = 200)
    private String preferenceTags;

    protected UserEntity() {}

    public UserEntity(String username, String passwordHash, String role) {
        this.username = username;
        this.passwordHash = passwordHash;
        this.role = role;
        this.createdAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getUsername() {
        return username;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getPasswordChangedAt() {
        return passwordChangedAt;
    }

    public void setPasswordChangedAt(Instant passwordChangedAt) {
        this.passwordChangedAt = passwordChangedAt;
    }

    public String getPreferenceTags() {
        return preferenceTags;
    }

    public void setPreferenceTags(String preferenceTags) {
        this.preferenceTags = preferenceTags;
    }

    /** 当前会话世代；老数据没有该字段时按 0 处理。 */
    public long epoch() {
        return tokenEpoch == null ? 0L : tokenEpoch;
    }

    /** 改密时调用：让此前签发的所有 token 立即失效。 */
    public void bumpTokenEpoch() {
        this.tokenEpoch = epoch() + 1;
    }
}
