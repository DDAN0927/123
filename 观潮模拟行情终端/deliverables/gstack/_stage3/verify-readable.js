/* 阶段四第 2 轮:数据可读性(Q10/Q17/Q19/Q25)验证探针 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1500); // 首帧后宇宙构建

  // Q10: 财务柱数值标签
  const fin = await p.evaluate(() => {
    const s = STOCKS.find((x) => x.pe > 0 && x.market !== 'CRYPTO');
    openDrawer(s.code);
    document.querySelector('.dh-tabs button[data-pane="fund"]').click();
    return new Promise((res) => setTimeout(() => {
      const vals = [...document.querySelectorAll('#finChart .fin-vals')];
      res({
        groups: vals.length,
        allHaveRev: vals.every((v) => /^\d[\d,.]*\.(?:\d亿|万亿)$|^\d[\d,]*亿$|^\d[\d,.]*万亿$/.test(v.querySelector('b').textContent)),
        allHavePro: vals.every((v) => v.querySelector('i').textContent.includes('亿')),
        sample: vals.slice(0, 2).map((v) => v.textContent.trim()),
      });
    }, 400));
  });
  ok('Q10 财务柱 4 组均有金额标签', fin.groups === 4 && fin.allHaveRev && fin.allHavePro, JSON.stringify(fin.sample));
  await p.keyboard.press('Escape');

  // Q19: 诊断三价位自洽(抽查 3 只不同评分档的标的)
  const diag = await p.evaluate(() => {
    const out = [];
    const picks = [STOCKS.find((x) => x.code === '300750') || STOCKS[0], STOCKS[Math.floor(STOCKS.length / 3)], STOCKS[Math.floor(STOCKS.length * 2 / 3)]];
    for (const s of picks) {
      const d = computeDiag(s);
      out.push({
        code: s.code, score: d.score, last: s.last,
        entryLo: d.entryLo, entryHi: d.entryHi, stop: d.stop,
        gap: d.entryLo != null ? ((d.entryLo - d.stop) / d.entryLo * 100).toFixed(1) : null,
        waitOK: !(d.score >= 55 && d.score < 68) || d.entryHi < s.last,
        inRangeOK: !(d.score >= 68) || d.entryLo <= s.last,
      });
    }
    return out;
  });
  ok('Q19 失效价距进场下沿 ≥5%', diag.every((d) => d.entryLo == null || d.gap >= 5), diag.map((d) => d.code + ':' + d.gap).join(' '));
  ok('Q19 等待档(55-67)区间严格低于现价', diag.every((d) => d.waitOK), '');
  ok('Q19 建仓档(≥68)进场下沿 ≤ 现价', diag.every((d) => d.inRangeOK), '');

  // Q19 UI: 进场区间行出现「现价对照」
  const ui = await p.evaluate(() => {
    const s = STOCKS.find((x) => x.code === '300750') || STOCKS[0];
    openDrawer(s.code);
    document.querySelector('.dh-tabs button[data-pane="diag"]').click();
    return new Promise((res) => setTimeout(() => {
      const rows = [...document.querySelectorAll('#diagPlan .dh-stat span')].map((x) => x.textContent);
      res({ hasContrast: rows.includes('现价对照'), rows });
    }, 400));
  });
  ok('Q19 诊断计划含「现价对照」行', ui.hasContrast, ui.rows.join('/'));
  await p.keyboard.press('Escape');

  // Q17 + Q25: 走真实交易流
  const trade = await p.evaluate(() => {
    const s = STOCKS.find((x) => lotOf(x) === 100 && x.last > 1 && x.last < 2000);
    const snap = JSON.stringify(account);
    const cashBefore = account.cash;
    try {
      const q = calcBuy(s.last, 100);
      const rb = execBuy(s.code, 100);
      const cashMid = account.cash;
      const rs = execSell(s.code, 100);
      const cashAfter = account.cash;
      const m = accountMetrics();
      return {
        ok: rb.ok && rs.ok,
        buyTotal: q.amount + q.fee,
        buyDelta: cashBefore - cashMid,
        // Q25: 买入现金减少额 == 委托金额+费用(两位小数下精确)
        q25: Math.abs((cashBefore - cashMid) - (q.amount + q.fee)) < 1e-6,
        // 往返净流出应恰为全部费用(与 Q17 交叉验证)
        roundTrip: cashBefore - cashAfter,
        // Q17: 清仓后今日盈亏为负(费用),不再是 +0
        day: m.day, dayRealized: account.dayRealized,
        q17: m.day < 0 && Math.abs(m.day - account.dayRealized) < 1e-6,
        buySellFees: q.fee + calcSell(s.last, 100).fee + calcSell(s.last, 100).stamp,
      };
    } finally { account = JSON.parse(snap); saveAccount(); }
  });
  ok('Q25 现金减少额 == 委托金额+费用(精确)', trade.ok && trade.q25, `Δbuy=${trade.buyDelta.toFixed(2)} vs ${(trade.buyTotal).toFixed(2)}`);
  ok('Q17 清仓后今日盈亏为负且等于已实现', trade.q17, `day=${trade.day.toFixed(2)} realized=${trade.dayRealized.toFixed(2)} fees=${trade.buySellFees.toFixed(2)}`);

  // Q25 UI: 交易 tab 摘要两位小数
  const ui25 = await p.evaluate(() => {
    const s = STOCKS.find((x) => lotOf(x) === 100 && x.last > 1 && x.last < 2000);
    openDrawer(s.code);
    document.querySelector('.dh-tabs button[data-pane="trade"]').click();
    $('#tradeQty').value = '100';
    updateTradeSummary(s);
    return { amount: document.querySelector('#tbAmount').textContent, fee: document.querySelector('#tbFee').textContent, cash: document.querySelector('#tbCash').textContent };
  });
  ok('Q25 摘要金额两位小数可横加', /^¥[\d,]+\.\d{2}$/.test(ui25.amount) && /\/ ¥[\d,]+\.\d{2}$/.test(ui25.fee) && /^¥[\d,]+\.\d{2}$/.test(ui25.cash), JSON.stringify(ui25));
  await p.keyboard.press('Escape');

  await b.close();
  console.log(fail ? `\n*** ${fail} FAILED ***` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
