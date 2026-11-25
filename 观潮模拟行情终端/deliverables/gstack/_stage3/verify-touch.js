const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  for (const vp of [{ width: 375, height: 812 }, { width: 414, height: 896 }]) {
    const ctx = await b.newContext({ viewport: vp });
    const p = await ctx.newPage();
    await p.goto(FILE, { waitUntil: 'load' });
    await p.waitForTimeout(900);
    const r = await p.evaluate(() => {
      const els = [...document.querySelectorAll('a, button, input, select, [role="button"]')].filter((e) => {
        const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
        return cs.display !== "none" && cs.visibility !== "hidden" && cs.pointerEvents !== "none" && r.width > 0 && (r.width < 48 || r.height < 48);
      });
      const below44 = els.filter((e) => { const r = e.getBoundingClientRect(); return r.width < 44 || r.height < 44; });
      return {
        total: els.length,
        below44: below44.map((e) => ({ s: (e.id ? '#' + e.id : '') + '.' + String(e.className).split(' ').slice(0, 2).join('.'), w: Math.round(e.getBoundingClientRect().width), h: Math.round(e.getBoundingClientRect().height), t: (e.textContent || '').trim().slice(0, 8) })),
        overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    ok(`${vp.width} below44=0`, r.below44.length === 0, `剩余 ${r.below44.length}: ${JSON.stringify(r.below44.slice(0, 8))}`);
    ok(`${vp.width} 无横向溢出`, r.overflowX <= 0, `overflowX=${r.overflowX}px (总 ${r.total} 个 <48, 达标口径 44)`);
    await ctx.close();
  }
  // selftest
  const ctx = await b.newContext({ viewport: { width: 375, height: 812 } });
  const p = await ctx.newPage();
  await p.goto(FILE + '?selftest', { waitUntil: 'load' });
  await p.waitForTimeout(3000);
  const st = await p.evaluate(() => (document.querySelector('#selfTestPanel b') || { textContent: 'panel missing' }).textContent);
  /* 口径:断言「全通过且总数不缩水」,别硬编码 40/40 */
  const mm = st.match(/自检 (\d+)\/(\d+)/);
  const allPass = !!mm && mm[1] === mm[2] && Number(mm[2]) >= 46;
  ok('selftest 全通过(≥46)', allPass, st);
  // 桌面 1440 回归:触摸块不影响桌面(桌面无 44 需求,但确认无溢出)
  const d = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const pd = await d.newPage();
  await pd.goto(FILE, { waitUntil: 'load' });
  await pd.waitForTimeout(800);
  const ov = await pd.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok('1440 无横向溢出', ov <= 0, `overflowX=${ov}px`);
  await b.close();
  console.log(fail ? `\n*** ${fail} FAILED ***` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
