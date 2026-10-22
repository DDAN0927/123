/* 文案数字自校验
 * ---------------------------------------------------------------------------
 * 站点文案里的「355 城 / 1558 个景点」这类数字，是从 geo-data.js 真实数据里数出来的。
 * 一旦有人加了城市却忘了改文案，就会出现「宣传 356 城、实际 355 城」这种
 * 一眼被戳穿的硬伤。本脚本直接解析 geo-data.js，把所有对外文案里的数字逐一比对。
 *
 * 运行：node scripts/copy_check.js
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
let pass = 0;
const fails = [];

function ok(name, cond, detail) {
  if (cond) { pass++; return; }
  fails.push(name + (detail ? "  → " + detail : ""));
}

// ---------- 1) 从真实数据算出基准值 ----------
global.window = {};
require(path.join(ROOT, "frontend/static/assets/js/geo-data.js"));
const GEO = global.window.CITY_GEO;
const cities = Object.keys(GEO);
let spots = 0;
const foodCities = new Set();
for (const c of cities) {
  const list = GEO[c].spots || [];
  spots += list.length;
  if (list.some((x) => /美食|夜市|小吃/.test(x[3] || ""))) foodCities.add(c);
}
const CITY_N = cities.length;
const SPOT_N = spots;
const FOOD_N = foodCities.size;
console.log(`基准值：${CITY_N} 城 / ${SPOT_N} 个景点 / ${FOOD_N} 城有美食街或夜市`);

// ---------- 2) 逐个文案文件比对 ----------
const read = (p) => fs.readFileSync(path.join(ROOT, p), "utf8");

/** 从文本里抽出所有「N 城」/「N 座城市」的 N（排除「N 城的美食街」这种限定语） */
function cityNums(text) {
  return [...text.matchAll(/(\d{2,4})\s*(?:座城市|个城市|城(?!市|的))/g)].map((m) => +m[1]);
}
/** 从文本里抽出所有「N 个景点」/「N+ 景点」的 N */
function spotNums(text) {
  return [...text.matchAll(/(\d{3,5})\s*\+?\s*个?景点/g)].map((m) => +m[1]);
}

// 2.1 所有对外页面
const pages = fs.readdirSync(path.join(ROOT, "frontend/static"))
  .filter((f) => f.endsWith(".html"));

for (const page of pages) {
  const file = "frontend/static/" + page;
  const html = read(file);

  for (const n of cityNums(html)) {
    // 允许「NNN+」的模糊写法：只要不低于真实值即视为诚实
    const loose = new RegExp(`\\b${n}\\+`).test(html);
    ok(`${page} 城市数 ${n} 与真实 ${CITY_N} 一致`,
      n === CITY_N || (loose && n <= CITY_N), `文案写 ${n}，实际 ${CITY_N}`);
  }
  for (const n of spotNums(html)) {
    const loose = new RegExp(`\\b${n}\\+`).test(html);
    ok(`${page} 景点数 ${n} 与真实 ${SPOT_N} 一致`,
      n === SPOT_N || (loose && n <= SPOT_N), `文案写 ${n}，实际 ${SPOT_N}`);
  }

  // data-count 动画数字：必须精确等于真实值，不能取整、不能虚报
  const counts = [...html.matchAll(/data-count="(\d+)"/g)].map((m) => +m[1]);
  for (const n of counts) {
    // 6（顾问数）/ 3（路线方式）等非地理数字不在此校验范围
    if (n > 100) {
      ok(`${page} 动画数字 ${n} 属于真实统计值`,
        n === CITY_N || n === SPOT_N, `data-count=${n} 既不是城市数也不是景点数`);
    }
  }
}

// 2.2 README（招聘方第一眼看的就是它）
const readme = read("README.md");
for (const n of cityNums(readme)) {
  const loose = new RegExp(`\\b${n}\\+`).test(readme);
  ok(`README 城市数 ${n} 与真实 ${CITY_N} 一致`,
    n === CITY_N || (loose && n <= CITY_N), `README 写 ${n}，实际 ${CITY_N}`);
}
for (const n of spotNums(readme)) {
  const loose = new RegExp(`\\b${n}\\+`).test(readme);
  ok(`README 景点数 ${n} 与真实 ${SPOT_N} 一致`,
    n === SPOT_N || (loose && n <= SPOT_N), `README 写 ${n}，实际 ${SPOT_N}`);
}
if (/美食街|夜市/.test(readme)) {
  const m = readme.match(/(\d{1,3})\s*城的?美食街/);
  if (m) {
    ok(`README 美食城市数 ${m[1]} 与真实 ${FOOD_N} 一致`, +m[1] === FOOD_N,
      `README 写 ${m[1]}，实际 ${FOOD_N}`);
  }
}

// ---------- 3) 结构自检：不允许出现「无数据支撑」的百分比 ----------
const allText = pages.map((p) => read("frontend/static/" + p)).join("\n") + readme;
const badPct = [...allText.matchAll(/(\d{1,3})\s*%\s*(?:用户满意度|好评率|满意度)/g)];
ok("没有编造的满意度百分比", badPct.length === 0,
  "发现：" + badPct.map((m) => m[0]).join("、"));

// ---------- 汇总 ----------
console.log(`\n通过 ${pass} 项`);
if (fails.length) {
  console.log(`失败 ${fails.length} 项：`);
  fails.forEach((f) => console.log("  ❌ " + f));
  process.exit(1);
}
console.log("✅ 文案数字全部与真实数据一致");
