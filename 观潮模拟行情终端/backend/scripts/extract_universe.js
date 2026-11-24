/* 从 index.html 抽取 UNIVERSE 数组，产出后端数据资产 backend/data/universe.json。
 *
 * 为什么不手抄：UNIVERSE 有 37 条，每条含 thesis/risks 多行文案，手抄必然出错，
 * 且前端一改就不同步。抽取能保证"后端看到的标的就是前端在用的标的"。
 *
 * 用法: node backend/scripts/extract_universe.js [index.html] [输出路径]
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const htmlPath = process.argv[2] || path.join(ROOT, 'index.html');
const outPath = process.argv[3] || path.join(ROOT, 'backend', 'data', 'universe.json');

const html = fs.readFileSync(htmlPath, 'utf8');

const startMark = 'const UNIVERSE = [';
const i = html.indexOf(startMark);
if (i < 0) throw new Error('未找到 const UNIVERSE');
// 数组以 "\n];" 收尾；元素内部不会出现该模式
const j = html.indexOf('\n];', i);
if (j < 0) throw new Error('未找到 UNIVERSE 结尾');
const seg = html.slice(i, j + 3);

const UNIVERSE = new Function(`${seg}; return UNIVERSE;`)();
if (!Array.isArray(UNIVERSE) || !UNIVERSE.length) throw new Error('抽取结果不是非空数组');

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(UNIVERSE));

const markets = {};
for (const s of UNIVERSE) markets[s.market] = (markets[s.market] || 0) + 1;
const missing = UNIVERSE.filter((s) => s.price == null || s.vol == null || s.drift == null);

console.log(`已写出 ${outPath}`);
console.log(`标的数: ${UNIVERSE.length}`);
console.log('市场分布:', JSON.stringify(markets));
console.log(`缺 price/vol/drift 的标的: ${missing.length}`);
if (missing.length) {
  console.log('  ' + missing.map((s) => s.code).join(', '));
}
