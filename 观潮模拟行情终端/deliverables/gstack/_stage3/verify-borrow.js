/* 借鉴升级探针:温度计 / K线周期聚合 / 分散度 / 纪律面板 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let pass = 0, fail = 0;
const ok = (name, cond, extra) => { if (cond) { pass++; console.log(`  PASS ${name}${extra ? ' — ' + extra : ''}`); } else { fail++; console.log(`  FAIL ${name}${extra ? ' — ' + extra : ''}`); } };

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1500);

  /* ===== 1. 大盘温度计 ===== */
  await p.evaluate(() => document.querySelector('.gauge-wrap').scrollIntoView({ block: 'center', behavior: 'instant' }));
  await p.waitForTimeout(2400);
  let r = await p.evaluate(() => ({
    val: $('#gaugeVal').textContent,
    title: $('#gaugeTitle').textContent,
    action: $('#gaugeAction').textContent.length,
    dims: $$('#thermoDims .xray-bar').length,
    meta: ['#advTurnover', '#advAdr', '#advRet20', '#advVol'].map((s) => document.querySelector(s).textContent),
    note: !!document.querySelector('.thermo-note'),
    cached: thermoCache && thermoCache.composite,
  }));
  const gaugeNum = parseInt(r.val, 10);
  ok('1 gaugeVal 出数字且在值域', Number.isFinite(gaugeNum) && gaugeNum >= 4 && gaugeNum <= 97 && gaugeNum === r.cached, `val=${r.val}`);
  ok('1 level 文案与行动句就位', r.title.includes('大盘温度 ·') && r.action > 8, r.title);
  ok('1 四条维度 bar', r.dims === 4, `n=${r.dims}`);
  ok('1 adv-meta 四格全部落数', r.meta.every((x) => x && x !== '—' && Number.isFinite(parseFloat(x))), r.meta.join(' | '));
  ok('1 方法学角标存在', r.note, '');
  /* P1-3 回归:波动维度原式 85-vAvg*55 在均值处为正大负值,clamp 后恒等 4,
     四维实际变三维,且复合分上界 73.75 让「过热」档永久不可达 */
  const dimsNow = await p.evaluate(() => computeThermo().dims);
  ok('1 [P1-3] 波动维度不贴下界且可分辨', dimsNow.volatility > 10 && dimsNow.volatility < 95, `vol=${dimsNow.volatility}`);
  ok('1 [P1-3] 四维非常数(至少 3 个不同值)', new Set(Object.values(dimsNow)).size >= 3, JSON.stringify(dimsNow));

  // 主题切换后分数不变(缓存一致性)
  await p.evaluate(() => setTheme('dark'));
  await p.waitForTimeout(700);
  const after = await p.evaluate(() => $('#gaugeVal').textContent);
  ok('1 主题切换分数不变', parseInt(after, 10) === gaugeNum, `${gaugeNum} → ${after}`);
  await p.evaluate(() => setTheme('light'));
  await p.waitForTimeout(400);

  /* ===== 2. K线周期聚合 ===== */
  await p.evaluate(() => openDrawer('AAPL'));
  await p.waitForTimeout(500);
  const btn = (per) => p.evaluate((per) => document.querySelector(`#dhPeriod [data-period="${per}"]`).click(), per);
  await btn('M');
  await p.waitForTimeout(300);
  r = await p.evaluate(() => ({
    badge: $('#detailSynth').textContent,
    ohlc: $('#dhOhlc').textContent.slice(0, 8),
    bars: detailChart.data.length,
    lastC: detailChart.data[detailChart.data.length - 1].c,
    maFastOn: detailChart.opts.maFast,
  }));
  ok('2 月K角标含聚合口径', r.badge.includes('月K(21 日聚合)'), r.badge);
  ok('2 OHLC 提示含逐月口径(未 hover 时显示 hint)', r.ohlc.includes('逐月') || r.ohlc.startsWith('月K'), r.ohlc);
  /* 下界定 10:原断言只写 ≤170,2 根也 PASS,等于没测(2026-11-24 QA 指出) */
  ok('2 月K根数 ≥10 且 ≤170(区间自动抬档)', r.bars <= 170 && r.bars >= 10, `bars=${r.bars}`);
  ok('2 月K开启 MA 快线', r.maFastOn === true, '');
  /* 图例诚实:月K 在 12 根数据下 MA20 无有效点,图例不该照样列 3 条 */
  const ml = await p.evaluate(() => {
    const legend = document.querySelector('.synth-line .legend');
    const slots = Array.from(document.querySelectorAll('.synth-line .legend [data-ma]'));
    const vis = slots.filter((s) => !s.hidden).map((s) => s.textContent.trim());
    const has = (detailChart.maFast || []).map((a) => !!(a && a.some((v) => v != null && Number.isFinite(v))));
    return { legendHidden: !!legend && legend.hidden, vis, has };
  });
  ok('2 月K图例只列真有数据的线', ml.vis.length === ml.has.filter(Boolean).length, JSON.stringify(ml));
  // 末根 c 必须等于末日线 c(聚合语义)
  const tailCheck = await p.evaluate(() => {
    const raw = rangeData(BY_CODE['AAPL'], drawerRange);
    return { rawLast: raw[raw.length - 1].c, aggLast: detailChart.data[detailChart.data.length - 1].c };
  });
  ok('2 末根聚合 c = 末日线 c', Math.abs(tailCheck.rawLast - tailCheck.aggLast) < 1e-9, `${tailCheck.rawLast} vs ${tailCheck.aggLast}`);
  // 连点竞态回归:12 次快速切换后视图与状态一致
  for (let i = 0; i < 12; i++) await btn(['W', 'M', 'D'][i % 3]);
  await p.waitForTimeout(400);
  r = await p.evaluate(() => ({
    period: drawerPeriod,
    bars: detailChart.data.length,
    prefix: $('#dhOhlc').textContent.slice(0, 3),
    on: document.querySelector('#dhPeriod .is-on').dataset.period,
  }));
  ok('2 连点 12 次后视图与状态一致', r.period === r.on && (r.period === 'D' ? r.prefix.startsWith('移') || r.prefix.startsWith('月') || r.prefix.startsWith('周') : r.prefix.startsWith(r.period === 'W' ? '周K' : '月K')), JSON.stringify(r));
  // 日K回落:MA 快线关闭
  await btn('D');
  await p.waitForTimeout(200);
  r = await p.evaluate(() => ({ maFastOn: detailChart.opts.maFast, badge: $('#detailSynth').textContent, legendHidden: !!document.querySelector('.synth-line .legend').hidden }));
  ok('2 切回日K:MA 快线关闭、角标不含聚合口径', r.maFastOn === false && !r.badge.includes('聚合'), r.badge);
  /* 日K 不画 MA5/10/20,图例还必须列出来就是假标注(QA 2026-11-24) */
  ok('2 日K 收起 MA 图例', r.legendHidden === true, `legendHidden=${r.legendHidden}`);
  /* 周K:区间可能已被前面的月K用例抬到 1Y,此时无需再抬;只要求根数够且区间能撑住 ≥50 根日线 */
  await btn('W');
  await p.waitForTimeout(300);
  r = await p.evaluate(() => ({ bars: detailChart.data.length, range: drawerRange, on: document.querySelector('#dhRanges .is-on').dataset.range }));
  ok('2 周K根数 ≥10 且区间足够', r.bars >= 10 && r.bars <= 170 && ['3M', '6M', '1Y', '5Y'].includes(r.range) && r.on === r.range, JSON.stringify(r));
  await btn('D');
  await p.waitForTimeout(150);
  // 1D + 月K → 自动抬档到 1Y(1M=22 根日线聚不出 10 根月K)
  await p.evaluate(() => document.querySelector('#dhRanges [data-range="1D"]').click());
  await p.waitForTimeout(150);
  await btn('M');
  await p.waitForTimeout(250);
  r = await p.evaluate(() => ({ range: drawerRange, on: document.querySelector('#dhRanges .is-on').dataset.range }));
  ok('2 1D 选月K自动抬档到 1Y', r.range === '1Y' && r.on === '1Y', JSON.stringify(r));

  /* ---- P1-1 回归守卫:1D → 周K 曾因单根数据 labelCount-1=0 除零,画布全白并抛
     TypeError(Cannot read properties of undefined (reading 't')) ---- */
  const errsBeforeP1 = errs.length;
  await p.evaluate(() => document.querySelector('#dhRanges [data-range="1D"]').click());
  await p.waitForTimeout(150);
  await btn('W');
  await p.waitForTimeout(400);
  r = await p.evaluate(() => ({
    period: drawerPeriod,
    bars: detailChart.data.length,
    badge: $('#detailSynth').textContent,
    ohlc: $('#dhOhlc').textContent.slice(0, 12),
    ink: (() => { /* 画布非空:取中心区像素,全同色说明没画出来 */ const cv = $('#detailChart'); const g = cv.getContext('2d'); const d = g.getImageData(cv.width / 2 | 0, cv.height / 2 | 0, 24, 24).data; return new Set(Array.from(d)).size; })(),
  }));
  ok('2 [P1-1] 1D→周K 不抛错', errs.length === errsBeforeP1, errs.slice(errsBeforeP1).join('|'));
  ok('2 [P1-1] 1D→周K 出图(≥10 根 + 画布有内容)', r.bars >= 10 && r.ink > 1, `bars=${r.bars} ink=${r.ink}`);
  ok('2 [P1-1] 1D→周K 角标与 OHLC 口径同步', r.badge.includes('周K') && r.ohlc.includes('逐周'), `${r.badge} | ${r.ohlc}`);
  /* 反向路径:周K 状态下点 1D,必须回落日K(否则分时 × 周聚合又是 1 根) */
  await p.evaluate(() => document.querySelector('#dhRanges [data-range="1D"]').click());
  await p.waitForTimeout(300);
  r = await p.evaluate(() => ({ period: drawerPeriod, maFast: detailChart.opts.maFast, on: document.querySelector('#dhPeriod .is-on').dataset.period }));
  ok('2 [P1-1] 周K 状态点 1D 自动回落日K', r.period === 'D' && r.maFast === false && r.on === 'D', JSON.stringify(r));
  /* 区间按钮侧同样要校验:周K 下点 1W(5 根日线)只够聚 1 根,应回落日K而不是画单根蜡烛 */
  await btn('W');
  await p.waitForTimeout(250);
  await p.evaluate(() => document.querySelector('#dhRanges [data-range="1W"]').click());
  await p.waitForTimeout(350);
  r = await p.evaluate(() => ({ period: drawerPeriod, bars: detailChart.data.length, on: document.querySelector('#dhPeriod .is-on').dataset.period, bad: $('#detailSynth').textContent }));
  ok('2 [P1-1] 周K 状态点 1W 回落日K', r.period === 'D' && r.on === 'D' && r.bars >= 2, JSON.stringify(r));
  ok('2 [P1-1] 回落态角标不含周K口径', !r.bad.includes('周K'), r.bad);
  ok('2 图表零 pageerror', errs.length === 0, errs.slice(0, 2).join('|'));

  /* ===== 3. 分散度 + 纪律面板 ===== */
  await p.evaluate(() => { closeDrawer(); });
  await p.evaluate(() => {
    ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOG'].forEach((c) => {
      if (!BY_CODE[c]) return;
      openDrawer(c); document.getElementById('tradeQty').value = '200'; document.getElementById('btnBuy').click(); closeDrawer();
    });
    /* 保证 ≥5 笔过样本线(某些标的可能不在池中) */
    if (account.trades.length < 5) { openDrawer('AAPL'); document.getElementById('tradeQty').value = '100'; document.getElementById('btnBuy').click(); closeDrawer(); }
  });
  await p.waitForTimeout(300);
  await p.evaluate(() => openPortfolio());
  await p.waitForTimeout(400);
  r = await p.evaluate(() => ({
    diver: $('#pfDivers').textContent,
    kpis: $$('#pfDivers .diver-kpis b').map((x) => x.textContent),
    cells: $$('#pfDivers .corr-grid i').length,
    disc: $('#pfDisc').textContent.slice(0, 60),
    chips: $$('#pfDisc .disc-chip').length,
    meta: $('#pfDiscMeta').textContent,
  }));
  ok('3 分散度 KPI 落数', r.kpis.length === 3 && r.kpis.every((x) => x && !x.includes('NaN')), r.kpis.join(' | '));
  ok('3 相关矩阵 n×n 且无 NaN', r.cells >= 9 && Number.isInteger(Math.sqrt(r.cells)) && !r.diver.includes('NaN'), `cells=${r.cells}`);
  ok('3 口径行含「不是红涨绿跌」', r.diver.includes('不是红涨绿跌'), '');
  /* P1-2 回归:表头曾只声明 repeat(cn,1fr) 却塞了 1+cn 个 span,
     导致列名整体错位一格、末位换行——列数必须等于 span 数且首列为 64px 行标签列 */
  const headCols = await p.evaluate(() => {
    const el = document.querySelector('#pfDivers .corr-head');
    if (!el) return null;
    const cols = getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean);
    return { n: cols.length, first: cols[0], spans: el.querySelectorAll('span').length, top: Array.from(el.querySelectorAll('span')).map((s) => Math.round(s.getBoundingClientRect().top)) };
  });
  ok('3 [P1-2] 表头列数 = 1 + 持仓数,首列 64px', headCols && headCols.n === headCols.spans && headCols.first === '64px', JSON.stringify(headCols && { n: headCols.n, spans: headCols.spans, first: headCols.first }));
  ok('3 [P1-2] 表头全部同行(无换行)', headCols && new Set(headCols.top).size === 1, headCols ? headCols.top.join(',') : 'null');
  ok('3 纪律芯片 5 条且 grade 非「样本不足」', r.chips === 5 && !r.meta.includes('样本不足'), `chips=${r.chips} meta=${r.meta}`);
  ok('3 全页零 pageerror', errs.length === 0, errs.slice(0, 2).join('|'));

  /* ===== 4. 移动端 375 无溢出 ===== */
  const ctx2 = await b.newContext({ viewport: { width: 375, height: 812 }, hasTouch: true, isMobile: true });
  const p2 = await ctx2.newPage();
  const errs2 = [];
  p2.on('pageerror', (e) => errs2.push(e.message));
  await p2.goto(FILE, { waitUntil: 'load' });
  await p2.waitForTimeout(1500);
  await p2.evaluate(() => openDrawer('AAPL'));
  await p2.waitForTimeout(400);
  await p2.evaluate(() => document.querySelector('#dhPeriod [data-period="W"]').click());
  await p2.waitForTimeout(250);
  const sw = await p2.evaluate(() => ({ w: document.documentElement.scrollWidth, dw: document.getElementById('drawer').scrollWidth }));
  ok('4 移动端月/周K无横向溢出', errs2.length === 0 && sw.w <= 377, JSON.stringify(sw));
  await ctx2.close();

  await ctx.close();
  await b.close();
  console.log(`\n结果: ${pass} PASS, ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('PROBE CRASH:', e.message); process.exit(2); });
