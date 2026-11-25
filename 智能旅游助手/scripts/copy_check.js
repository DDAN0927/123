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
const zlib = require("zlib");

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

/* 第二个真实数据源：知识库的景点清单档。
 * 「1558」是地图上的景点数，「9332」是攻略库清单档里收录的景点名总数 ——
 * 两个数字都真实，但说的不是同一件事。文案里出现哪个都必须能对上其中之一，
 * 否则就是「宣传数字无数据支撑」。这里直接数 md 里的「共收录 N 个景点」，
 * 不引入第二份基准常量（写死的常量迟早会和数据脱节）。
 */
function kbSpotTotal() {
  const dir = path.join(ROOT, "knowledge_base/spots");
  if (!fs.existsSync(dir)) return 0;
  let sum = 0;
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith(".md")) continue;
    const m = fs.readFileSync(path.join(dir, f), "utf8").match(/共收录\s*(\d+)\s*个景点/);
    if (m) sum += +m[1];
  }
  return sum;
}
const KB_SPOT_N = kbSpotTotal();

/* 第三个真实数据源：SpringBoot 侧的「景点库」种子表（346 城 / 8274 条）。
 * 11-18 的提交把景点做成了独立数据表，README 里于是同时出现「地图 1558」和
 * 「景点表 8274」——两个数都真实，只是说的不是同一件事。这里直接读种子 JSON
 * 现算，不写死常量；**也不连 H2**——CI 里没有数据库，连了就会在 CI 上静默变成 0，
 * 那等于把这道门禁关掉。
 */
function seedSpotStats() {
  const f = path.join(ROOT, "server/src/main/resources/seed/spots.json");
  if (!fs.existsSync(f)) return { cities: 0, rows: 0 };
  const raw = JSON.parse(fs.readFileSync(f, "utf8"));
  const cities = Object.keys(raw);
  const rows = cities.reduce((s, c) => s + (Array.isArray(raw[c]) ? raw[c].length : 0), 0);
  return { cities: cities.length, rows };
}
const SEED = seedSpotStats();
const SEED_ROWS = SEED.rows;
const SEED_CITIES = SEED.cities;

const SPOT_OK = [SPOT_N, KB_SPOT_N, SEED_ROWS].filter((n) => n > 0);
const SPOT_LABEL = `${SPOT_N}（地图）/ ${KB_SPOT_N}（清单档）/ ${SEED_ROWS}（景点表 ${SEED_CITIES} 城）`;
const spotOk = (n, loose) => SPOT_OK.includes(n) || (loose && n <= Math.max(...SPOT_OK));

/* 城市数同理：「355 城」是地图总覆盖，「349 城」是清单档文件数，「346 城」是高德
 * 实际覆盖到的城市数，「6 城」是精编攻略，「165 城」是导览档实际生效数。它们都是
 * 真实子集，不能因为不等于 355 就判成虚报。基准值全部现算，不写常量。
 *
 * 「生效数」与「文件数」必须分开算：guides/ 下有 171 篇，其中 6 篇是精编城市，
 * 索引器与覆盖判定都会让位给精编档，所以对外只能说 165 城。
 */
function countFiles(dir) {
  return fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => f.endsWith(".md")).length : 0;
}
function listMd(dir) {
  return fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => f.endsWith(".md")) : [];
}
const FULL_N = countFiles(path.join(ROOT, "knowledge_base"));
const LISTED_N = countFiles(path.join(ROOT, "knowledge_base/spots"));

const FULL_FILES = new Set(listMd(path.join(ROOT, "knowledge_base")));
const GUIDE_FILES = listMd(path.join(ROOT, "knowledge_base/guides"));
const GUIDE_SET = new Set(GUIDE_FILES);
const GUIDED_N = GUIDE_FILES.length;                                     // 文件数 171
const GUIDED_EFFECTIVE = GUIDE_FILES.filter((f) => !FULL_FILES.has(f)).length;  // 生效 165
const LISTED_EFFECTIVE = listMd(path.join(ROOT, "knowledge_base/spots"))
  .filter((f) => !GUIDE_SET.has(f)).length;                              // 生效 184

const AMAP_N = (() => {
  try {
    return Object.keys(JSON.parse(fs.readFileSync(path.join(ROOT, "datasets/amap_spots.json"), "utf8"))).length;
  } catch (e) { return 0; }
})();
const CITY_OK = [CITY_N, FULL_N, LISTED_N, AMAP_N, GUIDED_N, GUIDED_EFFECTIVE, LISTED_EFFECTIVE, SEED_CITIES]
  .filter((n) => n > 0);
