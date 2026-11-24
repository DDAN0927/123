/* 主动缺陷挖掘:bughunt 探针——重交互扫 console/pageerror + 脏 localStorage + 输入边界 + 移动端 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let pass = 0, fail = 0;
const ok = (name, cond, extra) => { if (cond) { pass++; console.log(`  PASS ${name}${extra ? ' — ' + extra : ''}`); } else { fail++; console.log(`  FAIL ${name}${extra ? ' — ' + extra : ''}`); } };

function watch(p) {
  const errs = [];
  p.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  p.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  return errs;
}

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });

  /* ===== A. 桌面重交互扫错 ===== */
  console.log('A. 重交互会话');
  {
    const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
    const errs = watch(p);
    await p.goto(FILE, { waitUntil: 'load' });
    await p.waitForTimeout(1500);

    // A1 智能筛选:正则特殊字符 / HTML / 超长串 / 空查询
    for (const q of ['(', '[', '*)+?', '市值>5000', '<script>alert(1)</script>', 'x'.repeat(300)]) {
      await p.fill('#smartQuery', q);
      await p.keyboard.press('Enter');
      await p.waitForTimeout(120);
    }
    await p.fill('#smartQuery', '');
    await p.keyboard.press('Enter'); // 空查询 → toast,不崩
    await p.waitForTimeout(150);
    ok('A1 智能筛选抗特殊字符', errs.length === 0, errs.slice(0, 2).join(' | '));

    // A2 键盘流作用于空结果集(筛选无结果 → j/k/Enter 不崩)
    await p.evaluate(() => { BY_CODE['AAPL'] && (document.getElementById('smartQuery').value = 'zzzz不存在的板块xq'); });
    await p.fill('#smartQuery', 'zzzz不存在xq');
    await p.keyboard.press('Enter');
    await p.waitForTimeout(150);
    await p.keyboard.press('j');
    await p.keyboard.press('k');
    await p.keyboard.press('Enter');
    await p.waitForTimeout(200);
    ok('A2 空结果键盘流不崩', errs.length === 0, errs.slice(0, 2).join(' | '));
    await p.evaluate(() => { document.getElementById('smartQuery').value = ''; window.clearSmartFilters && clearSmartFilters(); });
    await p.waitForTimeout(150);

    // A3 交易边界:qty 0/负/NaN/超大/现金不足
    await p.evaluate(() => openDrawer('AAPL'));
    await p.waitForTimeout(400);
    for (const q of ['0', '-100', 'abc', '999999999']) {
      await p.evaluate((q) => {
        const el = document.getElementById('tradeQty');
        el.value = q;
        document.getElementById('btnBuy').click();
      }, q);
      await p.waitForTimeout(120);
    }
    ok('A3 交易边界输入不崩且不产生坏账', errs.length === 0 && await p.evaluate(() => Number.isFinite(account.cash) && account.cash >= 0), `cash=${await p.evaluate(() => account.cash)}`);

    // A4 提醒:非法代码/价格
    for (const [c, v] of [['', ''], ['!!!!', '12'], ['AAPL', '0'], ['AAPL', '-5'], ['AAPL', 'nan']]) {
      await p.evaluate(([c, v]) => {
        document.getElementById('alertCode').value = c;
        document.getElementById('alertPrice').value = v;
        document.getElementById('alertAdd').click();
      }, [c, v]);
      await p.waitForTimeout(100);
    }
    ok('A4 提醒非法输入不崩', errs.length === 0, errs.slice(0, 2).join(' | '));

    // A5 条件单:重复挂单/取消不存在 id
    await p.evaluate(() => { document.getElementById('tradeQty').value = '100'; document.getElementById('condTrig').value = '99999'; });
    await p.evaluate(() => document.getElementById('condAdd').click());
    await p.waitForTimeout(120);
    await p.evaluate(() => document.getElementById('condAdd').click()); // 同参数再挂一条(允许,一次性有效各自触发)
    await p.waitForTimeout(120);
    const nCond = await p.evaluate(() => condOrders.length);
    await p.evaluate(() => condCancel('fake-id-xyz'));
    await p.waitForTimeout(100);
    ok('A5 条件单挂/撤边界', nCond >= 1 && errs.length === 0, `nCond=${nCond}`);

    // A6 对比弹层:同一标的加两次
    await p.evaluate(() => { openDrawer(); });
    await p.waitForTimeout(200);
    await p.evaluate(() => { closeDrawer(); openCompare(); });
    await p.waitForTimeout(250);
    await p.evaluate(() => { const i = document.getElementById('cmpInput'); i.value = 'AAPL'; i.dispatchEvent(new Event('input')); });
    await p.waitForTimeout(150);
    await p.keyboard.press('Enter');
    await p.waitForTimeout(200);
    await p.keyboard.press('Enter'); // 再加一次
    await p.waitForTimeout(200);
    ok('A6 对比重复添加不崩', errs.length === 0, errs.slice(0, 2).join(' | '));
    await p.evaluate(() => closeCompare());

    // A7 全弹层开关风暴 + 主题连打 5 次
    await p.evaluate(() => { openPortfolio(); });
    await p.evaluate(() => { closePortfolio(); openAlerts(); });
    await p.evaluate(() => { closeAlerts(); openToday(); });
    await p.evaluate(() => { closeToday(); openSettings(); });
    await p.evaluate(() => { closeSettings(); openSectorDrawer && openSectorDrawer(); });
    await p.evaluate(() => { closeSectorDrawer && closeSectorDrawer(); });
    for (let i = 0; i < 5; i++) { await p.evaluate(() => setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark')); await p.waitForTimeout(80); }
    await p.waitForTimeout(400);
    const themePersist = await p.evaluate(() => localStorage.getItem('guanchao-theme-v2'));
    ok('A7 弹层风暴+主题连打不崩且持久化', errs.length === 0 && (themePersist === 'light' || themePersist === 'dark'), `theme=${themePersist}`);

    ok('A8 全程零 pageerror/console.error', errs.length === 0, errs.slice(0, 3).join(' | '));
    await p.close();
  }

  /* ===== B. 脏 localStorage ===== */
  console.log('B. 脏存储容忍');
  const dirtySets = [
    ['全部 key 为断裂 JSON', { 'guanchao-account-v2': '{"cash":', 'guanchao-alerts-v1': '[{"code":', 'guanchao-cond-v1': '[[[', 'guanchao-favs': 'not json', 'guanchao-theme-v2': '"purple"', 'guanchao-settings-v1': '{{', 'guanchao-compare-v1': 'null', 'guanchao-fav-groups-v1': 'x' }],
    ['合法但恶意值', { 'guanchao-account-v2': JSON.stringify({ cash: -99999, positions: { 'FAKE': { qty: -1e9, cost: 'x' } }, trades: [{ code: '<img src=x onerror=alert(1)>' }] }), 'guanchao-alerts-v1': JSON.stringify([{ code: '><script>', price: 'x', dir: 'up' }, null, 42]), 'guanchao-cond-v1': JSON.stringify([{ code: 'DROP TABLE', side: 'x', qty: -1, trig: NaN }, 3]), 'guanchao-theme-v2': 'yellow' }],
    ['超大字符串', { 'guanchao-favs': JSON.stringify(Array(2000).fill('XXXX')), 'guanchao-alerts-v1': JSON.stringify(Array(500).fill({ code: 'AAPL', price: 1, dir: 'up' })) }],
  ];
  for (const [name, kv] of dirtySets) {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
    const p = await ctx.newPage();
    const errs = watch(p);
    await p.addInitScript((kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }, kv);
    await p.goto(FILE, { waitUntil: 'load' });
    await p.waitForTimeout(1800);
    const sane = await p.evaluate(() => ({
      cash: account.cash, alerts: (typeof alerts !== 'undefined' ? alerts.length : -1),
      cond: condOrders.length, rows: document.querySelectorAll('#hotBody tr').length,
    }));
    ok(`B ${name}: 不崩且账面健全`, errs.length === 0 && Number.isFinite(sane.cash) && sane.cash >= 0 && sane.rows > 0, `cash=${sane.cash} alerts=${sane.alerts} cond=${sane.cond} errs=${errs.slice(0, 2).join('|')}`);
    await ctx.close();
  }

  /* ===== C. 移动端 375 交互扫错 ===== */
  console.log('C. 移动端 375');
  {
    const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, hasTouch: true, isMobile: true });
    const p = await ctx.newPage();
    const errs = watch(p);
    await p.goto(FILE, { waitUntil: 'load' });
    await p.waitForTimeout(1500);
    await p.evaluate(() => document.getElementById('mobileMenu').click());
    await p.waitForTimeout(250);
    await p.evaluate(() => { [...document.querySelectorAll('.nav-links a')].find(a => a.textContent.includes('今日待办')).click(); });
    await p.waitForTimeout(300);
    await p.keyboard.press('Escape');
    await p.waitForTimeout(250);
    await p.evaluate(() => document.getElementById('mobileMenu').click());
    await p.waitForTimeout(200);
    await p.evaluate(() => { [...document.querySelectorAll('.nav-links a')].find(a => a.textContent.includes('价格提醒')).click(); });
    await p.waitForTimeout(300);
    await p.keyboard.press('Escape');
    await p.waitForTimeout(200);
    const noHScroll = await p.evaluate(() => document.documentElement.scrollWidth <= 377);
    ok('C 移动端菜单/面板交互不崩且无横向溢出', errs.length === 0 && noHScroll, `scrollW=${await p.evaluate(() => document.documentElement.scrollWidth)} errs=${errs.slice(0, 2).join('|')}`);
    await ctx.close();
  }

  await b.close();
  console.log(`\n结果: ${pass} PASS, ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('PROBE CRASH:', e.message); process.exit(2); });
