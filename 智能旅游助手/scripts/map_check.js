/**
 * 高德地图模板回归校验（jsdom）：
 * 从 app.js 中抽取 renderAmapCity / renderAmapRoute / wgs84ToGcj02，真实调用后
 * 解析其生成的 iframe srcdoc，断言本次修复的三个问题：
 *   1) 城市地图容器高度塌陷：内层 html,body 必须有 height:100%，且 #am-map 用 flex 撑满；
 *   2) JS API 2.0 缺少安全密钥：window._AMapSecurityConfig 必须在 amap 脚本「之前」注入；
 *   3) 加载失败时一片空白：必须有 typeof AMap==="undefined" 的兜底提示。
 * 同时断言 srcdoc 已做引号转义（否则 iframe 属性会被提前截断）。
 *
 * 用法（需 jsdom）：
 *   NODE_PATH=<managed-node-workspace>/node_modules node scripts/map_check.js
 */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const appjs = fs.readFileSync(
  path.join(__dirname, "..", "frontend", "static", "assets", "js", "app.js"),
  "utf8"
);

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log("✅ " + name); }
  else { fail++; console.log("❌ " + name + (extra ? "  → " + extra : "")); }
}

/* ---------- 按「唯一结束标记」抽取函数源码 ---------- */
function slice(startMark, endMark) {
  const a = appjs.indexOf(startMark);
  if (a < 0) throw new Error("找不到起始标记: " + startMark);
  const b = appjs.indexOf(endMark, a);
  if (b < 0) throw new Error("找不到结束标记: " + endMark);
  return appjs.slice(a, b);
}

const wgsSrc = slice("function wgs84ToGcj02(", "  /* ---------- 高德地图模板（城市景点） ---------- */");
const escSrc = slice("function escapeHtml(", "function mdInline(");
const citySrc = slice("function renderAmapCity(", "  /* ---------- 高德地图模板（跨城路线） ---------- */");
const routeSrc = slice("function renderAmapRoute(", "  /* ---------- 城市选择辅助 ---------- */");

const mKey = appjs.match(/const AMAP_KEY\s*=\s*"([^"]+)"/);
const mCode = appjs.match(/const AMAP_JS_CODE\s*=\s*"([^"]+)"/);
const mFail = appjs.match(/const AMAP_FAIL_HTML\s*=\s*([\s\S]*?);\r?\n/);
ok("抽取到 AMAP_KEY / AMAP_JS_CODE", !!(mKey && mCode));
ok("抽取到 AMAP_FAIL_HTML", !!mFail);

/* ---------- 在 jsdom 中执行被抽取的函数 ---------- */
const dom = new JSDOM(
  '<!doctype html><html><body><div id="amap-wrap"></div><div id="tr-map"></div></body></html>',
  { url: "http://localhost/map.html", runScripts: "outside-only" }
);
const { window } = dom;
const document = window.document;

const factory = new Function(
  "window", "document", "AMAP_KEY", "AMAP_JS_CODE", "AMAP_FAIL_HTML",
  escSrc + "\n" + wgsSrc + "\n" + citySrc + "\n" + routeSrc +
  "\nreturn { renderAmapCity: renderAmapCity, renderAmapRoute: renderAmapRoute };"
);

const AMAP_FAIL_HTML = mFail
  ? eval(mFail[1].trim()) // 常量字面量，安全
  : "";
const api = factory(window, document, mKey[1], mCode[1], AMAP_FAIL_HTML);

window.CITY_GEO = {
  北京: { center: [39.9042, 116.4074] },
  上海: { center: [31.2304, 121.4737] },
};

/* ---------- 构造一次真实渲染 ---------- */
api.renderAmapCity("amap-wrap", "北京", {
  center: [39.9042, 116.4074],
  spots: [
    ["故宫博物院", 39.9163, 116.3972, "古迹"],
    ["颐和园", 39.9999, 116.2755, "公园"],
  ],
});
api.renderAmapRoute("tr-map", "北京", "上海");

function srcdocOf(id) {
  const iframe = document.getElementById(id).querySelector("iframe");
  ok(id + "：已生成 iframe", !!iframe);
  if (!iframe) return "";
  const raw = iframe.getAttribute("srcdoc") || "";
  ok(id + "：srcdoc 非空且含 doctype", /<!DOCTYPE html>/i.test(raw));
  return raw;
}

function parse(html) {
  return new JSDOM(html).window.document;
}

/* ================= 城市地图 ================= */
const cityHtml = srcdocOf("amap-wrap");
const cd = parse(cityHtml);
const cityStyle = cd.querySelector("style").textContent;

ok("城市图：html,body 设了 height:100%（修复高度塌陷）",
  /html\s*,\s*body\s*\{[^}]*height\s*:\s*100%/.test(cityStyle));