const CITY_LABEL = `${CITY_N}（地图）/ ${LISTED_N}（清单档文件）/ ${LISTED_EFFECTIVE}（清单档生效）/ `
  + `${GUIDED_N}（导览档文件）/ ${GUIDED_EFFECTIVE}（导览档生效）/ ${AMAP_N}（高德）/ `
  + `${SEED_CITIES}（景点表）/ ${FULL_N}（精编）`;
const cityOk = (n, loose) => CITY_OK.includes(n) || (loose && n <= CITY_N);

console.log(`基准值：${CITY_N} 城 / ${SPOT_N} 个景点 / ${FOOD_N} 城有美食街或夜市 / `
  + `清单档 ${LISTED_N} 城 ${KB_SPOT_N} 个景点名 / 导览档 ${GUIDED_N} 篇（生效 ${GUIDED_EFFECTIVE} 城）`
  + ` / 高德覆盖 ${AMAP_N} 城 / 景点表 ${SEED_CITIES} 城 ${SEED_ROWS} 条`);

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
    // 允许「NNN+」的模糊写法：只要不超过真实值即视为诚实
    const loose = new RegExp(`\\b${n}\\+`).test(html);
    ok(`${page} 城市数 ${n} 属于真实统计值`,
      cityOk(n, loose), `文案写 ${n}，实际 ${CITY_LABEL}`);
  }
  for (const n of spotNums(html)) {
    const loose = new RegExp(`\\b${n}\\+`).test(html);
    ok(`${page} 景点数 ${n} 属于真实统计值`,
      spotOk(n, loose), `文案写 ${n}，实际 ${SPOT_LABEL}`);
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
  ok(`README 城市数 ${n} 属于真实统计值`,
    cityOk(n, loose), `README 写 ${n}，实际 ${CITY_LABEL}`);
}
for (const n of spotNums(readme)) {
  const loose = new RegExp(`\\b${n}\\+`).test(readme);
  ok(`README 景点数 ${n} 属于真实统计值`,
    spotOk(n, loose), `README 写 ${n}，实际 ${SPOT_LABEL}`);
}
if (/美食街|夜市/.test(readme)) {
  const m = readme.match(/(\d{1,3})\s*城的?美食街/);
  if (m) {
    ok(`README 美食城市数 ${m[1]} 与真实 ${FOOD_N} 一致`, +m[1] === FOOD_N,
      `README 写 ${m[1]}，实际 ${FOOD_N}`);
  }
}

// 2.3 前端体积：README 声称的 gzip 体积必须与实测对得上
//
// 为什么用 ±5% 区间而不是精确相等：gzip 的字节数取决于 zlib 实现，Node 大版本
// 升级会让同一份文件压缩后差几百字节。钉死等号的门禁迟早因为「换了个 Node」变红，
// 然后被人用 --no-verify 绕过去 —— 那还不如不设。±5% 足以抓住两种真问题：
// 「文案写 92KB、实际 826KB」和「新加了 1MB vendor 却没改文案」。
function gzTotal(excludeVendor) {
  let sum = 0;
  const walk = (dir) => {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, ent.name);
      if (ent.isDirectory()) { walk(p); continue; }
      if (![".js", ".css", ".html"].includes(path.extname(p).toLowerCase())) continue;
      if (excludeVendor && /[\\/]vendor[\\/]/.test(p)) continue;
      sum += zlib.gzipSync(fs.readFileSync(p), { level: 9 }).length;
    }
  };
  walk(path.join(ROOT, "frontend/static"));
  return Math.round(sum / 1024);
}
const GZ_ALL = gzTotal(false);
const GZ_CODE = gzTotal(true);
const volLine = (readme.split("\n").find((l) => /gzip/i.test(l)) || "").trim();
const volStated = [...volLine.matchAll(/(\d+)\s*KB/g)].map((m) => +m[1]);
const near = (stated, actual) => Math.abs(stated - actual) / actual <= 0.05;
for (const [label, actual] of [["含 vendor", GZ_ALL], ["不含 vendor", GZ_CODE]]) {
  ok(`README 前端 gzip 体积（${label}）${actual}KB 与实测一致`,
    volStated.some((n) => near(n, actual)),
    `实测 ${actual}KB；README 该行写 ${volStated.join(" / ") || "（无 KB 数字）"}KB：${volLine.slice(0, 90)}`);
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
