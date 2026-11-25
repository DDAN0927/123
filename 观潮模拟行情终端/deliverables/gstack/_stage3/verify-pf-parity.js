/* 持仓面板重构对账:改动只该加语义,不该改数字。
   做法:同一组持仓喂给「改动前的实现」(git HEAD:index.html)与当前文件,
   逐项比对 HHI / 有效持仓 / 相关系数矩阵 / 权重 / 五条纪律规则 / 评级。
   样本必须落在「全项可判」的状态(6 笔带涨幅成交 + 4 只可定价持仓),
   因为改动有意修改的是「缺失时的表现」,不是「齐全时的数值」。
   用法:node verify-pf-parity.js  → 任一不一致退出码 1 */
const { chromium } = require('../_baseline/node_modules/playwright');
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '../../..');
const NEW = 'file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/');
const OLD_TMP = path.join(__dirname, '_old_index.html');

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log(`  PASS ${name}${extra ? ' — ' + extra : ''}`); }
  else { fail++; console.log(`  FAIL ${name}${extra ? ' — ' + extra : ''}`); }
};
const head = (s) => console.log(`\n===== ${s} =====`);

/* 在页面里跑同一段采样脚本。故意不用 resolveHoldings/accountMetrics,
   因为旧文件里没有这两个函数 —— 两边只调用共同存在的接口。 */
const SAMPLE = () => {
  const codes = ['600519', '300750', 'NVDA', 'AAPL'];
  /* 价格必须钉死:liveTick 在 waitForTimeout 期间会漂移 last/chgPct,
     而 computeDiag 的止损价由 last + chgPct + _dc 派生 —— 不钉死就变成比两次加载的时序运气。
     这是探针缺陷,不是代码差异(第一次跑的 8.5e-6 权重差就是这么来的)。 */
  codes.forEach((c) => {
    const s = BY_CODE[c];
    if (!s) return;
    s.last = 10 + (hashStr(s.code) % 900) / 7;
    s.prevClose = s.last;
    s.chgPct = ((hashStr(s.code + 'x') % 500) / 100) - 2;
    delete s._dc;
  });
  const holdings = codes
    .map((c) => {
      const s = BY_CODE[c];
      if (!s) return null;
      ensureSeries(s);
      const qty = 100;
      return { code: c, p: { qty, cost: +(s.last * 1.02).toFixed(4) }, s, mv: s.last * qty, pnl: (s.last - s.last * 1.02) * qty };
    })
    .filter(Boolean)
    .sort((a, b) => b.mv - a.mv);
  const mk = (chg, i) => ({ t: Date.now() - i * 1000, code: '600519', side: 'buy', qty: 100, price: 10, fee: 5, amount: 1000, chg });
  account = { cash: 300000, positions: {}, trades: [mk(1, 0), mk(2, 1), mk(0.5, 2), mk(-1, 3), mk(6, 4), mk(0.2, 5)], realized: 0, dayRealized: 0, dayStamp: dayStamp() };
  const d = computeDiversification(holdings);
  const dsc = computeDiscipline(holdings);
  return {
    names: d.names, weights: d.weights, hhi: d.hhi, eff: d.eff,
    corr: d.corr.map((row) => row.map((v) => (v === null ? null : +v.toFixed(12)))),
    rules: dsc.rules.map((r) => ({ name: r.name, val: r.val, pass: r.pass })),
    grade: dsc.grade,
  };
};

const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const near = (a, b, tol) => Math.abs(a - b) <= tol;

(async () => {
  fs.writeFileSync(OLD_TMP, execSync(`git -C "${ROOT}" show HEAD:index.html`, { maxBuffer: 64 * 1024 * 1024 }));

  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });

  const run = async (url) => {
    const p = await ctx.newPage();
    const errs = [];
    p.on('pageerror', (e) => errs.push(e.message));
    await p.goto(url + '?api=off', { waitUntil: 'load' });
    await p.waitForTimeout(900);
    await p.evaluate(() => { if (typeof liveTimer !== 'undefined' && liveTimer) clearInterval(liveTimer); });
    const r = await p.evaluate(SAMPLE);
    await p.close();
    return { r, errs };
  };

  head('A. 同一组合,改动前后两版数值对账');
  const nw = await run(NEW);
  const od = await run('file:///' + OLD_TMP.replace(/\\/g, '/'));
  ok('两次采样都没有 pageerror', !nw.errs.length && !od.errs.length, [...nw.errs, ...od.errs].slice(0, 2).join(' | '));

  ok('参与计算的标的与排序一致', eq(nw.r.names, od.r.names), nw.r.names.join(','));
  ok('权重逐只一致(≤1e-12)', nw.r.weights.every((w, i) => near(w, od.r.weights[i], 1e-12)), JSON.stringify(nw.r.weights.map((w) => +w.toFixed(6))));
  ok('HHI 一致(≤1e-12)', near(nw.r.hhi, od.r.hhi, 1e-12), `${nw.r.hhi} vs ${od.r.hhi}`);
  ok('有效持仓 1/HHI 一致(≤1e-12)', near(nw.r.eff, od.r.eff, 1e-12), `${nw.r.eff} vs ${od.r.eff}`);
  ok('相关矩阵逐格一致(null 位置也一致)', eq(nw.r.corr, od.r.corr), `首行 ${JSON.stringify(nw.r.corr[0])}`);
  ok('五条纪律规则逐条一致', eq(nw.r.rules, od.r.rules), nw.r.rules.map((r) => `${r.name}=${r.val}/${r.pass}`).join(' | '));
  ok('全项可判时评级一致(文本/类名/百分比)', eq(nw.r.grade, od.r.grade), JSON.stringify(nw.r.grade));

  head('B. 全项可判的样本确实覆盖了 5 条规则(否则上面的对账不算数)');
  ok('规则数 = 5', nw.r.rules.length === 5, String(nw.r.rules.length));
  ok('无一条是缺失态', nw.r.rules.every((r) => r.pass !== null), nw.r.rules.filter((r) => r.pass === null).map((r) => r.name).join(','));
  ok('评级是「N/N 守住」而不是缺失标注', /^\d+\/\d+ 守住$/.test(nw.r.grade.txt), nw.r.grade.txt);

  head('C. 新增字段只在有降级时出现(齐全时不打扰)');
  const extra = await (async () => {
    const p = await ctx.newPage();
    await p.goto(NEW + '?api=off', { waitUntil: 'load' });
    await p.waitForTimeout(900);
    const r = await p.evaluate(() => {
      const codes = ['600519', '300750'];
      const holdings = codes.map((c) => { const s = BY_CODE[c]; ensureSeries(s); return { code: c, p: { qty: 100, cost: s.last }, s, mv: s.last * 100, pnl: 0 }; });
      const d = computeDiversification(holdings, []);
      return { win: d.win, q: d.quality, orphanCount: d.orphanCount };
    });
    await p.close();
    return r;
  })();
  ok('窗口按实际可得根数报(1300 根序列 → 120)', extra.win === 120, String(extra.win));
  ok('无缺失时 quality.degraded = false', extra.q.degraded === false, JSON.stringify(extra.q));
  ok('无缺失时 available = total', extra.q.available === extra.q.total && extra.q.total === 1, JSON.stringify(extra.q));

  fs.unlinkSync(OLD_TMP);
  console.log(`\n结果: ${pass} 通过 / ${fail} 失败`);
  await b.close();
  process.exit(fail ? 1 : 0);
})();
