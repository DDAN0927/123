/**
 * 观潮 · Cloudflare Worker 后端
 * - 邮箱密码注册/登录(令牌 30 天)
 * - 跨设备同步:自选、对比、提醒、模拟账户
 * - /api/snapshot 全市场 A 股快照(服务端缓存 10 分钟)
 * - cron 每 5 分钟检查价格提醒,可选 Resend 邮件
 */
const UT = 'bd1d9ddb04089700cf9c27f6f7426281';
const EM_FS = 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048';
const EM_FIELDS = 'f2,f3,f9,f12,f14,f20,f23,f100';
const SESSION_DAYS = 30;
const SNAPSHOT_TTL = 10 * 60 * 1000;

// Workers 生产运行时的 PBKDF2 迭代上限为 100,000(超过会抛 NotSupportedError),
// 因此这里取平台允许的最大值。OWASP 建议 PBKDF2-HMAC-SHA256 >= 600,000,差距见 README。
const PBKDF2_ITER = 100000;
const LEGACY_ITER = 30000; // 旧用户默认值,登录成功后自动升级
const LOGIN_MAX_FAILS = 5; // 窗口内最多失败次数
const LOGIN_WINDOW_MS = 15 * 60 * 1000;
const LOGIN_LOCK_MS = 15 * 60 * 1000;
const REGISTER_MAX = 5; // 同一 IP 在窗口内最多注册次数

// 邮箱维度不做硬锁:硬锁意味着「知道对方邮箱 = 每 15 分钟错 5 次就能永久锁死他人登录」。
// 改为递增延迟——攻击者锁不死人,但串行爆破被拖慢(并发爆破的残余风险见 README)。
const EMAIL_BACKOFF_AFTER = 3; // 前 3 次失败不惩罚,容忍正常手滑
const EMAIL_BACKOFF_BASE_MS = 200;
// 上限不宜太大:延迟越长,攻击者用 1 个请求换到的 Worker 占用时间越长(放大效应)。
const EMAIL_BACKOFF_MAX_MS = 2000;

// 云端状态的结构/规模上限(服务端为准,前端 sanitizeCloudState 只是体验优化)
const CODE_RE = /^[A-Za-z0-9][A-Za-z0-9.\-]{0,11}$/;
const ALERT_DIRS = new Set(['above', 'below', 'pct_up', 'pct_down']);
const MAX_ALERTS = 200;
const MAX_FAV_GROUPS = 20;
const MAX_GROUP_CODES = 500;
// cron 单轮最多查多少个代码:每 40 个 = 1 次子请求,800 → 20 次,
// 给免费版 50 次上限留出余量(快照抓取一次就要 30 次)。
const MAX_ALERT_CODES = 800;
// 单轮最多发多少封邮件:每封 = 1 次子请求,与行情查询共享免费版 50 次上限。
// 超出的用户整户顺延到下一轮(不写 hit),避免"标了 hit 却发不出去"的静默丢失。
const MAX_MAILS_PER_ROUND = 20;

const enc = new TextEncoder();

const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Cache-Control': 'no-store',
  'Cross-Origin-Resource-Policy': 'same-site',
};

function cors(env) {
  // 未配置 ALLOWED_ORIGIN 时不返回 CORS 头,浏览器会拒绝跨域调用(默认拒绝)。
  // 显式拒绝 '*':README 曾教用户本地调试填 '*',但通配符会让任意站点代受害者
  // 发起登录/注册(每个受害者是一个独立出口 IP),把按 IP 的限流维度整个绕开。
  const h = {
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    Vary: 'Origin',
    ...SECURITY_HEADERS,
  };
  const allowed = env && env.ALLOWED_ORIGIN;
  if (allowed && allowed !== '*') h['Access-Control-Allow-Origin'] = allowed;
  return h;
}
/* 只接受 application/json:跨站页面可以用 text/plain 发起「简单请求」绕过预检,
   拿受害者的 IP 去打登录/注册,把按 IP 的限流维度换成无数个出口。
   强制 JSON 会让这类请求必须先过预检,而预检会被 ALLOWED_ORIGIN 挡住。 */
