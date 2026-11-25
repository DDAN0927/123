package com.travel.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ReadListener;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletInputStream;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 登录与注册的限流 / 锁定。
 *
 * <p><b>为什么需要它</b>：`/api/auth/options` 一直返回 {@code rate_limit_enabled:false}，
 * 而 `.env` 里写着每分钟 10 次——Python 侧确实实现了 {@code auth_rate_limit}，但
 * {@code AiProxyController.PREFIXES} 里没有 {@code /api/auth}，那段限流**从来没被调用过**。
 * 实测连打 12 次错口令全是 401，没有一次 429。配置在、限流不在，比完全没有更危险。
 *
 * <p><b>为什么在 Spring 侧实现、不把 {@code /api/auth} 塞进反代</b>：Python 那套按 IP
 * 限流读的是 {@code X-Forwarded-For}，而该头客户端可以随手伪造（阶段一已实测），
 * 绕过去就是一个新桶。为了复用一段已知会被绕过的实现，把公网登录入口跨进程转一圈，
 * 是负收益。
 *
 * <p><b>为什么键里带用户名</b>：纯按 IP 的 10 次/5 分钟对校园网、公司网这种 NAT 出口
 * 太紧——一个人手滑就能把整个办公室锁住。带上用户名后，同 IP 下不同账号互不影响。
 *
 * <p><b>不读任何 {@code X-*} / {@code Forwarded} 头</b>：只认 {@code getRemoteAddr()}。
 * 代价见 {@link #clientKey} 的注释。
 *
 * <p><b>计数器在内存里，重启即清零</b>：这是运维的应急手段——答辩/演示前重启一次，
 * 所有桶与锁都归零。而且重启**不会踢掉任何登录**：S-02 之后密钥已落盘复用，
 * token 用的还是同一把密钥，{@code epoch} 也没变。
 */
@Component
public class AuthRateLimitFilter extends OncePerRequestFilter {

    private static final String LOGIN_PATH = "/api/auth/login";
    private static final String REGISTER_PATH = "/api/auth/register";

    /**
     * 登录：每个「用户名|IP」5 分钟内最多 10 次。
     *
     * <p>依据：10 次/5 分钟 ≈ 一天 2880 次。人工爆破撑不住这个成本，而正常用户手滑
     * 三五次远达不到；再紧（比如 5 次）就容易被 NAT 后的多人或记错密码的人撞上。
     * 写死成常量、不做成配置项——一个没人读的配置比一个常量更危险（{@code AUTH_RATE_LIMIT_PER_MINUTE}
     * 就是活例子）。
     */
    private static final int LOGIN_MAX_ATTEMPTS = 10;

    private static final long LOGIN_WINDOW_MS = 5 * 60_000L;

    /**
     * 注册：每个 IP 每小时最多 10 次（默认值，可用 {@code app.auth-rate-limit.register-per-hour} 覆盖）。
     *
     * <p>为什么是 10 而不是 5：注册没有用户名可做键（账号还没建出来），只能按 IP，
     * 而校园网/公司网是多人共用一个出口 IP；答辩现场老师连续注册也可能撞上。
     * 10 次/小时对刷号的约束几乎一样（一天上限 240 个），但误伤概率低得多。
     *
     * <p><b>为什么只有这一条做成可配置</b>：登录的桶是「用户名|IP」，多实例/代理都不会
     * 退化成全局，策略上也不该让运维随手放宽；而注册桶在平台代理后可能变成**全站共用
     * 一个**（所有人看到同一个 {@code getRemoteAddr()}），此时 10 次/小时就是全站上限，
     * 演示、答辩、内测都可能撞上——这类环境需要一个不改代码就能调大的旋钮。
     * 默认值仍是 10，不配就是最严的那一档。
     */
    private static final int DEFAULT_REGISTER_MAX_ATTEMPTS = 10;

    private static final long REGISTER_WINDOW_MS = 60 * 60_000L;

    /** 同账号连续失败达到这个次数就临时锁定。 */
    private static final int LOCK_AFTER_FAILURES = 5;

    /** 锁定时长：短到不影响真用户，长到让爆破成本不可接受。 */
    private static final long LOCK_MS = 60_000L;

    /**
     * 超过这个长度的 body 不缓存。
     *
     * <p>缓存 body 是为了读出 username，但「把请求体整个读进内存」本身就是个放大面：
     * 扫描器往登录接口灌 100MB，我们照单全收就是内存 DoS。所以只在 8KB 以内才包装，
     * 超长/未知长度一律不包装——此时 username 为 null，键退化成 {@code anon|IP}，
     * body 原样交给控制器由它自己拒绝（返回 400）。
     */
    private static final int MAX_CACHED_BODY_BYTES = 8192;

    /** 用户名长度上限：防止有人用超长字符串把 map 的键撑爆。 */
    private static final int MAX_USERNAME_LEN = 64;

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /**
     * 限流与锁定必须留痕。
     *
     * <p>没有日志时，「有人在爆破」和「管理员被锁死」这两件事在服务端都只剩一个症状：
     * 用户说「登不上」。日志只记 ip / 用户名 / 原因 / 剩余秒数，**不记口令、不记 body**
     * —— 记 body 等于把明文口令写进日志。
     */
    private static final Logger log = LoggerFactory.getLogger(AuthRateLimitFilter.class);

    /** 可替换，仅为了单测能推进时间（锁定 60 秒在集成测试里没法等）。 */
    private Clock clock = Clock.systemUTC();

    /** 注册上限，默认 {@value #DEFAULT_REGISTER_MAX_ATTEMPTS}；见上方注释说明为何可配。 */
    private int registerMaxAttempts = DEFAULT_REGISTER_MAX_ATTEMPTS;

    /** 滑动窗口：键 → 窗口内每次尝试的时间戳。 */
    private final Map<String, Deque<Long>> windows = new ConcurrentHashMap<>();

    /** 账号锁：{@code 用户名|IP} → 连续失败次数 + 解锁时刻（键的构成见 {@link #lockKey}）。 */
    private final Map<String, FailState> failures = new ConcurrentHashMap<>();

    void setClock(Clock clock) {
        this.clock = clock;
    }

    /**
     * 注册上限的唯一旋钮。默认 10；非正数视为非法、回落到默认值（防止有人写 0 把注册全关掉）。
     */
    @Value("${app.auth-rate-limit.register-per-hour:10}")
    void setRegisterMaxAttempts(int value) {
        this.registerMaxAttempts = value > 0 ? value : DEFAULT_REGISTER_MAX_ATTEMPTS;
    }

    /**
     * 请求路径，**唯一取法**。
     *
     * <p>为什么不用 {@code getRequestURI()}：它返回的是**原始、未解码、含 context-path**
     * 的 URI，于是有两个失效模式，且都是"静默失效"（不报错、不打日志、限流器直接不跑）：
     * <ul>
     *   <li><b>百分号编码</b>：{@code /api/auth/%6Cogin} 的 URI 不等于 {@code /api/auth/login}，
     *       而 Tomcat 会先把它解码成 {@code login} 再交给 Spring MVC —— 于是控制器照常登录，
     *       限流器却认为"这不是登录接口"。实测：编码路径连打 20 次全部 200，一次都没记账。</li>
     *   <li><b>context-path</b>：一旦配了 {@code server.servlet.context-path}，URI 变成
     *       {@code /ctx/api/auth/login}，永远不等于常量 —— 整个过滤器对所有请求失效。</li>
     * </ul>
     *
     * <p>{@code getServletPath()} 已解码、已去掉 context-path，与 Spring MVC 的路由依据一致，
     * 两种部署下都是 {@code /api/auth/login}。
     *
     * <p><b>这个判断只能有一处</b>：{@link #shouldNotFilter} 与 {@link #doFilterInternal}
     * 必须调用同一个方法。本轮漏洞的根因就是"同一件事在两处各判一次"（过滤器看原始 URI，
     * MVC 看解码后路径），而不是某一行写错。
     *
     * <p><b>不要为百分号编码补 MockMvc 用例</b>：MockMvc 会把 {@code %6C} 二次编码成
     * {@code %256C}（实测），用它写的用例只会得到 404 —— 一个永远绿的假守卫。编码绕过
     * **只能在 HTTP 层测**（真实 Tomcat + 真实 curl）。context-path 与明文路径的等价性
     * 已经由 {@code AuthRateLimitUnitTest#onlyGuardsLoginAndRegister} 覆盖，那两条是能测的。
     */
    private static String pathOf(HttpServletRequest request) {
        return request.getServletPath();
    }

    @Override
    protected boolean shouldNotFilter(@NonNull HttpServletRequest request) {
        if (!"POST".equals(request.getMethod())) {
            return true;
        }
        String path = pathOf(request);
        return !LOGIN_PATH.equals(path) && !REGISTER_PATH.equals(path);
    }

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain chain)
            throws ServletException, IOException {

        boolean login = LOGIN_PATH.equals(pathOf(request));
        String ip = remoteAddr(request);

        // 只有登录需要用户名（注册时账号还不存在，只能按 IP）
        HttpServletRequest effective = request;
        String username = null;
        if (login && request.getContentLengthLong() >= 0
                && request.getContentLengthLong() <= MAX_CACHED_BODY_BYTES) {
            CachedBodyRequest cached = new CachedBodyRequest(request);
            effective = cached;
            username = usernameOf(cached);
        }

        long now = clock.millis();

        // ---------- 1) 账号锁：先判锁，再验密 ----------
        // 顺序很重要：锁定期内即使密码正确也必须 429，否则锁等于不存在。
        if (username != null) {
            long left = lockedForMs(username, ip, now);
            if (left > 0) {
                reject(request, response, ip, username, left,
                        "账号临时锁定，请 " + seconds(left) + " 秒后重试", "lock");
                return;
            }
        }

        // ---------- 2) 滑动窗口 ----------
        String key = login ? clientKey(username, ip) : "register|" + ip;
        long windowMs = login ? LOGIN_WINDOW_MS : REGISTER_WINDOW_MS;
        int max = login ? LOGIN_MAX_ATTEMPTS : registerMaxAttempts;

        long retryAfterMs = hit(key, max, windowMs, now);
        if (retryAfterMs > 0) {
            reject(request, response, ip, username, retryAfterMs,
                    "尝试过于频繁，请 " + seconds(retryAfterMs) + " 秒后再试", "window");
            return;
        }

        chain.doFilter(effective, response);

        // ---------- 3) 记账：只有登录需要，且必须在链后看状态码 ----------
        if (login && username != null) {
            int status = response.getStatus();
            if (status == HttpServletResponse.SC_UNAUTHORIZED) {
                recordFailure(username, ip);
            } else if (status >= 200 && status < 300) {
                // 登录成功清零：不惩罚记错一次又想起来的人
                failures.remove(lockKey(username, ip));
            }
        }
    }

    /**
     * 限流键。
     *
     * <p>用户名先 trim：{@code AuthService.login} 用的是 {@code username.trim()}，
     * 这里不 trim 的话 {@code " alice"} 与 {@code "alice"} 会落进两个桶，而它们认证的是
     * 同一个账号 —— 加个空格就能绕过限流与账号锁。
     *
     * <p>不区分大小写是刻意的：注册允许大小写，{@code Alice} 与 {@code alice} 可能是两个
     * 不同账号，合并他们的桶会让一个人的失败锁住另一个人。
     *
     * <p><b>平台代理的后果</b>：如果容器里 {@code getRemoteAddr()} 恒定（请求都从平台
     * 代理进来），登录桶退化成「纯按账号」，仍然正确；但注册桶会变成**全站共用一个**，
     * 10 次/小时即全站上限。注册默认关闭（{@code allow-registration} 默认 false），
     * 只有运维显式打开才会遇到这个上限；真遇到了重启一次即可清零。
     */
    private static String clientKey(String username, String ip) {
        return username == null ? "anon|" + ip : username + "|" + ip;
    }

    /**
     * 账号锁的键：{@code 用户名|IP}。
     *
     * <p>以前是纯用户名，看起来更"安全"，实际是把锁变成了**攻击者手里的开关**：
     * 任何人对 {@code admin} 连打 5 次错口令就能锁住管理员 60 秒，每 60 秒补 5 个请求
     * 即可无限维持，而攻击者完全不需要知道口令 —— 一个"防爆破"的机制被用来做拒绝服务。
     * 实测：IP-A 锁住后，IP-B 用**正确**口令仍是 429；三个源地址即可让管理员 100% 登不进。
     *
     * <p>换成 {@code 用户名|IP} 之后，锁只能锁住"攻击者自己这条链路"，受害者从别处照常登录。
     * 代价是换 IP 就能重置锁 —— 这是刻意的取舍：爆破仍被第 2 道闸（同键 10 次/5 分钟）拦住，
     * 而"锁死真实用户"没有任何补偿手段。**任何以账号为唯一维度的硬阻断都会重新长回这个洞**，
     * 所以账号维度的观测只走日志（{@link #recordFailure}），不参与拒绝判定。
     */
    private static String lockKey(String username, String ip) {
        return username + "|" + ip;
    }

    private String remoteAddr(HttpServletRequest request) {
        String ip = request.getRemoteAddr();
        return ip == null || ip.isBlank() ? "unknown" : ip;
    }

    /** 从缓存的 body 里取 username；读不出来就返回 null（键退化为 anon|IP）。 */
    private String usernameOf(HttpServletRequest request) {
        try {
            JsonNode node = MAPPER.readTree(request.getInputStream());
            JsonNode u = node == null ? null : node.get("username");
            if (u == null || !u.isTextual()) {
                return null;
            }
            String name = u.asText().trim();
            if (name.isEmpty() || name.length() > MAX_USERNAME_LEN) {
                return null;
            }
            return name;
        } catch (Exception e) {
            // 空 body / 非 JSON / 超长：都不是这里该报错的事，交给控制器返回 400
            return null;
        }
    }

    private long lockedForMs(String username, String ip, long now) {
        FailState state = failures.get(lockKey(username, ip));
        if (state == null) {
            return 0;
        }
        synchronized (state) {
            return state.lockedUntilMs > now ? state.lockedUntilMs - now : 0;
        }
    }

    /**
     * 记一次登录失败；达到阈值就锁定，并打一条 WARN。
     *
     * <p>日志里带用户名是刻意的：锁键已经加了 IP，单条日志看不出"同一个账号被多个 IP 轮流打"，
     * 只能靠日志聚合按用户名统计来发现 —— 这正是"账号维度只观测、不阻断"的落点。
     */
    private void recordFailure(String username, String ip) {
        FailState state = failures.computeIfAbsent(lockKey(username, ip), k -> new FailState());
        synchronized (state) {
            state.consecutive++;
            if (state.consecutive >= LOCK_AFTER_FAILURES) {
                state.lockedUntilMs = clock.millis() + LOCK_MS;
                state.consecutive = 0;
                log.warn("登录连续失败 {} 次，锁定 {}s：username={} ip={}",
                        LOCK_AFTER_FAILURES, LOCK_MS / 1000, username, ip);
            } else {
                log.warn("登录失败：username={} ip={} 连续失败={}/{}",
                        username, ip, state.consecutive, LOCK_AFTER_FAILURES);
            }
        }
    }

    /**
     * 记一次尝试并返回「还要等多久」；返回 0 表示放行。
     *
     * <p>滑动窗口而不是固定窗口：固定窗口在边界处能放过 2 倍流量。
     */
    private long hit(String key, int max, long windowMs, long now) {
        Deque<Long> hits = windows.computeIfAbsent(key, k -> new ArrayDeque<>());
        synchronized (hits) {
            while (!hits.isEmpty() && now - hits.peekFirst() >= windowMs) {
                hits.pollFirst();
            }
            if (hits.size() >= max) {
                return windowMs - (now - hits.peekFirst());
            }
            hits.addLast(now);
            return 0;
        }
    }

    private static long seconds(long ms) {
        return Math.max(1, (ms + 999) / 1000);
    }

    private void reject(
            HttpServletRequest request,
            HttpServletResponse response,
            String ip,
            String username,
            long retryAfterMs,
            String detail,
            String reason)
            throws IOException {
        long secs = seconds(retryAfterMs);
        // 只记 ip / 用户名 / 原因 / 剩余秒数；不记口令、不记 body（记 body 等于把明文口令写进日志）
        log.warn("限流拒绝：{} {} ip={} username={} reason={} retryAfter={}s",
                request.getMethod(), pathOf(request), ip, username == null ? "-" : username, reason, secs);
        response.setStatus(429);
        response.setHeader("Retry-After", Long.toString(secs));
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("application/json;charset=UTF-8");
        // 文案里只有中文和数字，不含引号/反斜杠，直接拼是安全的
        response.getWriter().write("{\"detail\":\"" + detail + "\"}");
    }

    private static final class FailState {
        int consecutive;
        long lockedUntilMs;
    }

    /**
     * 把请求体缓存下来，让过滤器与控制器都能读到。
     *
     * <p>不加这层的话，过滤器读完 username，控制器再读 body 就是空字符串，
     * {@code @Valid LoginReq} 直接 400 —— 所有登录都会挂。
     *
     * <p>每次 {@code getInputStream()} 返回一个全新的流，语义上等价于原始请求。
     */
    private static final class CachedBodyRequest extends HttpServletRequestWrapper {

        private final byte[] body;

        CachedBodyRequest(HttpServletRequest request) throws IOException {
            super(request);
            this.body = request.getInputStream().readAllBytes();
        }

        @Override
        public ServletInputStream getInputStream() {
            ByteArrayInputStream source = new ByteArrayInputStream(body);
            return new ServletInputStream() {
                @Override
                public int read() {
                    return source.read();
                }

                @Override
                public boolean isFinished() {
                    return source.available() == 0;
                }

                @Override
                public boolean isReady() {
                    return true;
                }

                @Override
                public void setReadListener(ReadListener listener) {
                    // 同步读取，不需要异步回调
                }
            };
        }

        @Override
        public BufferedReader getReader() {
            return new BufferedReader(new InputStreamReader(getInputStream(), StandardCharsets.UTF_8));
        }
    }
}
