const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });

  // —— 场景 1:空状态 ——
  let ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  let p = await ctx.newPage();
  p.on('pageerror', (e) => { fail++; console.log('FAIL  pageerror', e.message); });
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1200);
  await p.evaluate(() => document.getElementById('todayBtn').click());
  await p.waitForTimeout(300);
  let r = await p.evaluate(() => {
    const panel = document.getElementById('todayPanel');
    return {
      on: panel.classList.contains('is-on'),
      empty: /自选与提醒都还是空的/.test(panel.textContent),
      goTerm: !!document.getElementById('todayGoTerm'),
      meta: document.getElementById('todayMeta').textContent,
    };
  });
  ok('空状态:面板打开且有引导文案', r.on && r.empty && r.goTerm, `meta=${r.meta}`);
  await p.evaluate(() => document.getElementById('todayGoTerm').click());
  await p.waitForTimeout(400);
  r = await p.evaluate(() => ({
    closed: !document.getElementById('todayPanel').classList.contains('is-on'),
    favFilter: document.querySelector('#marketSeg button.is-on')?.dataset.market,
  }));
  ok('空状态「去行情终端」引导', r.closed, '');
  await ctx.close();

  // —— 场景 2:自选 + 已触发提醒 + 异动 ——
  ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  p = await ctx.newPage();
  p.on('pageerror', (e) => { fail++; console.log('FAIL  pageerror', e.message); });
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1200);
  await p.evaluate(() => {
    toggleFav('NVDA'); toggleFav('300750'); toggleFav('0700');
    alerts.push({ id: 't1', code: 'NVDA', dir: 'above', price: 1 }); /* 必触发 */
    checkAlerts();
  });
  await p.waitForTimeout(200);
  await p.evaluate(() => document.getElementById('todayBtn').click());
  await p.waitForTimeout(300);
  r = await p.evaluate(() => {
    const host = document.getElementById('todayList');
    const secs = [...host.querySelectorAll('.pf-sec > h4')].map((h) => h.textContent.trim());
    const rows = [...host.querySelectorAll('[data-today]')].map((x) => x.dataset.today);
    return {
      meta: document.getElementById('todayMeta').textContent,
      secs, rows,
      hitShown: /已触发/.test(host.textContent),
      moverShown: /盘中异动/.test(host.textContent),
      btns: !!document.getElementById('todayGoFav') && !!document.getElementById('todayGoAlerts'),
    };
  });
  ok('聚合 meta 行', /个自选/.test(r.meta) && /条提醒/.test(r.meta) && /个异动/.test(r.meta), r.meta);
  ok('三个分区齐全', r.secs.length === 3, JSON.stringify(r.secs));
  ok('已触发提醒进待办', r.hitShown && r.rows.includes('NVDA'), '');
  ok('自选异动分区', r.moverShown, `rows=${r.rows.join(',')}`);
  ok('自选快照含全部自选', ['NVDA', '300750', '0700'].every((c) => r.rows.includes(c)), '');
  ok('底部双按钮', r.btns, '');
  // 点行回跳抽屉
  await p.evaluate(() => { document.querySelector('[data-today="300750"]').click(); });
  await p.waitForTimeout(300);
  r = await p.evaluate(() => ({
    drawer: document.getElementById('drawer').classList.contains('is-on'),
    code: document.querySelector('#drawerSub').textContent.slice(0, 6),
    todayClosed: !document.getElementById('todayPanel').classList.contains('is-on'),
  }));
  ok('点待办行打开个股抽屉', r.drawer && r.todayClosed && r.code.startsWith('300750'), r.code);
  // 「管理提醒」跳提醒抽屉
  await p.keyboard.press('Escape');
  await p.waitForTimeout(200);
  await p.evaluate(() => document.getElementById('todayBtn').click());
  await p.waitForTimeout(200);
  await p.evaluate(() => document.getElementById('todayGoAlerts').click());
  await p.waitForTimeout(300);
  r = await p.evaluate(() => ({
    alerts: document.getElementById('alertDrawer').classList.contains('is-on'),
    today: document.getElementById('todayPanel').classList.contains('is-on'),
  }));
  ok('「管理提醒」跳提醒抽屉', r.alerts && !r.today, '');
  await ctx.close();

  // —— 场景 3:移动端菜单入口 + 各宽度不溢出 ——
  ctx = await b.newContext({ viewport: { width: 375, height: 812 } });
  p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(900);
  await p.evaluate(() => document.getElementById('mobileMenu').click());
  r = await p.evaluate(() => {
    const a = document.querySelector('a[data-mact="today"]');
    return { present: !!a, hidden: getComputedStyle(document.getElementById('todayBtn')).display === 'none' };
  });
  ok('移动菜单有今日待办入口', r.present, '');
  ok('375 桌面图标隐藏', r.hidden, '');
  await p.evaluate(() => document.querySelector('a[data-mact="today"]').click());
  await p.waitForTimeout(300);
  r = await p.evaluate(() => document.getElementById('todayPanel').classList.contains('is-on'));
  ok('移动端入口打开待办面板', r, '');
  await ctx.close();

  for (const w of [1440, 1280, 1024, 768, 640, 560]) {
    const c = await b.newContext({ viewport: { width: w, height: 900 } });
    const pg = await c.newPage();
    await pg.goto(FILE, { waitUntil: 'load' });
    await pg.waitForTimeout(700);
    const ov = await pg.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const nr = await pg.evaluate(() => {
      const n = document.querySelector('.nav .wrap').getBoundingClientRect();
      return { right: Math.round(n.right), vw: document.documentElement.clientWidth };
    });
    ok(`${w} 导航不溢出`, ov <= 0 && nr.right <= nr.vw, `ovX=${ov} right=${nr.right}/${nr.vw}`);
    await c.close();
  }

  await b.close();
  console.log(fail ? `\n${fail} FAILED` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})();