function jsonOnly(req, env) {
  const ct = (req.headers.get('Content-Type') || '').toLowerCase();
  if (ct.startsWith('application/json')) return null;
  return json({ error: 'Content-Type 必须为 application/json' }, 415, env);
}
function json(data, status = 200, env = {}, extra = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(env), ...extra },
  });
}
function timingSafeEqual(a, b) {
  const x = enc.encode(String(a)), y = enc.encode(String(b));
  let diff = x.length ^ y.length;
  const n = Math.max(x.length, y.length);
  for (let i = 0; i < n; i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}
function b64(buf) {
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}
function unb64(s) {
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}
function randomToken() {
  const b = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
}
async function hashPassword(password, saltB64, iterations = PBKDF2_ITER) {
  const key = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt: unb64(saltB64), iterations, hash: 'SHA-256' },
    key,
    256,
  );
  return b64(bits);
}
function emailValid(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 120;
}
async function createSession(env, userId) {
  const token = randomToken();
  const expires = Date.now() + SESSION_DAYS * 86400000;
  await env.DB.prepare('INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,?)')
    .bind(token, userId, expires).run();
  return token;
}
async function authUser(req, env) {
  const header = req.headers.get('Authorization') || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : '';
  if (!token) return null;
  const row = await env.DB.prepare('SELECT user_id,expires_at FROM sessions WHERE token=?')
    .bind(token).first();
  if (!row) return null;
  if (row.expires_at < Date.now()) {
    await env.DB.prepare('DELETE FROM sessions WHERE token=?').bind(token).run();
    return null;
  }
  return { id: row.user_id, token };
}
async function readBody(req) {
  try { return await req.json(); } catch (e) { return null; }
}
function secid(code) {
  if (/^\d{6}$/.test(code)) return (/^(60|68|900)/.test(code) ? '1.' : '0.') + code;
  if (/^\d{4,5}$/.test(code)) return '116.' + code;
  if (/^[A-Z][A-Z0-9.]{0,9}$/.test(code)) return '105.' + code;
  return null;
}
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function fetchSnapshot(env, part = 1) {
  const PAGES_PER_PART = 30;
  const start = (part - 1) * PAGES_PER_PART + 1;
  const end = part * PAGES_PER_PART;
  const rows = [];
  let total = 0;
  for (let pn = start; pn <= end; pn++) {
    const url = 'https://push2.eastmoney.com/api/qt/clist/get' +
      `?pn=${pn}&pz=100&po=1&np=1&fltt=2&invt=2&fid=f12` +
      `&fs=${encodeURIComponent(EM_FS)}&fields=${EM_FIELDS}&ut=${UT}`;
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0', Referer: 'https://quote.eastmoney.com/' },
    });
    if (!res.ok) throw new Error('eastmoney ' + res.status);
    const j = await res.json();
    const d = j && j.data;
    if (!d || !Array.isArray(d.diff) || !d.diff.length) break;
    total = d.total || total;
    d.diff.forEach((x) => {
      const price = Number(x.f2);
      if (!x.f12 || !x.f14 || !(price > 0)) return;
      rows.push({
        code: String(x.f12),
        name: String(x.f14),
        price,
        chg: Number(x.f3) || 0,
        pe: Math.max(0, Number(x.f9) || 0),
        pb: Math.max(0, Number(x.f23) || 0),
        mcap: Number(x.f20) || 0,
        sector: x.f100 && x.f100 !== '-' ? String(x.f100) : '综合',
      });
    });
    if (total && start === 1 && rows.length >= total) break;
    if (total && pn * 100 >= total) break;
    await sleep(100);
  }
  const payload = {
    part,
    rows,
    total: total || rows.length,
    updatedAt: Date.now(),
    complete: !total || (part === 1 ? rows.length >= total : true),
  };
  await env.DB.prepare(
    'INSERT INTO cache (key,payload,updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at',
  ).bind('cn_snapshot_' + part, JSON.stringify(payload), Date.now()).run();
  return payload;
}

async function handleSnapshot(env, part) {
  const p = part === 2 ? 2 : 1;
  const key = 'cn_snapshot_' + p;
  const row = await env.DB.prepare('SELECT payload,updated_at FROM cache WHERE key=?')
    .bind(key).first();
  if (row && Date.now() - row.updated_at < SNAPSHOT_TTL) {
    return new Response(row.payload, {
      headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(env), 'X-Cache': 'hit' },
    });
  }
  try {
    const payload = await fetchSnapshot(env, p);
    return json(payload, 200, env);
  } catch (e) {
    if (row) {
      return new Response(row.payload, {
        headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(env), 'X-Cache': 'stale' },
      });
    }
    return json({ error: 'snapshot failed', detail: String(e && e.message || e) }, 502, env);
  }
}

