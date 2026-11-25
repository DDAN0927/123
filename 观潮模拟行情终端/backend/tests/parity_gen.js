/* 前后端序列一致性基准生成器。
 *
 * 不从别处抄算法 —— 直接从 index.html 里**抽取真实源码**（mulberry32 / gauss /
 * hashStr / D2 / TODAY / SERIES_DAYS / genSeries），在 Node 里 eval 后运行。
 * 这样对比的才是"前端实际跑的代码"，而不是我凭记忆重写的版本。
 *
 * 用法: node parity_gen.js <index.html 路径> <输出 json 路径>
 */
const fs = require('fs');
const path = require('path');

const htmlPath = process.argv[2] || path.join(__dirname, '..', '..', 'index.html');
const outPath = process.argv[3] || path.join(__dirname, 'parity_js.json');
const html = fs.readFileSync(htmlPath, 'utf8');

function grab(startMark, endMark) {
  const i = html.indexOf(startMark);
  if (i < 0) throw new Error('未找到起点: ' + startMark);
  const j = html.indexOf(endMark, i);
  if (j < 0) throw new Error('未找到终点: ' + endMark);
  return html.slice(i, j);
}

const rngSrc = grab('function mulberry32(seed) {', 'const UNIVERSE'); // 含 gauss/hashStr/D2/TODAY
const genSrc = grab('function genSeries(sym) {', 'const CURATED');
const daysMatch = html.match(/const SERIES_DAYS\s*=\s*(\d+)/);
if (!daysMatch) throw new Error('未找到 SERIES_DAYS');

const code = `
  const SERIES_DAYS = ${daysMatch[1]};
  ${rngSrc}
  ${genSrc}
  return { genSeries, hashStr, SERIES_DAYS };
`;
const { genSeries, hashStr, SERIES_DAYS } = new Function(code)();

// 三个不同市场的标的，参数取自 index.html 的 UNIVERSE 真实值
const cases = [
  { code: '600519', price: 1624.5, vol: 0.27, drift: 0.09, mcap: 20412 },
  { code: '300750', price: 258.4, vol: 0.38, drift: 0.14, mcap: 11368 },
  { code: 'AAPL', price: 242.7, vol: 0.24, drift: 0.12, mcap: 36210 },
  { code: 'BTC', price: 96420, vol: 0.62, drift: 0.24, mcap: 19120 },
];

// 必须按**本地**日期格式化：前端 t 是 new Date(2026,10,17) 本地午夜，
// 用 toISOString() 会按 UTC 转换并在 +08:00 时区倒退一天（11-17 → 11-16），
// 与后端 date(2026,11,17) 对不上。这是时区陷阱，不是算法差异。
const fmtLocal = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const out = { series_days: SERIES_DAYS, cases: [] };
for (const c of cases) {
  const bars = genSeries(c);
  out.cases.push({
    code: c.code,
    seed: hashStr(c.code),
    n: bars.length,
    last_close: bars[bars.length - 1].c,
    first_date: fmtLocal(bars[0].t),
    last_date: fmtLocal(bars[bars.length - 1].t),
    bars: bars.map((b) => ({
      t: fmtLocal(b.t),
      o: b.o, h: b.h, l: b.l, c: b.c, v: b.v,
    })),
  });
}

fs.writeFileSync(outPath, JSON.stringify(out));
console.log('已写出', outPath);
console.log('SERIES_DAYS =', SERIES_DAYS);
for (const c of out.cases) {
  console.log(`  ${c.code.padEnd(8)} seed=${c.seed} n=${c.n} last=${c.last_close.toFixed(4)} 区间=${c.first_date}~${c.last_date}`);
}
