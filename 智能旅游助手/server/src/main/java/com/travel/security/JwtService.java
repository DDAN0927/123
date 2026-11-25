package com.travel.security;

import com.travel.config.AppProperties;
import com.travel.config.SecretGuard;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import javax.crypto.SecretKey;
import org.springframework.stereotype.Service;

/**
 * JWT 签发与校验（HS256）。
 *
 * <p>为什么用 JWT 而不是把 token 存内存字典：原 Python 服务的 token 存在进程内 dict 里，
 * 重启即全部失效、也无法多实例。JWT 自带过期时间与角色声明，服务重启不影响已登录用户。
 *
 * <p>密钥长度必须 ≥ 32 字节（HS256 要求），配置里给的默认值就是按这个长度写的。
 */
@Service
public class JwtService {

    private final SecretKey key;
    private final long ttlSeconds;

    public JwtService(AppProperties props) {
        // 校验与报错文案统一在 SecretGuard：为空 / 等于历史默认值 / 短于 32 字节都会
        // 让启动直接失败，而不是用一把可猜的密钥把站点跑起来。
        byte[] raw = SecretGuard.requireJwtSecret(props.jwt().secret()).getBytes(StandardCharsets.UTF_8);
        this.key = Keys.hmacShaKeyFor(raw);
        this.ttlSeconds = props.jwt().ttlSeconds();
    }

    public String issue(String username, String role, long epoch) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(username)
                .claim("role", role)
                .claim("epoch", epoch)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusSeconds(ttlSeconds)))
                .signWith(key)
                .compact();
    }

    /**
     * 校验结果。
     *
     * @param issuedAt 签发时间（仅用于日志排查）
     * @param epoch 签发时的会话世代，与用户当前世代不一致即视为已失效
     */
    public record Parsed(AuthUser user, Instant issuedAt, long epoch) {}

    /** 校验并解出主体；任何不合法（签名错、过期、格式错）都返回 null，由调用方决定回 401。 */
    public Parsed verify(String token) {
        if (token == null || token.isBlank()) {
            return null;
        }
        try {
            Claims claims =
                    Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
            String username = claims.getSubject();
            if (username == null || username.isBlank()) {
                return null;
            }
            String role = claims.get("role", String.class);
            Instant issuedAt = claims.getIssuedAt() == null ? Instant.EPOCH : claims.getIssuedAt().toInstant();
            // 老 token 没有 epoch 声明 → 按 0 处理，与老用户的初始世代一致
            Long epoch = claims.get("epoch", Long.class);
            return new Parsed(new AuthUser(username, role == null ? "user" : role), issuedAt,
                    epoch == null ? 0L : epoch);
        } catch (JwtException | IllegalArgumentException e) {
            return null;
        }
    }
}