async function register(req, env) {
  const body = await readBody(req);
  if (!body) return json({ error: 'bad json' }, 400, env);
  // 注册限流:与登录的 i: 键分开命名,避免互相影响。每次尝试都计数(含格式错误),
  // 否则攻击者可以用垃圾请求绕过配额、只把有效注册打进来。
  const ip = req.headers.get('CF-Connecting-IP') || 'unknown';
  const wait = await gateBump(env, 'r:' + ip, REGISTER_MAX, LOGIN_LOCK_MS);
  if (wait > 0) {
    return json({ error: `注册过于频繁,请 ${Math.ceil(wait / 60)} 分钟后再试` }, 429, env, { 'Retry-After': String(wait) });
  }
  const email = String(body.email || '').trim().toLowerCase();
  const password = String(body.password || '');
  if (!emailValid(email)) return json({ error: '邮箱格式不正确' }, 400, env);
  if (password.length < 8 || password.length > 72) return json({ error: '密码需为 8–72 位' }, 400, env);
  const exists = await env.DB.prepare('SELECT id FROM users WHERE email=?').bind(email).first();
  if (exists) return json({ error: '邮箱已注册' }, 409, env);
  const salt = b64(crypto.getRandomValues(new Uint8Array(16)));
  const hash = await hashPassword(password, salt, PBKDF2_ITER);
  const id = crypto.randomUUID();
  await env.DB.prepare('INSERT INTO users (id,email,salt,pass_hash,iterations,created_at) VALUES (?,?,?,?,?,?)')
    .bind(id, email, salt, hash, PBKDF2_ITER, Date.now()).run();
  const token = await createSession(env, id);
  return json({ token, email }, 200, env);
}

/* 限流键命名空间:
     i:<ip>     登录来源(硬锁,唯一会返回 429 的维度)
     e:<email>  登录目标(只计数 + 递增延迟,永不硬锁)
     r:<ip>     注册来源(硬锁)
   计数与判定合成一条 UPSERT:先自增拿新值,再判是否超限。仅把"读"和"写"两行
   调换顺序不够——两者之间仍有 await 边界,并发请求会一起穿过。 */
const SQL_GATE_BUMP = `INSERT INTO login_attempts (key,fails,first_at,locked_until) VALUES (?,1,?,0)
ON CONFLICT(key) DO UPDATE SET
  fails = CASE WHEN excluded.first_at - first_at < ? THEN fails + 1 ELSE 1 END,
  first_at = CASE WHEN excluded.first_at - first_at < ? THEN first_at ELSE excluded.first_at END,
  locked_until = CASE
    WHEN excluded.first_at - first_at >= ? THEN 0
    WHEN locked_until > ? THEN locked_until
    WHEN fails + 1 > ? THEN ?
    ELSE locked_until END
RETURNING fails, locked_until`;
const SQL_BUMP_ONLY = `INSERT INTO login_attempts (key,fails,first_at,locked_until) VALUES (?,1,?,0)
ON CONFLICT(key) DO UPDATE SET
  fails = CASE WHEN excluded.first_at - first_at < ? THEN fails + 1 ELSE 1 END,
  first_at = CASE WHEN excluded.first_at - first_at < ? THEN first_at ELSE excluded.first_at END,
  locked_until = 0`;

/* 闸门必须「先写后判」:先原子自增、拿到新计数,再决定放行还是 429。
   若先 SELECT 判锁、再 UPSERT 计数,并发请求会全部读到 locked_until=0 而放行,
   有效配额 = 并发数 × 上限(实测 20 并发可全部穿过)。
   阈值语义:第 maxFails 次仍放行(返回 401),第 maxFails+1 次起 429。 */
async function gateBump(env, key, maxFails, lockMs) {
  const now = Date.now();
  const row = await env.DB.prepare(SQL_GATE_BUMP)
    .bind(key, now, LOGIN_WINDOW_MS, LOGIN_WINDOW_MS, LOGIN_WINDOW_MS, now, maxFails, now + lockMs)
    .first();
  const until = row ? Number(row.locked_until) || 0 : 0;
  return until > now ? Math.ceil((until - now) / 1000) : 0;
}
/* 登录成功时回退本次预占的配额。只减 1、不清零:
   攻击者必须持有一个有效账号,才能每轮多换 1 次猜测机会,代价高于收益。 */
