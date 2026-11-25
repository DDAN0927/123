package com.travel.config;

import java.nio.charset.StandardCharsets;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * 启动期密钥守卫：JWT 签名密钥与内部共享密钥不允许为空，也不允许沿用仓库里的历史默认值。
 *
 * <p><b>为什么直接让启动失败，而不是打一条 WARN</b>：这两个值一旦是公开常量，
 * 任何人 clone 仓库就能自己签一个 {@code role=admin} 的 token（JWT），或者直连
 * 7861 自称管理员（内部密钥）。而 WARN 在容器日志里通常没人看 —— 表现是「站点
 * 一切正常，直到某天被人接管」。fail-fast 把配置错误暴露在部署当场，代价只是
 * 首次启动需要显式设两个环境变量。
 *
 * <p><b>为什么还要拦「历史默认值」而不只是拦空串</b>：`.env.example` / README /
 * `scripts/start_all.sh` 里曾经写死过这几个值，照着文档抄一遍就会把它们带进生产。
 * 只判空串挡不住这种「照着文档配错」的路径。
 *
 * <p>校验逻辑做成静态方法，是为了让 {@link com.travel.security.JwtService} 复用
 * 同一段判断与同一条错误文案 —— 否则 bean 初始化顺序不同会给出两种不同的报错，
 * 排查时反而更迷惑。
 */
@Component
public class SecretGuard {

    private static final Logger log = LoggerFactory.getLogger(SecretGuard.class);

    /** HS256/HS384 要求密钥至少 32 字节（jjwt 会在更短时抛 WeakKeyException）。 */
    private static final int JWT_MIN_BYTES = 32;

    /**
     * 内部密钥只做「共享口令」用，协议上没有长度下限，所以不做硬性拒绝，
     * 短于该值时打 WARN（真正致命的是「等于历史默认值」和「为空」）。
     */
    private static final int INTERNAL_RECOMMENDED_CHARS = 32;

    /** 曾经写死在仓库里的默认值：任何人可读，等于没有密钥。 */
    private static final Set<String> KNOWN_DEFAULTS =
            Set.of(
                    "travel-copilot-dev-secret-change-me-please-32bytes",
                    "travel-internal-dev-secret",
                    "dev-internal-secret-please-change",
                    "change-me",
                    "secret");

    public SecretGuard(AppProperties props) {
        requireJwtSecret(props.jwt().secret());
        requireInternalSecret(props.ai().internalSecret());
    }

    /**
     * 校验 JWT 签名密钥，返回可直接用于 {@code Keys.hmacShaKeyFor} 的值。
     *
     * @throws IllegalStateException 为空、等于历史默认值、或短于 32 字节
     */
    public static String requireJwtSecret(String secret) {
        String value = secret == null ? "" : secret.trim();
        if (value.isEmpty()) {
            throw new IllegalStateException(
                    "启动中止：JWT_SECRET 未设置。请设置环境变量 JWT_SECRET（≥32 字符），"
                            + "可用 python -c \"import secrets;print(secrets.token_hex(32))\" 生成；"
                            + "用 scripts/start_all.sh 或 start.sh 启动时会自动生成并落盘复用。");
        }
        if (KNOWN_DEFAULTS.contains(value)) {
            throw new IllegalStateException(
                    "启动中止：JWT_SECRET 仍是仓库里的示例默认值，等于公开密钥（任何人可伪造 admin token）。"
                            + "请换成一个随机值：python -c \"import secrets;print(secrets.token_hex(32))\"。");
        }
        int bytes = value.getBytes(StandardCharsets.UTF_8).length;
        if (bytes < JWT_MIN_BYTES) {
            throw new IllegalStateException(
                    "启动中止：JWT_SECRET 只有 "
                            + bytes
                            + " 字节，HS256 要求 ≥"
                            + JWT_MIN_BYTES
                            + " 字节。请换一个更长的随机值（python -c \"import secrets;print(secrets.token_hex(32))\"）。");
        }
        return value;
    }

    /**
     * 校验 SpringBoot → Python 的内部共享密钥。
     *
     * <p>为空时直接失败：此时反代会注入一个空头，Python 侧按「密钥为空即关闭内部信任」
     * 退化成只认 token，而代理又把 token 剥掉了 —— 表现为所有需要登录的 AI 接口
     * 全部 401/403，排查方向会被引到「用户没登录」上，极难定位。宁可启动就报错。
     */
    public static void requireInternalSecret(String secret) {
        String value = secret == null ? "" : secret.trim();
        if (value.isEmpty()) {
            throw new IllegalStateException(
                    "启动中止：AI_INTERNAL_SECRET 未设置。SpringBoot 与 Python 必须共享同一个值，"
                            + "否则所有经反代的 AI 接口都会 403。用 scripts/start_all.sh / start.sh 启动时会自动生成。");
        }
        if (KNOWN_DEFAULTS.contains(value)) {
            throw new IllegalStateException(
                    "启动中止：AI_INTERNAL_SECRET 仍是仓库里的示例默认值（已入库，等于公开）。"
                            + "请换成一个随机值：python -c \"import secrets;print(secrets.token_hex(32))\"。");
        }
        if (value.length() < INTERNAL_RECOMMENDED_CHARS) {
            log.warn(
                    "AI_INTERNAL_SECRET 只有 {} 字符（建议 ≥{}）。当前值不是公开默认值，可以启动；"
                            + "但如果 7861 端口在容器网络内可达，短口令会降低伪造门槛。",
                    value.length(),
                    INTERNAL_RECOMMENDED_CHARS);
        }
    }
}
