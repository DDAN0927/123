/* 后端数据桥验收探针。
 *
 * 覆盖三个场景（缺一不可，否则"接了后端"可能是以破坏离线为代价的）：
 *   A. 同源访问 → 自动探测后端，data-source=server，且序列数值与 API 逐根一致
 *   B. ?api=off → 强制本地，selftest 仍 46/46
 *   C. file:// 打开 → 默认本地（离线可用），不发起无效请求
 *
 * 前置：后端已启动于 127.0.0.1:8000
 * 用法：cd deliverables/gstack/_stage3 && node verify-api-bridge.js
 */
const path = require('path');
const { chromium } = require(path.resolve(__dirname, '..', '_baseline', 'node_modules', 'playwright'));

const BASE = 'http://127.0.0.1:8000';
const ROOT = path.resolve(__dirname, '..', '..', '..');
const FILE_URL = 'file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/');

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

async function apiBars(code, limit) {
  const r = await fetch(`${BASE}/api/market/bars?code=${code}&limit=${limit || 1300}`);
  return r.json();
}

(async () => {
  const browser = await chromium.launch({ channel: 'msedge' });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));

  /* ---------- A. 同源自动接入 ---------- */
  console.log('===== A. 同源访问自动接入后端 =====');
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  /* 必须等到同步真正结束（synced 被写入）再断言：
     mark('server') 在同步开始前就设了，只等它命中会读到半程状态。 */
  const synced = await page
    .waitForFunction(
      () => window.QF_API && typeof window.QF_API.synced === 'number',
      { timeout: 40000 }
    )
    .then(() => true)
    .catch(() => false);
  ok('A 同步流程执行完毕', synced, 'QF_API.synced 未写入');

  const snap = await page.evaluate(() => {
    const s = typeof CURATED !== 'undefined' ? CURATED[0] : null;
    return {
      src: document.documentElement.dataset.dataSource,
      api: window.QF_API || null,
      code: s ? s.code : null,
      n: s && s.series ? s.series.length : 0,
      lastC: s && s.series ? s.series[s.series.length - 1].c : null,
      srcTag: s ? s._src || null : null,
      firstT: s && s.series ? s.series[0].t.getFullYear() + '-' + (s.series[0].t.getMonth() + 1) : null,
      intraday: s && s.series && s.series[0].intraday ? true : false,
    };
  });
  ok('A QF_API.mode = server', snap.api && snap.api.mode === 'server', JSON.stringify(snap.api));
  ok('A provider 声明为 mock（不冒充真实行情）', snap.api && snap.api.provider === 'mock', snap.api && snap.api.provider);
  ok('A 全部 31 只同步成功', snap.api && snap.api.synced === 31 && snap.api.failed === 0,
    snap.api ? `synced=${snap.api.synced} failed=${snap.api.failed}` : 'no api');
  ok('A 序列带 _src=api 标记（证明确实来自后端）', snap.srcTag === 'api', 'srcTag=' + snap.srcTag);
  ok('A 序列长度为 1300（未截断，5Y 区间可用）', snap.n === 1300, 'n=' + snap.n);

  const ref = await apiBars(snap.code, 5);
  const refLast = ref.data[ref.data.length - 1];
  ok('A 末根收盘价与后端一致', Math.abs(snap.lastC - refLast.c) < 1e-9,
    `页面=${snap.lastC} 后端=${refLast.c}`);

  /* 抽查 5 根逐字段比对：页面 series 尾部 vs 后端 bars 尾部 */
  const tail = await page.evaluate((code) => {
    const s = BY_CODE[code];
    if (!s || !s.series) return null;
    return s.series.slice(-5).map((b) => ({
      t: `${b.t.getFullYear()}-${String(b.t.getMonth() + 1).padStart(2, '0')}-${String(b.t.getDate()).padStart(2, '0')}`,
      o: b.o, h: b.h, l: b.l, c: b.c, v: b.v,
    }));
  }, snap.code);

  let maxRel = 0;
  let dateBad = 0;
  for (let i = 0; i < ref.data.length; i++) {
    const a = tail[i];
    const b = ref.data[i];
    if (!a) { dateBad++; continue; }
    if (a.t !== b.t) dateBad++;
    for (const k of ['o', 'h', 'l', 'c', 'v']) {
      const d = Math.abs(a[k] - b[k]) / Math.max(Math.abs(a[k]), Math.abs(b[k]), 1e-12);
      if (d > maxRel) maxRel = d;
    }
  }
  ok('A 尾部 5 根日期全对齐', dateBad === 0, 'mismatch=' + dateBad);
  ok('A 尾部 5 根数值一致(<1e-12)', maxRel < 1e-12, 'maxRel=' + maxRel.toExponential(2));
  ok('A 页面无 JS 错误', errs.length === 0, errs.slice(0, 2).join(' | '));

  /* ---------- B. ?api=off 强制本地 ---------- */
  console.log('===== B. ?api=off 强制本地 =====');
  const p2 = await ctx.newPage();
  const errs2 = [];
  p2.on('pageerror', (e) => errs2.push(e.message));
  await p2.goto(BASE + '/?api=off&selftest', { waitUntil: 'domcontentloaded' });
  await p2.waitForSelector('#selfTestPanel', { timeout: 20000 }).catch(() => {});
  const b = await p2.evaluate(() => {
    const head = document.querySelector('#selfTestPanel b');
    return {
      src: document.documentElement.dataset.dataSource,
      api: window.QF_API || null,
      st: head ? head.textContent.trim() : '',
    };
  });
  ok('B data-source=local', b.src === 'local', b.src);
  ok('B 未创建 QF_API（完全不走后端）', b.api === null, JSON.stringify(b.api));
  const m = b.st.match(/(\d+)\s*\/\s*(\d+)/);
  ok('B selftest 仍为 N/N 且 N≥46', !!m && m[1] === m[2] && Number(m[2]) >= 46, b.st);
  ok('B 无 JS 错误', errs2.length === 0, errs2.slice(0, 2).join(' | '));

  /* ---------- C. file:// 离线回退 ---------- */
  console.log('===== C. file:// 离线打开 =====');
  const p3 = await ctx.newPage();
  const errs3 = [];
  p3.on('pageerror', (e) => errs3.push(e.message));
  await p3.goto(FILE_URL, { waitUntil: 'domcontentloaded' });
  await p3.waitForTimeout(1500);
  const c = await p3.evaluate(() => {
    const s = typeof CURATED !== 'undefined' ? CURATED[0] : null;
    return {
      src: document.documentElement.dataset.dataSource,
      api: window.QF_API || null,
      n: s && s.series ? s.series.length : 0,
      lastC: s && s.series ? s.series[s.series.length - 1].c : null,
    };
  });
  ok('C data-source=local（离线不尝试跨域）', c.src === 'local', c.src);
  ok('C 本地序列照常生成 1300 根', c.n === 1300, 'n=' + c.n);
  ok('C 本地末价 = 1624.5（与后端同值）', Math.abs(c.lastC - 1624.5) < 1e-9, 'last=' + c.lastC);
  ok('C 无 JS 错误', errs3.length === 0, errs3.slice(0, 2).join(' | '));

  await browser.close();
  console.log(`\n结果: ${pass}/${pass + fail} 通过`);
  if (fail) console.log('存在失败项');
  process.exit(fail ? 1 : 0);
})().catch((e) => {
  console.error('探针异常:', e);
  process.exit(1);
});