async function gateRelease(env, key) {
  await env.DB.prepare('UPDATE login_attempts SET fails = CASE WHEN fails > 0 THEN fails - 1 ELSE 0 END WHERE key=?')
    .bind(key).run();
}
async function bumpOnly(env, key) {
  const now = Date.now();
  await env.DB.prepare(SQL_BUMP_ONLY).bind(key, now, LOGIN_WINDOW_MS, LOGIN_WINDOW_MS).run();
}
// 邮箱维度:失败越多等越久,但永远放行(不返回 429)。
async function emailBackoffMs(env, email) {
  const r = await env.DB.prepare('SELECT fails,first_at FROM login_attempts WHERE key=?')
    .bind('e:' + email).first();
  if (!r) return 0;
  if (Date.now() - r.first_at >= LOGIN_WINDOW_MS) return 0;
  const fails = Number(r.fails) || 0;
  if (fails < EMAIL_BACKOFF_AFTER) return 0;
  return Math.min(EMAIL_BACKOFF_MAX_MS, EMAIL_BACKOFF_BASE_MS * 2 ** (fails - EMAIL_BACKOFF_AFTER));
}
async function loginFail(env, email) {
  await bumpOnly(env, 'e:' + email);
}
// 只清邮箱键。IP 键不能清零——清零等于让攻击者登录自己的账号就把失败计数归零;
// 成功登录只在 gateRelease 里回退 1 次预占配额。
async function loginClear(env, email) {
  await env.DB.prepare('DELETE FROM login_attempts WHERE key=?').bind('e:' + email).run();
}

async function login(req, env) {
  const body = await readBody(req);
  if (!body) return json({ error: 'bad json' }, 400, env);
  const email = String(body.email || '').trim().toLowerCase();
  const password = String(body.password || '');
  if (!email || password.length > 72) return json({ error: '邮箱或密码错误' }, 401, env);
  const ip = req.headers.get('CF-Connecting-IP') || 'unknown';
  const wait = await gateBump(env, 'i:' + ip, LOGIN_MAX_FAILS, LOGIN_LOCK_MS);
  if (wait > 0) {
    return json({ error: `尝试次数过多,请 ${Math.ceil(wait / 60)} 分钟后再试` }, 429, env, { 'Retry-After': String(wait) });
  }
  const backoff = await emailBackoffMs(env, email);
  if (backoff > 0) await sleep(backoff);
  const user = await env.DB.prepare('SELECT id,email,salt,pass_hash,iterations FROM users WHERE email=?')
    .bind(email).first();
  const iters = user ? (Number(user.iterations) || LEGACY_ITER) : PBKDF2_ITER;
  // 用户不存在时同样做一次哈希,避免响应时间暴露邮箱是否已注册
  const hash = await hashPassword(password, user ? user.salt : b64(new Uint8Array(16)), iters);
  if (!user || !timingSafeEqual(hash, user.pass_hash)) {
    await loginFail(env, email);
    return json({ error: '邮箱或密码错误' }, 401, env);
  }
  // 成功:回退本次预占的 IP 配额(不清零),再清邮箱维度。
  await gateRelease(env, 'i:' + ip);
  await loginClear(env, email);
  if (iters < PBKDF2_ITER) {
    // 透明升级:密码正确时用新迭代次数重新哈希并保存
    try {
      const upgraded = await hashPassword(password, user.salt, PBKDF2_ITER);
      await env.DB.prepare('UPDATE users SET pass_hash=?, iterations=? WHERE id=?')
        .bind(upgraded, PBKDF2_ITER, user.id).run();
    } catch (e) { /* 升级失败不影响本次登录 */ }
  }
  const token = await createSession(env, user.id);
  return json({ token, email: user.email }, 200, env);
}

async function getState(req, env, user) {
  const row = await env.DB.prepare('SELECT data,updated_at FROM states WHERE user_id=?')
    .bind(user.id).first();
  if (!row) return json({ state: null, updatedAt: 0 }, 200, env);
  let state = null;
  try { state = JSON.parse(row.data); } catch (e) {}
  return json({ state, updatedAt: row.updated_at }, 200, env);
}

