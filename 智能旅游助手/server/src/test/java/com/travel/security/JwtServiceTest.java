package com.travel.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.travel.config.AppProperties;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * JWT 签发与校验。
 *
 * <p>这里最要紧的一条不是「能签能验」，而是**伪造与过期的 token 必须一律返回 null**：
 * 一旦漏掉签名校验，任何人 base64 改个 role 就是管理员。
 */
class JwtServiceTest {

    private static final String SECRET = "travel-copilot-test-secret-please-32bytes";

    private static JwtService service(long ttl) {
        return new JwtService(
                new AppProperties(
                        new AppProperties.Jwt(SECRET, ttl),
                        new AppProperties.Admin("admin", "admin123"),
                        true,
                        new AppProperties.Ai("http://127.0.0.1:1", "s", 1),
                        new AppProperties.Weather("http://127.0.0.1:1", 1)));
    }

    @Test
    @DisplayName("签出来的 token 能验回同一个人与角色")
    void issueThenVerify() {
        JwtService jwt = service(600);
        String token = jwt.issue("alice", "user", 0);
        JwtService.Parsed parsed = jwt.verify(token);
        assertThat(parsed).isNotNull();
        assertThat(parsed.user().username()).isEqualTo("alice");
        assertThat(parsed.user().role()).isEqualTo("user");
        assertThat(parsed.issuedAt()).isNotNull();
        assertThat(parsed.epoch()).isZero();
    }

    @Test
    @DisplayName("会话世代跟着 token 走：改密把它 +1，旧 token 的世代就对不上了")
    void epochRoundTrips() {
        JwtService jwt = service(600);
        assertThat(jwt.verify(jwt.issue("alice", "user", 7)).epoch()).isEqualTo(7);
        assertThat(jwt.verify(jwt.issue("alice", "user", 0)).epoch()).isZero();
    }

    @Test
    @DisplayName("签名被篡改的 token 直接无效（防手改 role）")
    void tamperedTokenIsRejected() {
        JwtService jwt = service(600);
        String token = jwt.issue("alice", "user", 0);
        // 改**签名段第一个字符**，不能改最后一个：
        // HMAC-SHA256 是 32 字节，Base64URL 编码成 43 个字符，最后一个字符只有高 4 位
        // 是有效数据（256 = 42×6 + 4），低 2 位是填充位。'A'(000000) 与 'B'(000001)
        // 只差最低位，解码后字节完全相同 —— 签名没变，token 依然有效，这条用例就会
        // 在「最后一个字符恰好是 A」时偶发失败。签名段首字符 6 位全是有效位。
        int sig = token.lastIndexOf('.') + 1;
        char c = token.charAt(sig);
        String broken = token.substring(0, sig) + (c == 'A' ? 'B' : 'A') + token.substring(sig + 1);
        assertThat(broken).isNotEqualTo(token);
        assertThat(jwt.verify(broken)).isNull();
    }

    @Test
    @DisplayName("换一个密钥签的 token 无效")
    void tokenFromAnotherSecretIsRejected() {
        String other = new JwtService(
                        new AppProperties(
                                new AppProperties.Jwt("another-secret-another-secret-32bytes", 600),
                                new AppProperties.Admin("admin", "admin123"),
                                true,
                                new AppProperties.Ai("http://127.0.0.1:1", "s", 1),
                                new AppProperties.Weather("http://127.0.0.1:1", 1)))
                .issue("alice", "admin", 0);
        assertThat(service(600).verify(other)).isNull();
    }

    @Test
    @DisplayName("过期 token 无效")
    void expiredTokenIsRejected() {
        JwtService jwt = service(-1); // 签发即过期
        assertThat(jwt.verify(jwt.issue("alice", "user", 0))).isNull();
    }

    @Test
    @DisplayName("空 token / 乱码 / null 都返回 null，不抛异常")
    void garbageInputIsRejected() {
        JwtService jwt = service(600);
        assertThat(jwt.verify(null)).isNull();
        assertThat(jwt.verify("")).isNull();
        assertThat(jwt.verify("   ")).isNull();
        assertThat(jwt.verify("not-a-jwt")).isNull();
    }

    @Test
    @DisplayName("密钥短于 32 字节要在启动时就报错，而不是运行时才发现")
    void shortSecretFailsFast() {
        assertThatThrownBy(
                        () ->
                                new JwtService(
                                        new AppProperties(
                                                new AppProperties.Jwt("too-short", 600),
                                                new AppProperties.Admin("admin", "admin123"),
                                                true,
                                                new AppProperties.Ai("http://127.0.0.1:1", "s", 1),
                                                new AppProperties.Weather("http://127.0.0.1:1", 1))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("32");
    }
}
