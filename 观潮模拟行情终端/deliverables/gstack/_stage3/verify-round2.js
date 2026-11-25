/* 阶段三第二轮修复验证:
   C6 抽屉 .24s / C5 浮层避让 / C3 移动菜单 elevation / R3 hero 可点 / R5 提醒回跳 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (name, cond, detail) => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}  ${detail}`);
  if (!cond) fail++;
};
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });

  /* --- 桌面 1440:抽屉时长 + 浮层几何 + hero 可点 --- */
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(800);

  // C6: CSS 声明值 + transitionend 计时(后者含内容渲染同步耗时,仅作参考)
  const dur = await p.evaluate(async () => {
    const d = document.querySelector('#drawer');
    const declared = getComputedStyle(d).transitionDuration;
    let ms = -1;
    const onEnd = (e) => { if (e.propertyName === 'transform' && e.target === d) ms = Math.round(performance.now() - t0); };
    d.addEventListener('transitionend', onEnd, { once: true });
    const t0 = performance.now();
    window.openDrawer('300750');
    await new Promise((r) => setTimeout(r, 900));
    return { declared, ms };
  });
  ok('C6 drawer 时长声明', dur.declared.includes('0.24'), `transition-duration=${dur.declared}, transitionend=${dur.ms}ms(含渲染)`);

  // C5: signal-chip 几何
  const chip = await p.evaluate(() => {
    const c = document.querySelector('.signal-chip').getBoundingClientRect();
    const card = document.querySelector('.chart-card').getBoundingClientRect();
    const cv = document.querySelector('#heroChart').getBoundingClientRect();
    return { chipL: c.left, chipB: c.bottom, cardL: card.left, cardR: card.right, cvB: cv.bottom, overflowL: card.left - c.left, overflowR: c.right - card.right, axisGap: cv.bottom - c.bottom };
  });
  ok('C5 chip 无左溢出', chip.overflowL <= 0, `overflowL=${chip.overflowL}px`);
  ok('C5 chip 无右溢出', chip.overflowR <= 0, `overflowR=${chip.overflowR}px`);
  ok('C5 chip 距画布下沿 ≥32px', chip.axisGap >= 32, `axisGap=${Math.round(chip.axisGap)}px`);

  // R3: hero cc-sym 点击开抽屉
  await p.keyboard.press('Escape');
  await p.evaluate(() => window.closeDrawer && window.closeDrawer());
  await p.waitForTimeout(400);
  await p.click('#heroSym');
  await p.waitForTimeout(500);
  const heroOpens = await p.evaluate(() => {
    const d = document.querySelector('#drawer');
    const name = document.querySelector('#drawerName').textContent;
    return { on: d.classList.contains('is-on'), name, code: (window.DRAWER_CODE || '') };
  });
  ok('R3 hero 点击开抽屉', heroOpens.on, `drawerName=${heroOpens.name}`);
  await p.keyboard.press('Escape');
  await p.evaluate(() => window.closeDrawer && window.closeDrawer());
  await p.waitForTimeout(400);
  await ctx.close();

  /* --- 移动 375:菜单 elevation + 提醒回跳 --- */
  const ctx2 = await b.newContext({ viewport: { width: 375, height: 812 } });
  const p2 = await ctx2.newPage();
  await p2.goto(FILE, { waitUntil: 'load' });
  await p2.waitForTimeout(800);

  // C3: 打开移动菜单看背景/边框/投影
  await p2.click('#mobileMenu');
  await p2.waitForTimeout(400);
  let menu = await p2.evaluate(() => {
    const m = document.querySelector('.nav-links.is-open');
    if (!m) return null;
    const cs = getComputedStyle(m);
    return { bg: cs.backgroundColor, bw: cs.borderBottomWidth, bc: cs.borderBottomColor, sh: cs.boxShadow };
  });
  if (!menu) { // 试着点汉堡按钮
    await p2.evaluate(() => { const t = document.querySelector('.nav .icon-btn'); if (t) t.click(); });
    await p2.waitForTimeout(400);
    menu = await p2.evaluate(() => {
      const m = document.querySelector('.nav-links.is-open');
      if (!m) return null;
      const cs = getComputedStyle(m);
      return { bg: cs.backgroundColor, bw: cs.borderBottomWidth, sh: cs.boxShadow };
    });
  }
  ok('C3 移动菜单浮层化', !!menu && menu.bg === 'rgb(255, 255, 255)' && parseFloat(menu.bw) > 0 && menu.sh !== 'none', JSON.stringify(menu));

  await p2.evaluate(() => document.body.click());
  await p2.waitForTimeout(300);

  // R5: 造一条提醒,点行应关提醒面板开个股抽屉
  const r5 = await p2.evaluate(async () => {
    const code = '600519';
    window.openAlerts();
    await new Promise((r) => setTimeout(r, 500));
    const input = document.querySelector('#alertCode, .alert-form input');
    if (!input) return { err: 'no alert form input' };
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(input, code);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 200));
    const addBtn = [...document.querySelectorAll('.alert-form button')].find((x) => x.textContent.includes('添加') || x.type === 'submit');
    if (addBtn) addBtn.click();
    await new Promise((r) => setTimeout(r, 500));
    const row = document.querySelector('.alert-item[data-code]');
    if (!row) return { err: 'no alert row with data-code' };
    row.click();
    await new Promise((r) => setTimeout(r, 600));
    return {
      alertClosed: !document.querySelector('#alertDrawer').classList.contains('is-on'),
      drawerOn: document.querySelector('#drawer').classList.contains('is-on'),
      drawerName: document.querySelector('#drawerName').textContent,
    };
  });
  ok('R5 提醒回跳', !r5.err && r5.alertClosed && r5.drawerOn, JSON.stringify(r5));

  // selftest:读自检面板标题
  await p2.goto(FILE + '?selftest', { waitUntil: 'load' });
  await p2.waitForTimeout(3000);
  const st = await p2.evaluate(() => {
    const el = document.querySelector('#selfTestPanel b');
    return el ? el.textContent : 'selftest panel not found';
  });
  /* 口径:断言「全通过且总数不缩水」,别硬编码 40/40——每轮新增用例都会让硬编码失效 */
  const mm = st.match(/自检 (\d+)\/(\d+)/);
  const allPass = !!mm && mm[1] === mm[2] && Number(mm[2]) >= 46;
  ok('selftest 全通过(≥46)', allPass, st);
  await ctx2.close();
  await b.close();
  console.log(fail ? `\n*** ${fail} FAILED ***` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