/* 云端状态来自前端,而前端是攻击者可控的——sanitizeCloudState 只是体验优化,服务端必须自己校验。
   策略:非法条目**逐条丢弃**,不整体 400(一个脏字段不该让用户整个状态同步失败);
   结构性错误(如 alerts 不是数组)按空处理。其余字段原样保留,避免影响账户/自选同步。 */
function sanitizeState(s) {
  const out = { ...s };
  // 只在字段存在时归一化:若客户端压根没带 alerts,保持"不存在",
  // 否则写成 [] 会让前端拉取时把本地提醒清空(凭空制造数据丢失)。
  if ('alerts' in s) out.alerts = Array.isArray(s.alerts) ? s.alerts.reduce((acc, a) => {
    if (acc.length >= MAX_ALERTS) return acc;
    if (!a || typeof a !== 'object' || Array.isArray(a)) return acc;
    if (!ALERT_DIRS.has(a.dir)) return acc;
    if (typeof a.code !== 'string' || !CODE_RE.test(a.code)) return acc;
    const price = Number(a.price);
    if (!Number.isFinite(price) || price <= 0) return acc;
    if ((a.dir === 'pct_up' || a.dir === 'pct_down') && price > 100) return acc;
    acc.push({ ...a, code: a.code, dir: a.dir, price });
    return acc;
  }, []) : [];
  if ('favGroups' in s) out.favGroups = Array.isArray(s.favGroups) ? s.favGroups.slice(0, MAX_FAV_GROUPS).map((g) => ({
    name: g && typeof g.name === 'string' ? g.name.slice(0, 24) : '',
    codes: Array.isArray(g && g.codes)
      ? g.codes.filter((c) => typeof c === 'string' && CODE_RE.test(c)).slice(0, MAX_GROUP_CODES)
      : [],
  })) : [];
  return out;
}

async function putState(req, env, user) {
  const body = await readBody(req);
  if (!body || !body.state || typeof body.state !== 'object' || Array.isArray(body.state)) {
    return json({ error: 'bad state' }, 400, env);
  }
  const incoming = sanitizeState(body.state);
  // 防止旧设备把服务端已触发的提醒覆盖回未触发
  const oldRow = await env.DB.prepare('SELECT data FROM states WHERE user_id=?').bind(user.id).first();
  if (oldRow && Array.isArray(incoming.alerts)) {
    try {
      const oldState = JSON.parse(oldRow.data);
      const oldMap = new Map((oldState.alerts || []).map((a) => [String(a.id), a]));
      incoming.alerts = incoming.alerts.map((a) => {
        const old = oldMap.get(String(a.id));
        return old && old.hit ? { ...a, hit: old.hit } : a;
      });
    } catch (e) {}
  }
  const data = JSON.stringify(incoming);
  if (data.length > 400000) return json({ error: 'state too large' }, 413, env);
  const now = Date.now();
  await env.DB.prepare(
    'INSERT INTO states (user_id,data,updated_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at',
  ).bind(user.id, data, now).run();
  return json({ ok: true, updatedAt: now }, 200, env);
}

/* 提醒方向判定:above/below 比较最新价,pct_up/pct_down 比较当日涨跌幅(%)。
   四分支必须显式穷举 —— 曾经用 `dir === 'above' ? ... : price <= a.price` 二元写法,
   导致 pct_up/pct_down 落进 else 分支:高价股 price <= 阈值 恒 false(静默失效),
   低价股立即命中(与涨跌幅无关地误发邮件)。 */
/* 邮件 HTML 转义:拼进模板的动态片段一律先过这里(纵深防御,防止后续新增字段时重演注入) */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function alertHit(a, q) {
  const thr = Number(a.price);
  if (!Number.isFinite(thr)) return false;
  if (a.dir === 'above') return q.price >= thr;
  if (a.dir === 'below') return q.price <= thr;
  if (!Number.isFinite(q.chgPct)) return false;
  if (a.dir === 'pct_up') return q.chgPct >= thr;
  if (a.dir === 'pct_down') return q.chgPct <= -thr;
  return false;
}
function alertLine(a, q) {
  const thr = Number(a.price);
  if (a.dir === 'pct_up') return `${a.code} 涨幅 ${q.chgPct.toFixed(2)}% ≥ ${thr}%`;
  if (a.dir === 'pct_down') return `${a.code} 跌幅 ${(-q.chgPct).toFixed(2)}% ≥ ${thr}%`;
  if (a.dir === 'above') return `${a.code} 突破 ${thr}(现价 ${q.price})`;
  return `${a.code} 跌破 ${thr}(现价 ${q.price})`;
}

