/* 诊断与图表同源专项。
   缺陷:ensureDiagCloses 自己用 seed = code + 'dc' 另造一条 120 根随机路,与 K 线图
   (ensureSeries 的 1,300 根)互不相干。实测日收益相关 -0.067~0.147 —— 两条独立随机游走。
   用户能当场看见的矛盾:
     · 600519 图上近 20 日 +10.9%,诊断说 +1.4%
     · 0700 图上 RSI 32.6(偏弱),诊断说 55.9(偏强)
     · AAPL 图上 20 日 -7.9%,诊断说 +4.2%(方向相反)
   修法:诊断从 series 末 120 根派生;图表未建时走 genSeries 的 closesOnly 快捷键
   (同一 seed、同一段 gauss、同一次 rescale,只是不构造 OHLCV 对象)。

   断言分两层 —— 只在序列层比对不够,因为用户看的是 DOM 里的数字:
     A 层:序列逐位相等
     B 层:打开详情页,读 #indGrid 上的 RSI / MACD / BOLL%B,用同一份序列独立算一遍
     C 层:对照 —— 临时塞回旧的独立随机序列,面板数字必须对不上(证明 B 段不是空转)
   用法:node verify-diag-source.js  → 任一不满足退出码 1 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log(`  PASS ${name}${extra ? ' — ' + extra : ''}`); }
  else { fail++; console.log(`  FAIL ${name}${extra ? ' — ' + extra : ''}`); }
};
const head = (s) => console.log(`\n===== ${s} =====`);

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(FILE + '?api=off', { waitUntil: 'load' });
  await p.waitForTimeout(900);
  await p.evaluate(() => { if (typeof liveTimer !== 'undefined' && liveTimer) clearInterval(liveTimer); });

  /* ---------- A. 序列层:两条路必须逐位相同 ---------- */
  head('A. closesOnly 快捷键 与 完整序列 逐位一致');
  const seq = await p.evaluate(() => {
    const codes = ['600519', '300750', 'NVDA', 'AAPL', '0700', 'BTC'];
    return codes.map((c) => {
      const s = BY_CODE[c];
      if (!s) return { code: c, missing: true };
      const keepSer = s.series, keepDc = s._dc;
      try {
        delete s.series; delete s._dc;
        const viaDiag = ensureDiagCloses(s).slice();
        delete s.series; delete s._dc;
        const ser = ensureSeries(s);
        const viaSeries = ser.slice(-120).map((d) => d.c);
        let maxDiff = 0;
        for (let i = 0; i < viaDiag.length; i++) maxDiff = Math.max(maxDiff, Math.abs(viaDiag[i] - viaSeries[i]));
        return {
          code: c, last: s.last, diagLast: viaDiag[viaDiag.length - 1], serLast: viaSeries[viaSeries.length - 1],
          lenA: viaDiag.length, lenB: viaSeries.length, maxDiff,
          rsiDiag: +rsiLast(viaDiag).toFixed(4), rsiSeries: +rsiLast(viaSeries).toFixed(4),
          dcAligned: Math.abs(s._dc[s._dc.length - 1] - viaSeries[viaSeries.length - 1]) < 1e-9,
        };
      } finally {
        s.series = keepSer; s._dc = keepDc;
      }
    });
  });
  const present = seq.filter((x) => !x.missing);
  ok('样本标的数 ≥5', present.length >= 5, `${present.length} 只`);
  present.forEach((x) => {
    ok(`${x.code} 两条路长度一致`, x.lenA === x.lenB && x.lenA === 120, `${x.lenA} vs ${x.lenB}`);
    ok(`${x.code} 逐位相同(<1e-9)`, x.maxDiff < 1e-9, `最大偏差 ${x.maxDiff}`);
    ok(`${x.code} 末值锚定现价`, Math.abs(x.diagLast - x.last) < 1e-6 && Math.abs(x.serLast - x.last) < 1e-6, `${x.diagLast.toFixed(2)} / ${x.serLast.toFixed(2)} vs last ${x.last}`);
    ok(`${x.code} RSI 只有一套口径`, x.rsiDiag === x.rsiSeries, `${x.rsiDiag} vs ${x.rsiSeries}`);
    ok(`${x.code} _dc 已对齐到 series`, x.dcAligned === true);
  });

  /* ---------- B. DOM 层:面板上显示的数字必须等于用图上序列算出来的 ---------- */
  head('B. 诊断面板的数字与图上序列一致(DOM 层)');
  for (const code of ['600519', '0700', 'AAPL']) {
    const r = await p.evaluate(async (c) => {
      const s = BY_CODE[c];
      if (!s) return { code: c, missing: true };
      openDrawer(c);
      await new Promise((res) => setTimeout(res, 280));
      const cells = Array.from(document.querySelectorAll('#indGrid .ind-cell')).map((el) => ({
        k: (el.querySelector('span') || {}).textContent || '',
        v: (el.querySelector('b') || {}).textContent || '',
      }));
      const ser = ensureSeries(s).slice(-120).map((d) => d.c);
      const macd = macdLast(ser);
      const boll = bollSeries(ser, 20, 2);
      const up = boll.upper[boll.upper.length - 1], lo = boll.lower[boll.lower.length - 1];
      const lastCl = ser[ser.length - 1];
      const dg = computeDiag(s);
      return {
        code: c, cells, last: s.last,
        calc: {
          rsi: rsiLast(ser).toFixed(1),
          macd: (macd.dif >= 0 ? '+' : '') + macd.dif.toFixed(2),
          boll: (up !== lo ? ((lastCl - lo) / (up - lo)) * 100 : 50).toFixed(0) + '%',
        },
        stop: dg.stop, seriesLast: ser[ser.length - 1],
      };
    }, code);
    if (r.missing) { ok(`${code} 标的存在`, false); continue; }
    const byKey = {};
    r.cells.forEach((x) => { byKey[x.k] = x.v; });
    ok(`${code} 面板 RSI = 图上序列 RSI`, byKey['RSI(14)'] === r.calc.rsi, `DOM ${byKey['RSI(14)']} vs 计算 ${r.calc.rsi}`);
    ok(`${code} 面板 MACD = 图上序列 MACD`, byKey['MACD(12,26)'] === r.calc.macd, `DOM ${byKey['MACD(12,26)']} vs 计算 ${r.calc.macd}`);
    ok(`${code} 面板 BOLL%B = 图上序列 BOLL%B`, byKey['BOLL %B'] === r.calc.boll, `DOM ${byKey['BOLL %B']} vs 计算 ${r.calc.boll}`);
    ok(`${code} 图表末值 = 现价`, Math.abs(r.seriesLast - r.last) < 1e-6, `${r.seriesLast.toFixed(2)} vs ${r.last}`);
    /* 止损算法地板:max(last*0.85, min(m60*0.985, last*0.97, ...)) —— 必须落在 [85%, 97%] */
    ok(`${code} 止损在算法地板内`, r.stop >= r.last * 0.85 - 1e-6 && r.stop <= r.last * 0.97 + 1e-6, `${r.stop.toFixed(2)}(现价 ${r.last.toFixed(2)}, 区间 ${(r.last * 0.85).toFixed(2)}~${(r.last * 0.97).toFixed(2)})`);
  }

  /* ---------- C. 反向验证:回到「另造一条路」,B 段必须红 ---------- */
  head('C. 对照:临时换回旧的独立随机序列,面板数字应当对不上');
  const ctrl = await p.evaluate(async () => {
    const s = BY_CODE['600519'];
    if (!s) return { missing: true };
    const keep = s._dc;
    /* 逐行复刻旧实现,确认这条断言不是空转 */
    const rng = mulberry32(hashStr(s.code + 'dc'));
    const dv = (s.vol || 0.3) / Math.sqrt(252);
    let q = s.last / Math.exp((s.drift || 0.1) * 0.5);
    const arr = [];
    for (let i = 0; i < 120; i++) { q = Math.max(q * Math.exp((s.drift || 0.1) / 252 + gauss(rng) * dv), 0.0001); arr.push(q); }
    const k = s.last / arr[119];
    for (let i = 0; i < 120; i++) arr[i] *= k;
    s._dc = arr;
    renderIndicators(s);
    const domRsi = (document.querySelector('#indGrid .ind-cell b') || {}).textContent || '';
    const realRsi = rsiLast(ensureSeries(s).slice(-120).map((d) => d.c)).toFixed(1);
    s._dc = keep;
    renderIndicators(s);
    return { domRsi, realRsi, differ: domRsi !== realRsi };
  });
  ok('对照组确实能造出不一致(证明 B 段不是空转)', ctrl.missing ? false : ctrl.differ, ctrl.missing ? '缺标的' : `旧实现 ${ctrl.domRsi} vs 图上 ${ctrl.realRsi}`);

  head('D. 运行期零异常');
  ok('零 pageerror', errs.length === 0, errs.slice(0, 3).join(' | '));

  console.log(`\n结果: ${pass} 通过 / ${fail} 失败`);
  await b.close();
  process.exit(fail ? 1 : 0);
})();
