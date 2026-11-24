/* 温度计数据质量专项:四维可用性(available/note)、缺失维度不得伪装成中性分、
   合成按可用权重归一、权重覆盖不足时不出结论。
   另含一条「重构未改算法」证明:用改动前的原式重算四维,与现实现逐维比对。
   用法:node verify-thermo-quality.js  → 任一不满足退出码 1 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log(`  PASS ${name}${extra ? ' — ' + extra : ''}`); }
  else { fail++; console.log(`  FAIL ${name}${extra ? ' — ' + extra : ''}`); }
};
const head = (s) => console.log(`\n===== ${s} =====`);

/* 读 DOM 里的四行维度条 */
const readRows = (p) => p.evaluate(() => ({
  rows: Array.from(document.querySelectorAll('#thermoDims .xray-bar')).map((el) => ({
    label: el.querySelector('span').textContent,
    score: el.querySelector('b').textContent,
    na: el.classList.contains('is-na'),
    title: el.getAttribute('title') || '',
  })),
  gaugeTitle: document.getElementById('gaugeTitle').textContent,
  gaugeAction: document.getElementById('gaugeAction').textContent,
  gaugeVal: document.getElementById('gaugeVal').textContent,
  turnover: document.getElementById('advTurnover').textContent,
  adr: document.getElementById('advAdr').textContent,
  ret20: document.getElementById('advRet20').textContent,
  vol: document.getElementById('advVol').textContent,
  note: (document.querySelector('.thermo-note') || {}).textContent || '',
}));

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(FILE + '?api=off', { waitUntil: 'load' });
  await p.waitForTimeout(1000);
  /* 停掉仿真:chgPct 会随 liveTick 漂移,不停掉则"重算 vs 实现"必对不上 */
  await p.evaluate(() => { if (typeof liveTimer !== 'undefined' && liveTimer) clearInterval(liveTimer); });
  /* 滚到仪表盘触发首屏揭示动画(1100ms),之后 gaugeVal 才由 renderThermo 接管 */
  await p.evaluate(() => document.querySelector('.gauge-wrap').scrollIntoView({ block: 'center', behavior: 'instant' }));
  await p.waitForTimeout(1600);

  /* ---------- A. 重构未改算法:用改动前的原式重算,逐维比对 ---------- */
  head('A. 四维口径与改动前原式一致');
  const a = await p.evaluate(() => {
    const t = computeThermo();
    const cl = (x) => Math.min(97, Math.max(4, Math.round(x)));
    /* —— 以下四段是改动前的原式,原样抄回,只用来对账 —— */
    const cnIdx = INDICES.filter((x) => x.mkt === 'CN');
    const devs = cnIdx.map((idx) => {
      const ser = indexSeries(idx);
      const ma = movingAvg(ser, 20);
      const m = ma[ma.length - 1];
      return m ? (ser[ser.length - 1] / m - 1) * 100 : 0;
    });
    const trendOld = cnIdx.length ? cl(50 + (devs.reduce((x, y) => x + y, 0) / devs.length) * 6) : 50;
    const cn = STOCKS.filter((s) => s.market === 'CN');
    const upR = cn.length ? cn.filter((s) => s.chgPct > 0).length / cn.length : 0.5;
    const breadthOld = cl(upR * 125);
    const boards = industryBoards();
    const chgs = boards.map((x) => x.chg);
    const rotationOld = boards.length > 1 ? cl(35 + (Math.max(...chgs) - Math.min(...chgs)) * 9) : 50;
    const sample = cn.slice(0, 400);
    const vAvgOld = sample.length ? sample.reduce((x, s) => x + atrPct(s), 0) / sample.length : 1.5;
    const volOld = cl(104 - vAvgOld * 11.5);
    return {
      dims: t.dims,
      old: { trend: trendOld, breadth: breadthOld, rotation: rotationOld, volatility: volOld },
      composite: t.composite,
      coverage: t.coverage,
      missing: t.missing,
      level: t.level,
      vAvg: t.vAvg,
      vAvgOld,
      sumW: Object.values(t.dims).length,
    };
  });
  ok('趋势 dims = 原式', a.dims.trend === a.old.trend, `${a.dims.trend} vs ${a.old.trend}`);
  ok('宽度 dims = 原式', a.dims.breadth === a.old.breadth, `${a.dims.breadth} vs ${a.old.breadth}`);
  ok('轮动 dims = 原式', a.dims.rotation === a.old.rotation, `${a.dims.rotation} vs ${a.old.rotation}`);
  ok('波动 dims = 原式', a.dims.volatility === a.old.volatility, `${a.dims.volatility} vs ${a.old.volatility}`);
  ok('波动均值 = 原式', Math.abs(a.vAvg - a.vAvgOld) < 1e-9, `${a.vAvg} vs ${a.vAvgOld}`);
  ok('正常态四维齐全(不误报缺失)', a.missing.length === 0 && a.coverage === 1, `missing=${a.missing.length} coverage=${a.coverage}`);

  /* ---------- B. 正常态 DOM ---------- */
  head('B. 正常态渲染(4 行有分、无 is-na)');
  await p.evaluate(() => { thermoCache = computeThermo(); renderThermo(); });
  await p.waitForTimeout(800);
  const nd = await readRows(p);
  ok('4 行维度条', nd.rows.length === 4, `实际 ${nd.rows.length}`);
  ok('无 is-na 标记', nd.rows.every((r) => !r.na), nd.rows.map((r) => (r.na ? 'NA' : 'ok')).join(','));
  const domScores = nd.rows.map((r) => Number(r.score));
  const expectScores = [a.dims.trend, a.dims.breadth, a.dims.rotation, a.dims.volatility];
  ok('DOM 分数与 dims 逐维一致', JSON.stringify(domScores) === JSON.stringify(expectScores), `${domScores} vs ${expectScores}`);
  ok('每行 title 带计算说明', nd.rows.every((r) => r.title.length > 6), nd.rows[0].title.slice(0, 40));
  ok('标题含档位、不含「维度不足」', nd.gaugeTitle.includes('大盘温度 · ') && !nd.gaugeTitle.includes('维度不足'), nd.gaugeTitle);
  ok('仪表盘数字 = 合成分', Number(nd.gaugeVal) === a.composite, `${nd.gaugeVal} vs ${a.composite}`);
  ok('揭示动画已结束(gaugeVal 交给 renderThermo 管)', await p.evaluate(() => gaugeRevealed === true), 'gaugeRevealed');
  ok('方法学角标仍在', nd.note.includes('四维复合评分'), nd.note.slice(0, 30));

  /* ---------- C. 四维全缺:必须标不可用、不出结论 ---------- */
  head('C. 四维全缺(空市场)');
  await p.evaluate(() => { thermoCache = computeThermo({ indices: [], stocks: [], boards: [] }); renderThermo(); });
  await p.waitForTimeout(800);
  const ed = await readRows(p);
  ok('4 行仍渲染(不留空白)', ed.rows.length === 4);
  ok('4 行全部 is-na', ed.rows.every((r) => r.na), ed.rows.map((r) => (r.na ? 'NA' : r.score)).join(','));
  ok('分数位显示「—」而不是数字', ed.rows.every((r) => r.score === '—'), ed.rows.map((r) => r.score).join(','));
  ok('每行 title 说明缺失原因', ed.rows.every((r) => r.title.length > 6), ed.rows[0].title);
  ok('标题判维度不足', ed.gaugeTitle.includes('维度不足'), ed.gaugeTitle);
  ok('结论含「不给结论」与缺失清单', ed.gaugeAction.includes('不给结论') && ed.gaugeAction.includes('缺失'), ed.gaugeAction);
  ok('成交额/涨跌比/20日/波动率 全部「—」',
    [ed.turnover, ed.adr, ed.ret20, ed.vol].every((v) => v.trim() === '—'),
    [ed.turnover, ed.adr, ed.ret20, ed.vol].join(' | '));
  ok('仪表盘数字显示「—」(不摆假数)', ed.gaugeVal.trim() === '—', JSON.stringify(ed.gaugeVal));

  /* ---------- D. 缺两维:覆盖 0.5 → 仍不出结论 ---------- */
  head('D. 缺趋势+轮动(覆盖 0.50)');
  const d = await p.evaluate(() => {
    const t = computeThermo({ indices: [], boards: [] });
    thermoCache = t;
    renderThermo();
    return { coverage: t.coverage, missing: t.missing, level: t.level, composite: t.composite,
      want: Math.round((t.dims.breadth * 0.25 + t.dims.volatility * 0.25) / 0.5) };
  });
  await p.waitForTimeout(800);
  const dd = await readRows(p);
  ok('missing 恰为 trend+rotation', d.missing.length === 2 && d.missing.includes('trend') && d.missing.includes('rotation'), `[${d.missing.join(',')}]`);
  ok('覆盖 0.50', d.coverage === 0.5, String(d.coverage));
  ok('合成分按可用权重归一', d.composite === d.want, `${d.composite} vs ${d.want}`);
  ok('仍判维度不足', dd.gaugeTitle.includes('维度不足'), dd.gaugeTitle);
  ok('2 行 is-na、2 行仍有分数', dd.rows.filter((r) => r.na).length === 2 && dd.rows.filter((r) => !r.na).length === 2,
    dd.rows.map((r) => (r.na ? 'NA' : r.score)).join(','));
  ok('缺失维的行序与 label 对得上(趋势/轮动为 NA)', dd.rows[0].na && dd.rows[2].na, `${dd.rows[0].label}=${dd.rows[0].score}`);

  /* ---------- E. 缺一维:覆盖 0.70 → 照常给结论 ---------- */
  head('E. 只缺趋势(覆盖 0.70)');
  const e = await p.evaluate(() => {
    const t = computeThermo({ indices: [] });
    thermoCache = t;
    renderThermo();
    return { coverage: t.coverage, level: t.level, insufficient: t.insufficient, composite: t.composite };
  });
  await p.waitForTimeout(800);
  const ee = await readRows(p);
  ok('覆盖 0.70 且 sufficient', e.coverage === 0.7 && e.insufficient === false, `${e.coverage}/${e.insufficient}`);
  ok('正常给档位(不判维度不足)', !ee.gaugeTitle.includes('维度不足') && ee.gaugeTitle.includes('大盘温度 · '), ee.gaugeTitle);
  ok('仅 1 行 is-na', ee.rows.filter((r) => r.na).length === 1, ee.rows.map((r) => (r.na ? 'NA' : r.score)).join(','));

  /* ---------- F. 切主题后缺失态不丢失 ---------- */
  head('F. 主题切换后 is-na 状态保持');
  await p.evaluate(() => setTheme('dark'));
  await p.waitForTimeout(900);
  const dd2 = await readRows(p);
  ok('暗色下仍 1 行 is-na', dd2.rows.filter((r) => r.na).length === 1, dd2.rows.map((r) => (r.na ? 'NA' : r.score)).join(','));
  ok('暗色下结论未被重算改写', dd2.gaugeTitle === ee.gaugeTitle, dd2.gaugeTitle);
  await p.evaluate(() => setTheme('light'));
  await p.waitForTimeout(600);

  /* ---------- G. 无 pageerror ---------- */
  head('G. 运行期零异常');
  ok('零 pageerror', errs.length === 0, errs.slice(0, 3).join(' | '));

  /* ---------- 汇总(打印本次真实四维数值,便于人工核对) ---------- */
  console.log('\n本次实测四维:', JSON.stringify(a.dims), '| 合成', a.composite, '| 档位', a.level);
  console.log(`\n结果: ${pass} 通过 / ${fail} 失败`);
  await b.close();
  process.exit(fail ? 1 : 0);
})();