ok("城市图：body 为纵向 flex（让地图吃掉剩余高度）",
  /body\s*\{[^}]*display\s*:\s*flex/.test(cityStyle) && /flex-direction\s*:\s*column/.test(cityStyle));
const amMapRule = (cityStyle.match(/#am-map\s*\{[^}]*\}/) || [""])[0];
ok("城市图：#am-map 用 flex:1 撑满而非无效的 height:100%",
  /flex\s*:\s*1\s+1\s+auto/.test(amMapRule) && /min-height\s*:\s*0/.test(amMapRule),
  amMapRule.replace(/\s+/g, " "));

const cityScripts = Array.from(cd.querySelectorAll("script"));
const secIdx = cityScripts.findIndex((s) => /_AMapSecurityConfig/.test(s.textContent));
const apiIdx = cityScripts.findIndex((s) => /webapi\.amap\.com\/maps/.test(s.src));
ok("城市图：找到安全密钥脚本与 amap 脚本", secIdx >= 0 && apiIdx >= 0, `sec=${secIdx} api=${apiIdx}`);
ok("城市图：_AMapSecurityConfig 注入在 amap 脚本之前（否则报 INVALID_USER_SCODE）",
  secIdx >= 0 && apiIdx >= 0 && secIdx < apiIdx);
ok("城市图：安全密钥取值与 .env 一致",
  new RegExp(mCode[1]).test(cityScripts[secIdx] ? cityScripts[secIdx].textContent : ""));
ok("城市图：amap 脚本 key 使用常量而非硬编码遗漏",
  apiIdx >= 0 && cityScripts[apiIdx].src.indexOf(mKey[1]) >= 0);
ok("城市图：有 typeof AMap==='undefined' 兜底，失败时给出排查提示",
  cityHtml.indexOf('typeof AMap==="undefined"') >= 0 && cityHtml.indexOf("地图加载失败") >= 0);
ok("城市图：兜底 HTML 已正确转义进 srcdoc（无裸引号截断）",
  /am-fail/.test(cityHtml));
ok("城市图：.am-fail 样式已定义（失败提示可见）", /\.am-fail\{/.test(cityStyle.replace(/\s/g, "")));

/* ================= 跨城路线图 ================= */
const routeHtml = srcdocOf("tr-map");
const rd = parse(routeHtml);
const routeStyle = rd.querySelector("style").textContent;
const rScripts = Array.from(rd.querySelectorAll("script"));
const rSec = rScripts.findIndex((s) => /_AMapSecurityConfig/.test(s.textContent));
const rApi = rScripts.findIndex((s) => /webapi\.amap\.com\/maps/.test(s.src));
ok("跨城图：html,body 保持 height:100%", /html,body\{height:100%\}/.test(routeStyle.replace(/\s/g, "")));
ok("跨城图：_AMapSecurityConfig 注入在 amap 脚本之前", rSec >= 0 && rApi >= 0 && rSec < rApi);
ok("跨城图：有 AMap 兜底提示", routeHtml.indexOf('typeof AMap==="undefined"') >= 0);
ok("跨城图：.am-fail 样式已定义（*{margin:0} 会把它压扁，必须显式覆盖）",
  /\.am-fail\{/.test(routeStyle.replace(/\s/g, "")) && /\.am-fail\{[^}]*padding/.test(routeStyle.replace(/\s/g, "")));

/* ================= 注入防御：城市名里塞尖括号 ================= */
// 城市名来自 CITY_GEO，正常不会带尖括号；这里故意造一个脏名字，
// 确认「万一有人把数据改脏了」也不会把 iframe 里的 HTML 结构撕开。
const DIRTY = 'A<b>"c';
window.CITY_GEO[DIRTY] = { center: [30.0, 120.0] };
api.renderAmapRoute("tr-map", DIRTY, "上海");
const dirtyIframe = document.getElementById("tr-map").querySelector("iframe");
const dirty = dirtyIframe ? dirtyIframe.getAttribute("srcdoc") || "" : "";
// 注意：srcdoc 里本来就有合法的 <b>（AMAP_FAIL_HTML 的兜底提示），
// 所以不能笼统断言「没有 <b>」，要盯住脏城市名本身。
ok("跨城图：城市名中的 < > 已转义（不会注入 HTML 标签）",
  dirty.indexOf("A<b>") < 0 && dirty.indexOf("A&lt;b&gt;") >= 0);
ok("跨城图：JSON 载荷里的 < 已转成 \\u003c", dirty.indexOf("\\u003c") >= 0);

console.log("\n通过 " + pass + " / " + (pass + fail));
process.exit(fail ? 1 : 0);
