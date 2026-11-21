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

const enc = new TextEncoder();

const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Cache-Control': 'no-store',
  'Cross-Origin-Resource-Policy': 'same-site',
};

function cors(env) {
  // 未配置 ALLOWED_ORIGIN 时不返回 CORS 头,浏览器会拒绝跨域调用(默认拒绝)。
  const h = {
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    Vary: 'Origin',
    ...SECURITY_HEADERS,
  };
  if (env && env.ALLOWED_ORIGIN) h['Access-Control-Allow-Origin'] = env.ALLOWED_ORIGIN;
  return h;
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

// 登录限流:按「邮箱」和「来源 IP」两个维度计数,窗口内失败达到上限即锁定。
async function loginGate(env, keys) {
  const now = Date.now();
  for (const k of keys) {
    const r = await env.DB.prepare('SELECT fails,first_at,locked_until FROM login_attempts WHERE key=?').bind(k).first();
    if (r && r.locked_until > now) return Math.ceil((r.locked_until - now) / 1000);
  }
  return 0;
}
async function loginFail(env, keys) {
  const now = Date.now();
  for (const k of keys) {
    const r = await env.DB.prepare('SELECT fails,first_at FROM login_attempts WHERE key=?').bind(k).first();
    let fails = 1, first = now, lock = 0;
    if (r && now - r.first_at < LOGIN_WINDOW_MS) { fails = r.fails + 1; first = r.first_at; }
    if (fails >= LOGIN_MAX_FAILS) lock = now + LOGIN_LOCK_MS;
    await env.DB.prepare(
      'INSERT INTO login_attempts (key,fails,first_at,locked_until) VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET fails=excluded.fails, first_at=excluded.first_at, locked_until=excluded.locked_until',
    ).bind(k, fails, first, lock).run();
  }
}
async function loginClear(env, keys) {
  for (const k of keys) await env.DB.prepare('DELETE FROM login_attempts WHERE key=?').bind(k).run();
}

async function login(req, env) {
  const body = await readBody(req);
  if (!body) return json({ error: 'bad json' }, 400, env);
  const email = String(body.email || '').trim().toLowerCase();
  const password = String(body.password || '');
  if (!email || password.length > 72) return json({ error: '邮箱或密码错误' }, 401, env);
  const ip = req.headers.get('CF-Connecting-IP') || 'unknown';
  const keys = ['e:' + email, 'i:' + ip];
  const wait = await loginGate(env, keys);
  if (wait > 0) {
    return json({ error: `尝试次数过多,请 ${Math.ceil(wait / 60)} 分钟后再试` }, 429, env, { 'Retry-After': String(wait) });
  }
  const user = await env.DB.prepare('SELECT id,email,salt,pass_hash,iterations FROM users WHERE email=?')
    .bind(email).first();
  const iters = user ? (Number(user.iterations) || LEGACY_ITER) : PBKDF2_ITER;
  // 用户不存在时同样做一次哈希,避免响应时间暴露邮箱是否已注册
  const hash = await hashPassword(password, user ? user.salt : b64(new Uint8Array(16)), iters);
  if (!user || !timingSafeEqual(hash, user.pass_hash)) {
    await loginFail(env, keys);
    return json({ error: '邮箱或密码错误' }, 401, env);
  }
  await loginClear(env, keys);
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

async function putState(req, env, user) {
  const body = await readBody(req);
  if (!body || !body.state || typeof body.state !== 'object') {
    return json({ error: 'bad state' }, 400, env);
  }
  const incoming = body.state;
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
const ALERT_DIRS = new Set(['above', 'below', 'pct_up', 'pct_down']);
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
  for (let i = 0; i < codes.length; i += 40) {
    const chunk = codes.slice(i, i + 40);
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
  let hitCount = 0, mailed = 0;
  for (const item of parsed) {
    if (!item.active.length) continue;
    const changed = [];
    item.active.forEach((a) => {
      const q = quote[String(a.code)];
      if (!q || !(q.price > 0)) return;
      if (!alertHit(a, q)) return;
      a.hit = Date.now();
      changed.push(alertLine(a, q));
      hitCount++;
    });
    if (!changed.length) continue;
    const now = Date.now();
    await env.DB.prepare('UPDATE states SET data=?,updated_at=? WHERE user_id=?')
      .bind(JSON.stringify(item.state), now, item.row.user_id).run();
    if (env.RESEND_API_KEY && env.ALERT_FROM) {
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
              <p style="color:#555;line-height:1.7">${changed.join('<br>')}</p>
              <p style="color:#999;font-size:12px;margin-top:20px">来自观潮 · 本邮件由你的自建 Worker 发送。</p>
            </div>`,
          }),
        });
        if (res.ok) mailed++;
      } catch (e) {}
    }
  }
  return { checked: results.length, hit: hitCount, mailed };
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const path = url.pathname.replace(/\/+$/, '') || '/';
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(env) });
    try {
      if (path === '/api/health') return json({ ok: true, now: Date.now() }, 200, env);
      if (path === '/api/register' && req.method === 'POST') return register(req, env);
      if (path === '/api/login' && req.method === 'POST') return login(req, env);
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
        if (path === '/api/state' && (req.method === 'PUT' || req.method === 'POST')) return putState(req, env, user);
      }
      return json({ error: 'not found' }, 404, env);
    } catch (e) {
      return json({ error: 'server error', detail: String(e && e.message || e) }, 500, env);
    }
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(handleAlerts(env));
  },
};

/* 供单元测试直接调用(纯函数,无副作用);Workers 允许多个具名导出。 */
export { alertHit, alertLine };
