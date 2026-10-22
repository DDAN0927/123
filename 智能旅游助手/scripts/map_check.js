/**
 * 高德地图模板回归校验（jsdom）：
 * 从 app.js 中抽取 renderAmapCity / renderAmapRoute / wgs84ToGcj02，真实调用后
 * 解析其生成的 iframe srcdoc，断言：
 *   1) 城市地图容器高度塌陷：内层 html,body 必须有 height:100%，且 #am-map 用 flex 撑满；
 *   2) JS API 2.0 缺少安全密钥：window._AMapSecurityConfig 必须在 amap 脚本「之前」注入；
 *   3) 加载失败时一片空白：必须有 typeof AMap==="undefined" 的兜底提示；
 *   4) 前端不再硬编码 Key，改为 GET /api/config 下发；未配置时给出明确提示；
 *   5) srcdoc 已做引号转义（否则 iframe 属性会被提前截断）。
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
// 注意：这两个函数现在是 async 的，起始标记必须带上 "async "，
// 否则切出来的源码丢了 async 关键字，里面一句 await 就变成语法错误。
const citySrc = slice("async function renderAmapCity(", "  /* ---------- 高德地图模板（跨城路线） ---------- */");
const routeSrc = slice("async function renderAmapRoute(", "  /* ---------- 城市选择辅助 ---------- */");

const mFail = appjs.match(/const AMAP_FAIL_HTML\s*=\s*([\s\S]*?);\r?\n/);
ok("抽取到 AMAP_FAIL_HTML", !!mFail);

// Key 改为运行时下发后，前端源码里不应再出现硬编码的 Key 字面量
ok("前端不再硬编码高德 Key（改为 /api/config 下发）",
  /\/api\/config/.test(appjs) && !/const\s+AMAP_KEY\s*=\s*"/.test(appjs));

/* ---------- 在 jsdom 中执行被抽取的函数 ---------- */
const TEST_KEY = "test-key-0123456789";
const TEST_CODE = "test-jscode-abcdef";

function makeApi(dom, key, code) {
  const { window } = dom;
  const document = window.document;
  // 替身：把「异步取配置」压平成同步就绪状态，方便断言模板产物
  const stub = `
    let AMAP_KEY = ${JSON.stringify(key)};
    let AMAP_JS_CODE = ${JSON.stringify(code)};
    function loadPublicConfig() { return Promise.resolve({}); }
  `;
  const factory = new Function(
    "window", "document", "AMAP_FAIL_HTML",
    stub + escSrc + "\n" + wgsSrc + "\n" + citySrc + "\n" + routeSrc +
    "\nreturn { renderAmapCity: renderAmapCity, renderAmapRoute: renderAmapRoute };"
  );
  const AMAP_FAIL_HTML = mFail ? eval(mFail[1].trim()) : "";
  window.CITY_GEO = {
    北京: { center: [39.9042, 116.4074] },
    上海: { center: [31.2304, 121.4737] },
  };
  return factory(window, document, AMAP_FAIL_HTML);
}

function parse(html) {
  return new JSDOM(html).window.document;
}

(async () => {
  /* ================= 正常配置 ================= */
  const dom = new JSDOM(
    '<!doctype html><html><body><div id="amap-wrap"></div><div id="tr-map"></div></body></html>',
    { url: "http://localhost/map.html", runScripts: "outside-only" }
  );
  const { window } = dom;
  const document = window.document;
  const api = makeApi(dom, TEST_KEY, TEST_CODE);

  await api.renderAmapCity("amap-wrap", "北京", {
    center: [39.9042, 116.4074],
    spots: [
      ["故宫博物院", 39.9163, 116.3972, "古迹"],
      ["颐和园", 39.9999, 116.2755, "公园"],
    ],
  });
  await api.renderAmapRoute("tr-map", "北京", "上海");

  function srcdocOf(id) {
    const iframe = document.getElementById(id).querySelector("iframe");
    ok(id + "：已生成 iframe", !!iframe);
    if (!iframe) return "";
    const raw = iframe.getAttribute("srcdoc") || "";
    ok(id + "：srcdoc 非空且含 doctype", /<!DOCTYPE html>/i.test(raw));
    return raw;
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
  ok("城市图：安全密钥取的是运行时配置（不再写死）",
    secIdx >= 0 && cityScripts[secIdx].textContent.indexOf(TEST_CODE) >= 0);
  ok("城市图：amap 脚本 key 取的是运行时配置",
    apiIdx >= 0 && cityScripts[apiIdx].src.indexOf(TEST_KEY) >= 0);
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
  await api.renderAmapRoute("tr-map", DIRTY, "上海");
  const dirtyIframe = document.getElementById("tr-map").querySelector("iframe");
  const dirty = dirtyIframe ? dirtyIframe.getAttribute("srcdoc") || "" : "";
  // 注意：srcdoc 里本来就有合法的 <b>（AMAP_FAIL_HTML 的兜底提示），
  // 所以不能笼统断言「没有 <b>」，要盯住脏城市名本身。
  ok("跨城图：城市名中的 < > 已转义（不会注入 HTML 标签）",
    dirty.indexOf("A<b>") < 0 && dirty.indexOf("A&lt;b&gt;") >= 0);
  ok("跨城图：JSON 载荷里的 < 已转成 \\u003c", dirty.indexOf("\\u003c") >= 0);

  /* ================= 未配置 Key：给提示而不是空白 ================= */
  const dom2 = new JSDOM(
    '<!doctype html><html><body><div id="amap-wrap"></div><div id="tr-map"></div></body></html>',
    { url: "http://localhost/map.html", runScripts: "outside-only" }
  );
  const api2 = makeApi(dom2, "", "");
  await api2.renderAmapCity("amap-wrap", "北京", { center: [39.9042, 116.4074], spots: [] });
  const noKeyBox = dom2.window.document.getElementById("amap-wrap");
  ok("未配置 Key 时：不生成 iframe，直接展示排查提示",
    !noKeyBox.querySelector("iframe") && /地图加载失败/.test(noKeyBox.innerHTML));
  ok("未配置 Key 时的提示里包含 AMAP_KEY 字样（指向正确的配置项）",
    /AMAP_KEY/.test(noKeyBox.innerHTML));

  console.log("\n通过 " + pass + " / " + (pass + fail));
  process.exit(fail ? 1 : 0);
})();
