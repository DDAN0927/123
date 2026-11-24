/* 部署链路验收探针（前后端分离后的「能不能被访问」这条腿）。
 *
 * 为什么需要它：功能探针全绿不等于能部署。之前 backend/README 的待办里躺着
 * "依赖声明 / 进程入口 / 鉴权 / 持久化"四条，其中前三条只要有一个缺失，
 * 换台机器就跑不起来。这个探针把「跑得起来」拆成可断言的几步。
 *
 * 覆盖：
 *   A. 制品静检 —— requirements / Procfile / render.yaml / Dockerfile 内容与真实路径一致
 *   B. 无 ACCESS_TOKEN（开发模式）—— 接口放行，但 health 明说 auth.mode=off
 *   C. 有 ACCESS_TOKEN —— health 白名单放行、缺头 401、错 token 401、对 token 200、预检不拦
 *   D. 前端真实接入 —— 无 token 标 denied / ?token= 接入 server 且同步 31 只 /
 *      刷新后靠 localStorage 仍 server / ?api=off 仍 local
 *
 * 用法：cd deliverables/gstack/_stage3 && node verify-deploy.js
 * 退出码 0 = 全过。探针自己起停服务，不依赖外部已启动的后端。
 */
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { chromium } = require(path.resolve(__dirname, '..', '_baseline', 'node_modules', 'playwright'));

const ROOT = path.resolve(__dirname, '..', '..', '..');
const PY = process.env.PYTHON || 'python';
const PORT_OPEN = 18325;
const PORT_LOCK = 18326;
const SECRET = 'probe-token-8f3a1c';

let pass = 0;
let fail = 0;
function ok(name, cond, extra) {
  if (cond) {
    pass++;
    console.log('  PASS', name);
  } else {
    fail++;
    console.log('  FAIL', name, extra == null ? '' : '| ' + extra);
  }
}

