/* K 线聚合的期望值生成器（前端口径）。
 *
 * 抽取 index.html 的 genSeries / aggBars / RANGE_MAP 原文，按 drawerBars 的规则
 * （残行过滤 → 聚合 → 超 170 根截尾）复现前端行为，产出 JSON 供 Python 端与
 * 后端 /api/market/kline 逐根比对。
 *
 * 用法: node parity_kline_gen.js <index.html> <输出 json>
 */
const fs = require('fs');
const path = require('path');

const htmlPath = process.argv[2] || path.join(__dirname, '..', '..', 'index.html');
const outPath = process.argv[3] || path.join(__dirname, 'parity_kline_js.json');
const html = fs.readFileSync(htmlPath, 'utf8');

function grab(startMark, endMark) {
  const i = html.indexOf(startMark);
  if (i < 0) throw new Error('未找到起点: ' + startMark);
  const j = html.indexOf(endMark, i);
  if (j < 0) throw new Error('未找到终点: ' + endMark);
  return html.slice(i, j);
}

const rngSrc = grab('function mulberry32(seed) {', 'const UNIVERSE');
const genSrc = grab('function genSeries(sym) {', 'const CURATED');
const aggSrc = grab('function aggBars(bars, mult) {', 'let drawerPeriod');
const rangeSrc = grab('const RANGE_MAP = {', 'function intradayOf');
const daysMatch = html.match(/const SERIES_DAYS\s*=\s*(\d+)/);

const code = `
  const SERIES_DAYS = ${daysMatch[1]};
  ${rngSrc}
  ${genSrc}
  ${rangeSrc}
  ${aggSrc}
  return { genSeries, aggBars, RANGE_MAP };
`;
const { genSeries, aggBars, RANGE_MAP } = new Function(code)();

// 按 drawerBars 原文复现（残行过滤 → 聚合 → 170 截尾）
const DH_CANDLE_MAX = 170;
function drawerBars(bars, range, period) {
  const n = RANGE_MAP[range] || 22;
  const raw = bars.slice(-n);
  if (period === 'D') return raw;
  const cleaned = raw.filter(
    (b) => b && ['o', 'h', 'l', 'c'].every((k) => Number.isFinite(b[k]) && b[k] > 0)
  );
  const agg = aggBars(cleaned, period === 'W' ? 5 : 21);
  return agg.length > DH_CANDLE_MAX ? agg.slice(-DH_CANDLE_MAX) : agg;
}

const fmtLocal = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const syms = [
  { code: '600519', price: 1624.5, vol: 0.27, drift: 0.09, mcap: 20412 },
  { code: 'AAPL', price: 242.7, vol: 0.24, drift: 0.12, mcap: 36210 },
  { code: 'BTC', price: 96420, vol: 0.62, drift: 0.24, mcap: 19120 },
];

const combos = [
  { range: '1W', period: 'D' },
  { range: '1M', period: 'D' },
  { range: '1Y', period: 'D' },
  { range: '3M', period: 'W' },
  { range: '1Y', period: 'W' },
  { range: '5Y', period: 'W' },
  { range: '3M', period: 'M' },
  { range: '5Y', period: 'M' },
  { range: '1W', period: 'W' }, // 边界：5 根日线聚出 1 根周 K
  { range: '1M', period: 'M' }, // 边界：22 根日线聚出 2 根月 K
];

const out = { cases: [] };
for (const sym of syms) {
  const series = genSeries(sym);
  for (const c of combos) {
    const bars = drawerBars(series, c.range, c.period);
    out.cases.push({
      code: sym.code,
      range: c.range,
      period: c.period,
      n: bars.length,
      bars: bars.map((b) => ({
        t: fmtLocal(b.t), o: b.o, h: b.h, l: b.l, c: b.c, v: b.v,
      })),
    });
  }
}

fs.writeFileSync(outPath, JSON.stringify(out));
console.log('已写出', outPath, '用例数', out.cases.length);
const byKey = {};
for (const c of out.cases) byKey[`${c.range}/${c.period}`] = c.n;
console.log('各组合根数(600519):', JSON.stringify(
  Object.fromEntries(Object.entries(byKey).filter(([k]) => k))
));
