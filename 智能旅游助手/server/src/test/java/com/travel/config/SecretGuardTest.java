package com.travel.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 密钥守卫的单元测试（不需要 Spring 上下文，直接测静态校验）。
 *
 * <p>锁死的是「配置错误必须在启动期暴露」这件事：
 * 为空、等于仓库里的历史默认值、短于 HS256 要求的 32 字节 —— 三种都必须抛异常。
 * 这几条一旦被改回「打 WARN 继续跑」，站点会带着一把公开密钥上线，而所有功能
 * 测试都还是绿的（token 能签、能验、能登录），只有安全测试能发现。
 */
class SecretGuardTest {

    private static final String GOOD = "0123456789abcdef0123456789abcdef"; // 32 字节

    @Test
    @DisplayName("JWT 密钥为空 → 启动中止，且提示里点名 JWT_SECRET")
    void blankJwtSecretFails() {
        assertThatThrownBy(() -> SecretGuard.requireJwtSecret(null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("JWT_SECRET");
        assertThatThrownBy(() -> SecretGuard.requireJwtSecret("   "))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("JWT_SECRET");
    }

    @Test
    @DisplayName("JWT 密钥等于仓库历史默认值 → 启动中止（等于公开密钥）")
    void knownDefaultJwtSecretFails() {
        assertThatThrownBy(
                        () ->
                                SecretGuard.requireJwtSecret(
                                        "travel-copilot-dev-secret-change-me-please-32bytes"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("默认值");
    }

    @Test
    @DisplayName("JWT 密钥短于 32 字节 → 启动中止（HS256 硬要求）")
    void shortJwtSecretFails() {
        assertThatThrownBy(() -> SecretGuard.requireJwtSecret("too-short-secret"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("32");
    }

    @Test
    @DisplayName("合法 JWT 密钥原样返回（前后空白被裁掉）")
    void validJwtSecretPasses() {
        assertThat(SecretGuard.requireJwtSecret("  " + GOOD + "  ")).isEqualTo(GOOD);
    }

    @Test
    @DisplayName("内部密钥为空 → 启动中止，提示里点名 AI_INTERNAL_SECRET")
    void blankInternalSecretFails() {
        assertThatThrownBy(() -> SecretGuard.requireInternalSecret(""))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("AI_INTERNAL_SECRET");
        assertThatThrownBy(() -> SecretGuard.requireInternalSecret(null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("AI_INTERNAL_SECRET");
    }

    @Test
    @DisplayName("内部密钥等于仓库历史默认值 → 启动中止")
    void knownDefaultInternalSecretFails() {
        assertThatThrownBy(() -> SecretGuard.requireInternalSecret("dev-internal-secret-please-change"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("默认值");
        assertThatThrownBy(() -> SecretGuard.requireInternalSecret("travel-internal-dev-secret"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("默认值");
    }

    @Test
    @DisplayName("内部密钥是自定义短值 → 只告警不中止（协议上没有长度下限）")
    void shortButCustomInternalSecretOnlyWarns() {
        assertThatCode(() -> SecretGuard.requireInternalSecret("test-secret")).doesNotThrowAnyException();
    }
}