const ALERT_CURSOR_KEY = 'alert_cursor';

/* 单轮代码配额是全局共享的:所有用户的代码汇成一个集合后截断。
   若固定截断前 800 个,第 801+ 个永远轮不到(插入序稳定),
   5 个账号 × 200 条垃圾代码就能让全站真实提醒永久静默。
   这里用 cache 表存游标做环形窗口,保证每个代码在 ceil(N/800) 轮内必被查到。
   游标读写失败只影响起点,不影响本轮提醒本身。 */
async function rotateAlertCodes(env, codes) {
  const total = codes.length;
  if (total <= MAX_ALERT_CODES) return codes;
  let cursor = 0;
  try {
    const row = await env.DB.prepare('SELECT payload FROM cache WHERE key=?').bind(ALERT_CURSOR_KEY).first();
    if (row) cursor = Number(row.payload) || 0;
  } catch (e) { /* 读不到就从 0 开始 */ }
  const offset = ((cursor % total) + total) % total;
  try {
    await env.DB.prepare(
      'INSERT INTO cache (key,payload,updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at',
    ).bind(ALERT_CURSOR_KEY, String(offset + MAX_ALERT_CODES), Date.now()).run();
  } catch (e) { /* 写失败只影响下一轮起点 */ }
  return codes.slice(offset).concat(codes.slice(0, offset)).slice(0, MAX_ALERT_CODES);
}