function read(rel) {
  const p = path.join(ROOT, rel);
  return fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : null;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function startServer(port, env) {
  const e = { ...process.env };
  delete e.ACCESS_TOKEN;
  Object.assign(e, env || {});
  const child = spawn(PY, ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(port)], {
    cwd: ROOT,
    env: e,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.on('data', () => {});
  child.stderr.on('data', () => {});
  for (let i = 0; i < 60; i++) {
    await sleep(300);
    try {
      const r = await fetch(`http://127.0.0.1:${port}/api/health`, { signal: AbortSignal.timeout(1500) });
      if (r.ok) return child;
    } catch (_) {
      /* 还没起来 */
    }
  }
  child.kill();
  throw new Error('服务在 20s 内未就绪: ' + port);
}

function stopServer(child) {
  try {
    child.kill();
  } catch (_) {
    /* 已退出 */
  }
}

async function get(port, p, headers) {
  const r = await fetch(`http://127.0.0.1:${port}${p}`, {
    headers: headers || {},
    signal: AbortSignal.timeout(15000),
  });
  let body = null;
  try {
    body = await r.json();
  } catch (_) {
    body = null;
  }
  return { status: r.status, body, headers: r.headers };
}

(async () => {
  /* ================= A. 制品静检 ================= */
  console.log('===== A. 部署制品 =====');
  const req = read('backend/requirements.txt');
  ok('A1 requirements.txt 存在', !!req);
  ok('A2 声明 fastapi 且钉版本', /^fastapi==\d+\.\d+\.\d+$/m.test(req || ''), (req || '').split('\n')[1]);
  ok('A3 声明 uvicorn[standard] 且钉版本', /^uvicorn\[standard\]==\d+\.\d+\.\d+$/m.test(req || ''));
  ok('A4 声明 pydantic 且钉版本', /^pydantic==\d+\.\d+\.\d+$/m.test(req || ''));

  const proc = read('Procfile');
  ok('A5 Procfile 存在', !!proc);
  ok('A6 Procfile 读 $PORT（写死端口在云端会 502）', /\$PORT/.test(proc || ''));
  ok('A7 Procfile 绑 0.0.0.0', /--host\s+0\.0\.0\.0/.test(proc || ''));
  ok('A8 Procfile 不带 --reload', !/--reload/.test(proc || ''));

  const ry = read('render.yaml');
  ok('A9 render.yaml 存在', !!ry);
  ok('A10 healthCheckPath 是真实存在的 /api/health', /healthCheckPath:\s*\/api\/health/.test(ry || ''));
  ok('A11 buildCommand 装的是同一份 requirements', /pip install -r backend\/requirements\.txt/.test(ry || ''));
  ok('A12 startCommand 绑 0.0.0.0 且读 $PORT', /0\.0\.0\.0/.test(ry || '') && /\$PORT/.test(ry || ''));
  ok('A13 ACCESS_TOKEN 不在仓库里存明文', /key:\s*ACCESS_TOKEN[\s\S]{0,80}sync:\s*false/.test(ry || ''));

  const df = read('backend/Dockerfile');
  ok('A14 Dockerfile 存在', !!df);
  ok('A15 Dockerfile 从仓库根拷 index.html（只拷 backend/ 首页会 404）', /COPY index\.html/.test(df || ''));
  ok('A16 Dockerfile 用 ${PORT:-8000} 而非写死', /\$\{PORT:-8000\}/.test(df || ''));
  /* 断言只看 CMD 那一行：注释里可以为了解释而提到 --reload，
     整文件搜关键词会让"解释清楚"和"写错了"被判成同一个结果。 */
  const cmdLine = (df || '').split(/\r?\n/).filter((l) => /^\s*CMD\b/.test(l)).join(' ');
  ok('A17 Dockerfile 的 CMD 不带 --reload', !!cmdLine && !/--reload/.test(cmdLine), cmdLine);
  ok('A18 .dockerignore 排除 deliverables', /deliverables/.test(read('.dockerignore') || ''));
  ok('A19 .env.example 说明 ACCESS_TOKEN 语义', /ACCESS_TOKEN/.test(read('backend/.env.example') || ''));

  /* 依赖版本必须与实测环境一致：换版本要重跑前后端数值一致性测试 */
  const inst = await new Promise((resolve) => {
    const c = spawn(PY, ['-c', 'import fastapi,uvicorn,pydantic;print(fastapi.__version__,uvicorn.__version__,pydantic.VERSION)'], {
      env: process.env,
    });
    let out = '';
    c.stdout.on('data', (d) => (out += d));
    c.on('close', () => resolve(out.trim()));
  });
  const [fV, uV, pV] = inst.split(/\s+/);
  ok('A20 钉的版本 = 实测运行版本', (req || '').includes(`fastapi==${fV}`) && (req || '').includes(`uvicorn[standard]==${uV}`) && (req || '').includes(`pydantic==${pV}`), inst);

  /* ================= B. 开发模式（无 token） ================= */
  console.log('===== B. 无 ACCESS_TOKEN（开发模式） =====');
  let child = await startServer(PORT_OPEN, {});
  const hOpen = await get(PORT_OPEN, '/api/health');
  ok('B1 health 200', hOpen.status === 200, hOpen.status);
  ok('B2 auth.mode = off（不假装自己是安全的）', hOpen.body && hOpen.body.auth && hOpen.body.auth.mode === 'off', JSON.stringify(hOpen.body && hOpen.body.auth));
  ok('B3 auth.note 明说无鉴权', !!(hOpen.body && hOpen.body.auth && /无鉴权/.test(hOpen.body.auth.note || '')));
  ok('B4 data_is_simulated 仍为 true', !!(hOpen.body && hOpen.body.checks && hOpen.body.checks.data_is_simulated === true));
  const uOpen = await get(PORT_OPEN, '/api/market/universe');
  ok('B5 无 token 也能取行情（本机开发不该被拦）', uOpen.status === 200 && Array.isArray(uOpen.body.data), uOpen.status);
  stopServer(child);

  /* ================= C. 鉴权开启 ================= */
  console.log('===== C. 有 ACCESS_TOKEN（对外部署态） =====');
  child = await startServer(PORT_LOCK, { ACCESS_TOKEN: SECRET });
  const hLock = await get(PORT_LOCK, '/api/health');
  ok('C1 health 仍在白名单内（探活不能被拦）', hLock.status === 200, hLock.status);
  ok('C2 auth.mode = bearer', hLock.body && hLock.body.auth && hLock.body.auth.mode === 'bearer');
  ok('C3 auth 自描述里列出开放路径', !!(hLock.body && hLock.body.auth && (hLock.body.auth.open_paths || []).includes('/api/health')));

  const uNo = await get(PORT_LOCK, '/api/market/universe');
  ok('C4 缺 Authorization → 401', uNo.status === 401, uNo.status);
  ok('C5 401 带 WWW-Authenticate: Bearer', /Bearer/.test(uNo.headers.get('www-authenticate') || ''));
  ok('C6 401 文案区分「没带」（不是笼统的 403）', !!(uNo.body && /缺少/.test(uNo.body.detail || '')), JSON.stringify(uNo.body));

  const uBad = await get(PORT_LOCK, '/api/market/universe', { Authorization: 'Bearer wrong-token' });
  ok('C7 错 token → 401', uBad.status === 401, uBad.status);
  ok('C8 错 token 文案与「没带」不同', !!(uBad.body && /不正确/.test(uBad.body.detail || '')), JSON.stringify(uBad.body));
  ok('C9 401 响应不回显期望 token', JSON.stringify(uBad.body).indexOf(SECRET) === -1);

  const uOk = await get(PORT_LOCK, '/api/market/universe', { Authorization: 'Bearer ' + SECRET });
  ok('C10 对 token → 200', uOk.status === 200 && Array.isArray(uOk.body.data), uOk.status);
  const altOk = await get(PORT_LOCK, '/api/market/universe', { 'X-API-Token': SECRET });
  ok('C11 备用头 X-API-Token 也可用', altOk.status === 200, altOk.status);

  const docs = await get(PORT_LOCK, '/docs');
  ok('C12 /docs 不被拦（否则用户连「怎么带 token」都看不到）', docs.status === 200, docs.status);

  const pre = await fetch(`http://127.0.0.1:${PORT_LOCK}/api/market/universe`, {
    method: 'OPTIONS',
    headers: {
      Origin: 'http://127.0.0.1:9999',
      'Access-Control-Request-Method': 'GET',
      'Access-Control-Request-Headers': 'authorization',
    },
  });
  ok('C13 CORS 预检不返回 401（否则浏览器报成 CORS 错误）', pre.status !== 401, pre.status);
  ok('C14 预检响应带 Allow-Origin', !!pre.headers.get('access-control-allow-origin'));

  const bars = await get(PORT_LOCK, '/api/market/bars?code=600519&limit=10');
  ok('C15 行情接口同样受保护', bars.status === 401, bars.status);

  /* 中间件顺序的实证：401 必须仍带 CORS 头。
     若鉴权注册在 CORS 外层（即后 add），401 没有 Allow-Origin，
     浏览器会把「没权限」报成「CORS 错误」，排查方向直接跑偏。 */
  const r401 = await fetch(`http://127.0.0.1:${PORT_LOCK}/api/market/universe`, {
    headers: { Origin: 'http://127.0.0.1:9999' },
  });
  ok('C16 401 响应仍带 Access-Control-Allow-Origin（证明 CORS 在外层）',
    r401.status === 401 && !!r401.headers.get('access-control-allow-origin'),
    r401.status + ' / ' + r401.headers.get('access-control-allow-origin'));

  /* ================= D. 前端真实接入 ================= */
  console.log('===== D. 前端在鉴权态下的三种表现 =====');
  const BASE = `http://127.0.0.1:${PORT_LOCK}`;
  const browser = await chromium.launch({ channel: 'msedge' });

  /* D-a 不带 token：应当标 denied，且页面照常渲染（本地序列） */
  const c1 = await browser.newContext();
  const p1 = await c1.newPage();
  const errs1 = [];
  p1.on('pageerror', (e) => errs1.push(e.message));
  await p1.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await p1.waitForFunction(() => document.documentElement.dataset.dataSource, { timeout: 20000 }).catch(() => {});
  await sleep(1200);
  const d1 = await p1.evaluate(() => ({
    src: document.documentElement.dataset.dataSource,
    rows: document.querySelectorAll('#portfolio [data-code], .row[data-code]').length,
    rendered: !!document.querySelector('.kpi, .card, main'),
  }));
  ok('D1 无 token 时标 denied（不是 local，两者原因不同）', d1.src === 'denied', d1.src);
  ok('D2 无 token 不白屏（离线回退仍在）', d1.rendered, JSON.stringify(d1));
  ok('D3 无 token 无 JS 报错', errs1.length === 0, errs1.slice(0, 2).join(' / '));
  await c1.close();

  /* D-b 带 ?token=：应当真连上后端并同步完 31 只 */
  const c2 = await browser.newContext();
  const p2 = await c2.newPage();
  const errs2 = [];
  p2.on('pageerror', (e) => errs2.push(e.message));
  await p2.goto(BASE + '/?token=' + SECRET, { waitUntil: 'domcontentloaded' });
  const synced = await p2
    .waitForFunction(() => window.QF_API && typeof window.QF_API.synced === 'number', { timeout: 60000 })
    .then(() => true)
    .catch(() => false);
  ok('D4 带 token 时同步流程跑完', synced, 'QF_API.synced 未写入');
  const d2 = await p2.evaluate(() => ({
    src: document.documentElement.dataset.dataSource,
    api: window.QF_API || null,
    srcFlag: typeof CURATED !== 'undefined' && CURATED[0] ? CURATED[0]._src : null,
  }));
  ok('D5 数据源标 server', d2.src === 'server', d2.src);
  ok('D6 31 只全部同步成功', !!(d2.api && d2.api.synced === 31 && d2.api.failed === 0), JSON.stringify(d2.api && { s: d2.api.synced, f: d2.api.failed }));
  ok('D7 标的真带 _src=api 标记（证明走了后端，不是数值巧合）', d2.srcFlag === 'api', d2.srcFlag);
  ok('D8 带 token 无 JS 报错', errs2.length === 0, errs2.slice(0, 2).join(' / '));

  /* D-c 刷新后不重输 token：localStorage 应记住 */
  const p3 = await c2.newPage();
  await p3.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  const again = await p3
    .waitForFunction(() => window.QF_API && typeof window.QF_API.synced === 'number', { timeout: 60000 })
    .then(() => true)
    .catch(() => false);
  const d3 = await p3.evaluate(() => document.documentElement.dataset.dataSource);
  ok('D9 同源第二次打开仍连上（token 已落 localStorage）', again && d3 === 'server', d3);

  /* D-d ?api=off 永远优先：鉴权态下也能强制离线 */
  const p4 = await c2.newPage();
  await p4.goto(BASE + '/?api=off', { waitUntil: 'domcontentloaded' });
  await sleep(800);
  const d4 = await p4.evaluate(() => document.documentElement.dataset.dataSource);
  ok('D10 ?api=off 仍强制本地（回滚开关不被鉴权破坏）', d4 === 'local', d4);

  await browser.close();
  stopServer(child);

  console.log(`\n合计 ${pass + fail} 条：PASS ${pass} / FAIL ${fail}`);
  process.exit(fail === 0 ? 0 : 1);
})().catch((e) => {
  console.error('探针自身异常:', e && e.stack ? e.stack : e);
  process.exit(2);
});
