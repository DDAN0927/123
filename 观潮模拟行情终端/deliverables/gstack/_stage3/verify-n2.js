const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });

  // —— 场景 1:升破买入,市价直接推过触发价 ——
  let ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  let p = await ctx.newPage();
  p.on('pageerror', (e) => { fail++; console.log('FAIL  pageerror', e.message); });
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1200);
  // 打开抽屉走真实 UI 挂单
  await p.evaluate(() => openDrawer('NVDA'));
  await p.waitForTimeout(300);
  await p.evaluate(() => document.querySelector('.dh-tabs button[data-pane="trade"]').click());
  await p.waitForTimeout(300);
  let r = await p.evaluate(() => ({
    box: !!document.querySelector('#condAdd'),
    list: /暂无条件单/.test(document.getElementById('condList').textContent),
  }));
  ok('交易页出现条件单面板', r.box && r.list, '');
  // 校验:升破单触发价低于现价应拒绝
  r = await p.evaluate(() => {
    const s = BY_CODE['NVDA'];
    document.getElementById('condTrig').value = (s.last * 0.5).toFixed(2);
    document.getElementById('condAdd').click();
    return { n: condOrders.length, toast: document.querySelector('#toasts .toast:last-child span')?.textContent || '' };
  });
  ok('触发价低于现价的买入单被拒', r.n === 0 && /应高于现价/.test(r.toast), r.toast.slice(0, 30));
  // 正确挂单
  const trig = await p.evaluate(() => {
    const s = BY_CODE['NVDA'];
    const t = +(s.last * 1.02).toFixed(2);
    document.getElementById('condTrig').value = t;
    document.getElementById('condAdd').click();
    return { t, last: s.last, n: condOrders.length, cash0: account.cash };
  });
  ok('挂单成功', trig.n === 1, `trig=${trig.t}`);
  // localStorage 持久化
  r = await p.evaluate(() => JSON.parse(localStorage.getItem('guanchao-cond-v1') || '[]').length);
  ok('挂单已落 localStorage', r === 1, '');
  // 推价触发(模拟 tick 撮合)
  r = await p.evaluate((tv) => {
    const s = BY_CODE['NVDA'];
    s.last = tv * 1.01;
    const cashBefore = account.cash;
    checkCondOrders();
    return {
      n: condOrders.length,
      pos: account.positions['NVDA'] ? account.positions['NVDA'].qty : 0,
      cashDelta: account.cash - cashBefore,
      trades: account.trades.length,
      toast: document.querySelector('#toasts .toast:last-child span')?.textContent || '',
    };
  }, trig.t);
  ok('到价触发买入成交', r.n === 0 && r.pos === 100, `pos=${r.pos}`);
  ok('按触发时市价扣款', r.cashDelta < 0, `Δcash=${r.cashDelta.toFixed(2)}`);
  ok('成交记录入账', r.trades > 0 && /条件单触发/.test(r.toast), r.toast.slice(0, 30));
  // 幂等:再跑一次轮询不应重复成交
  r = await p.evaluate(() => { checkCondOrders(); return { n: condOrders.length, pos: account.positions['NVDA'] ? account.positions['NVDA'].qty : 0 }; });
  ok('幂等:不会重复触发', r.n === 0 && r.pos === 100, '');
  await ctx.close();

  // —— 场景 2:止损卖出 + 资金不足作废 + 持久化重载 ——
  ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1200);
  r = await p.evaluate(() => {
    // 先建持仓
    const b1 = execBuy('AAPL', 100);
    if (!b1.ok) return { err: b1.msg };
    const s = BY_CODE['AAPL'];
    // 止损单触发价低于现价才有效
    const t = +(s.last * 0.97).toFixed(2);
    condOrders.push({ id: 's1', code: 'AAPL', side: 'sell', qty: 100, trig: t, t: Date.now() });
    saveCondOrders();
    // 资金不足作废:买单触发价打满现金外
    const s2 = BY_CODE['TSLA'];
    condOrders.push({ id: 'b1', code: 'TSLA', side: 'buy', qty: 100000, trig: +(s2.last * 1.01).toFixed(2), t: Date.now() });
    saveCondOrders();
    const realized0 = account.realized;
    // 推价:两者同时触发
    s.last = t * 0.99;
    BY_CODE['TSLA'].last = s2.last * 1.02;
    checkCondOrders();
    return {
      n: condOrders.length,
      pos: account.positions['AAPL'] ? account.positions['AAPL'].qty : 0,
      tslaPos: account.positions['TSLA'] ? account.positions['TSLA'].qty : 0,
      realizedDelta: account.realized - realized0,
      toasts: [...document.querySelectorAll('#toasts .toast span')].map((x) => x.textContent),
    };
  });
  ok('止损单触发清仓', r.n === 0 && r.pos === 0, `pos=${r.pos}`);
  ok('止损落袋(已实现盈亏变动)', r.realizedDelta < 0, `Δ=${r.realizedDelta.toFixed(2)}`);
  ok('资金不足的买单触发即作废', r.tslaPos === 0 && r.toasts.some((t) => /触发失败/.test(t)), r.toasts.join(' | ').slice(0, 60));
  // 持久化重载:再挂一条后刷新页面
  await p.evaluate(() => {
    condOrders.push({ id: 'keep1', code: 'NVDA', side: 'buy', qty: 100, trig: 999999, t: Date.now() });
    saveCondOrders();
  });
  await p.reload({ waitUntil: 'load' });
  await p.waitForTimeout(1500);
  r = await p.evaluate(() => ({ n: condOrders.length, id: condOrders[0] && condOrders[0].id }));
  ok('刷新后条件单恢复', r.n === 1 && r.id === 'keep1', `n=${r.n}`);
  // 撤单
  r = await p.evaluate(() => {
    openDrawer('NVDA');
    document.querySelector('.dh-tabs button[data-pane="trade"]').click();
    return { listed: !!document.querySelector('[data-condcancel]') };
  });
  ok('挂单在交易页列出', r.listed, '');
  await p.evaluate(() => { document.querySelector('[data-condcancel]').click(); });
  r = await p.evaluate(() => ({ n: condOrders.length, ls: JSON.parse(localStorage.getItem('guanchao-cond-v1') || '[]').length }));
  ok('撤销条件单', r.n === 0 && r.ls === 0, '');
  await ctx.close();

  // —— 场景 3:移动端 375 条件单面板可用 ——
  ctx = await b.newContext({ viewport: { width: 375, height: 812 } });
  p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(900);
  r = await p.evaluate(() => {
    openDrawer('NVDA');
    document.querySelector('.dh-tabs button[data-pane="trade"]').click();
    const inp = document.getElementById('condTrig');
    const r1 = inp.getBoundingClientRect();
    return { visible: r1.width > 0 && r1.height >= 44, formW: document.querySelector('.cond-form').getBoundingClientRect().width };
  });
  ok('375 条件单输入触控达标', r.visible && r.formW > 200, `h=${r.visible}`);
  await ctx.close();

  await b.close();
  console.log(fail ? `\n${fail} FAILED` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})();