async function handleAlerts(env) {
  const { results } = await env.DB.prepare(
    'SELECT s.user_id,s.data,u.email FROM states s JOIN users u ON u.id=s.user_id LIMIT 1000',
  ).all();
  if (!results || !results.length) return { checked: 0, hit: 0, mailed: 0 };
  const allCodes = new Set();
  const parsed = results.map((r) => {
    let state = {};
    try { state = JSON.parse(r.data); } catch (e) {}
    const active = Array.isArray(state.alerts) ? state.alerts.filter((a) => a && !a.hit && a.code) : [];
    active.forEach((a) => allCodes.add(String(a.code)));
    return { row: r, state, active };
  });
  if (!allCodes.size) return { checked: 0, hit: 0, mailed: 0 };
  const quote = {};
  const codes = Array.from(allCodes);
  // 总量闸 + 轮转:超出部分本轮不查。没有这道闸,一条塞了几千个代码的 state 就能让
  // 子请求数冲破免费版 50 次上限、整个 cron 抛错,全站提醒停摆。
  // 但只截断不轮转会让尾部代码永远饿死,所以用环形窗口按轮次推进游标。
  if (codes.length > MAX_ALERT_CODES) {
    console.warn(`[cron] 提醒代码 ${codes.length} 个,超过单轮上限 ${MAX_ALERT_CODES},本轮轮转检查 ${MAX_ALERT_CODES} 个`);
  }
  const picked = await rotateAlertCodes(env, codes);
  for (let i = 0; i < picked.length; i += 40) {
    const chunk = picked.slice(i, i + 40);
    const secids = chunk.map(secid).filter(Boolean);
    if (!secids.length) continue;
    const url = 'https://push2.eastmoney.com/api/qt/ulist.np/get?secids=' + secids.join(',') +
      '&fields=f2,f3,f12&fltt=2&invt=2&ut=' + UT;
    try {
      const res = await fetch(url, {
        headers: { 'User-Agent': 'Mozilla/5.0', Referer: 'https://quote.eastmoney.com/' },
      });
      const j = await res.json();
      const diff = j && j.data && j.data.diff;
      if (Array.isArray(diff)) {
        diff.forEach((d) => {
          const code = String(d.f12);
          /* f3 是当日涨跌幅(%),百分比提醒要用;f2 是最新价。两个字段一起存。 */
          const q = { price: Number(d.f2), chgPct: Number(d.f3) };
          quote[code] = q;
          quote[code.padStart(6, '0')] = q;
        });
      }
    } catch (e) {}
    await sleep(120);
  }
  let hitCount = 0, mailed = 0, mailAttempts = 0, mailDeferred = 0;
  const mailOn = !!(env.RESEND_API_KEY && env.ALERT_FROM);
  for (const item of parsed) {
    if (!item.active.length) continue;
    const hits = [];
    item.active.forEach((a) => {
      const q = quote[String(a.code)];
      if (!q || !(q.price > 0)) return;
      if (!alertHit(a, q)) return;
      hits.push({ alert: a, line: alertLine(a, q) });
    });
    if (!hits.length) continue;
    /* 发信预算:每命中 1 个用户 = 1 次子请求,而免费版单轮上限只有 50 次。
       超预算时整用户顺延(不写 hit、不落库),下一轮会重新判定,
       否则「标了 hit 却发不出信」等于静默吞掉这条提醒。 */
    if (mailOn && mailAttempts >= MAX_MAILS_PER_ROUND) { mailDeferred++; continue; }
    const now = Date.now();
    hits.forEach((h) => { h.alert.hit = now; hitCount++; });
    await env.DB.prepare('UPDATE states SET data=?,updated_at=? WHERE user_id=?')
      .bind(JSON.stringify(item.state), now, item.row.user_id).run();
    if (mailOn) {
      mailAttempts++;
      try {
        const res = await fetch('https://api.resend.com/emails', {
          method: 'POST',
          headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            from: env.ALERT_FROM,
            to: [item.row.email],
            subject: '观潮 · 价格提醒已触发',
            html: `<div style="font-family:system-ui;padding:20px">
              <h2 style="margin:0 0 12px">价格提醒</h2>
              <p style="color:#555;line-height:1.7">${hits.map((h) => esc(h.line)).join('<br>')}</p>
              <p style="color:#999;font-size:12px;margin-top:20px">来自观潮 · 本邮件由你的自建 Worker 发送。</p>
            </div>`,
          }),
        });
        if (res.ok) mailed++;
      } catch (e) {}
    }
  }
  if (mailDeferred) {
    console.warn(`[cron] 本轮发信达上限 ${MAX_MAILS_PER_ROUND},${mailDeferred} 个用户顺延到下一轮`);
  }
  return { checked: results.length, hit: hitCount, mailed, deferred: mailDeferred };
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const path = url.pathname.replace(/\/+$/, '') || '/';
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(env) });
    try {
      if (path === '/api/health') return json({ ok: true, now: Date.now() }, 200, env);
      if (path === '/api/register' && req.method === 'POST') return jsonOnly(req, env) || register(req, env);
      if (path === '/api/login' && req.method === 'POST') return jsonOnly(req, env) || login(req, env);
      if (path === '/api/snapshot' && req.method === 'GET') return handleSnapshot(env, Number(url.searchParams.get('part')) || 1);

      if (path === '/api/state' || path === '/api/me' || path === '/api/logout') {
        const user = await authUser(req, env);
        if (!user) return json({ error: 'unauthorized' }, 401, env);
        if (path === '/api/me' && req.method === 'GET') return json({ ok: true }, 200, env);
        if (path === '/api/logout' && req.method === 'POST') {
          await env.DB.prepare('DELETE FROM sessions WHERE token=?').bind(user.token).run();
          return json({ ok: true }, 200, env);
        }
        if (path === '/api/state' && req.method === 'GET') return getState(req, env, user);
        if (path === '/api/state' && (req.method === 'PUT' || req.method === 'POST')) {
          return jsonOnly(req, env) || putState(req, env, user);
        }
      }
      return json({ error: 'not found' }, 404, env);
    } catch (e) {
      return json({ error: 'server error', detail: String(e && e.message || e) }, 500, env);
    }
  },

  async scheduled(event, env, ctx) {
    // waitUntil 里的 promise 若 reject 会被平台吞掉,这里必须自己兜住并留痕,
    // 否则任何一次提醒检查失败在运维视角都是完全静默的。
    ctx.waitUntil((async () => {
      try {
        const r = await handleAlerts(env);
        console.log('[cron] alerts', JSON.stringify(r));
        return r;
      } catch (e) {
        console.error('[cron] handleAlerts failed', e && e.stack || e);
      }
    })());
  },
};

/* 供单元测试直接调用(纯函数,无副作用);Workers 允许多个具名导出。 */
export { alertHit, alertLine, esc };
