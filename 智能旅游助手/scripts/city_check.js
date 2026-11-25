/**
 * 城市选择器回归校验（jsdom）：
 * 真实加载 map.html / transit.html（geo-data → app.js → main.js），断言：
 *   1) 城市下拉框按拼音首字母分成 <optgroup>，且字母升序；
 *   2) 每个城市在选项里只出现一次，数量与 CITY_GEO 一致；
 *   3) 城市名互相包含时取最长匹配（「峨眉山」不能落到「眉山」、「马鞍山」不能落到「鞍山」）；
 *   4) 别名（地区名 / 景区名）能正确落到所属城市。
 *
 * 用法（需 jsdom）：
 *   NODE_PATH=<managed-node-workspace>/node_modules node scripts/city_check.js
 */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const root = path.join(__dirname, "..", "frontend", "static");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");

const geo = read("assets/js/geo-data.js");
const appjs = read("assets/js/app.js");
const mainjs = read("assets/js/main.js");
const inline = (s) => s.replace(/<\/script>/gi, "<\\/script>");

// HTML 里的资源引用带 ?v=<build>（scripts/stamp_assets.py 打的版本号），
// 这里必须容忍版本参数，否则字符串替换匹配不上、脚本根本没被内联。
const subScript = (html, src, code) =>
  html.replace(
    new RegExp(`<script src="${src.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:\\?v=[\\w.-]+)?"></script>`),
    () => `<script>${code}</script>`
  );

const stub = `
window.matchMedia = function () { return { matches: false, addEventListener: function(){}, removeEventListener: function(){} }; };
window.IntersectionObserver = function () { this.observe=function(){}; this.unobserve=function(){}; this.disconnect=function(){}; };
window.requestAnimationFrame = function (cb) { return setTimeout(function(){ cb(0); }, 0); };
window.cancelAnimationFrame = function (id) { clearTimeout(id); };
window.scrollTo = function () {};
window.fetch = function () {
  // /api/config 会走 r.json()，其余接口走 r.text()，两个都给上，
  // 否则地图页拿不到 AMAP_KEY，只会渲染「未配置」提示而没有 iframe。
  var body = { amap_key: "test-key-0123456789", amap_security_js_code: "test-jscode" };
  return Promise.resolve({
    ok: true, status: 200,
    json: function () { return Promise.resolve(body); },
    text: function () { return Promise.resolve("{}"); },
  });
};
`;

function build(page) {
  // 用替换函数而非替换字符串：String.replace 会把替换值里的 $' / $& 当特殊记号，
  // 一旦源码里出现这类序列，整段脚本会被吃掉。
  const doc = subScript(
    subScript(
      subScript(read(page), "assets/js/geo-data.js", inline(geo)),
      "assets/js/app.js",
      inline(appjs)
    ),
    "assets/js/main.js",
    inline(mainjs)
  ).replace("<body>", () => `<body><script>${stub}</script>`);
  return new JSDOM(doc, {
    url: "http://localhost/" + page,
    runScripts: "dangerously",
    pretendToBeVisual: true,
  });
}

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log("✅ " + name); }
  else { fail++; console.log("❌ " + name + (extra !== undefined ? "  → " + extra : "")); }
}

const mapDom = build("map.html");
const trDom = build("transit.html");

setTimeout(async () => {
  const doc = mapDom.window.document;
  const geoObj = mapDom.window.CITY_GEO;
  const allCities = Object.keys(geoObj);

  /* ---------- 1. 首字母分组 ---------- */
  const sel = doc.querySelector("#map-city");
  ok("地图页城市下拉框存在", !!sel);

  const groups = sel ? Array.from(sel.querySelectorAll("optgroup")) : [];
  ok("下拉框使用了 optgroup 分组", groups.length > 0, groups.length);

  const labels = groups.map((g) => g.getAttribute("label"));
  ok("分组标签都是单个大写字母", labels.every((l) => /^[A-Z]$/.test(l)), labels.join(","));
  ok("分组按字母升序", labels.join("") === labels.slice().sort().join(""), labels.join(","));
  ok("分组数 >= 20", labels.length >= 20, labels.length);

  /* ---------- 2. 选项完整且不重复 ---------- */
  const opts = sel ? Array.from(sel.querySelectorAll("option")).map((o) => o.textContent.trim()) : [];
  ok("选项总数 = 城市总数", opts.length === allCities.length, opts.length + " vs " + allCities.length);
  ok("选项无重复", new Set(opts).size === opts.length, "重复 " + (opts.length - new Set(opts).size));
  const missing = allCities.filter((c) => !opts.includes(c));
  ok("所有城市都在下拉框里", missing.length === 0, missing.slice(0, 5).join(","));

  // 分组内的城市首字母必须与分组标签一致
  let mismatch = [];
  groups.forEach((g) => {
    const L = g.getAttribute("label");
    Array.from(g.querySelectorAll("option")).forEach((o) => {
      const c = o.textContent.trim();
      if (geoObj[c] && geoObj[c].py !== L) mismatch.push(c + "(" + geoObj[c].py + "≠" + L + ")");
    });
  });
  ok("分组标签与城市首字母一致", mismatch.length === 0, mismatch.slice(0, 5).join(","));

  ok("默认选中北京", sel && sel.value === "北京", sel && sel.value);

  /* ---------- 2.5 地图按需加载：点击前不建 iframe，点击后才建 ---------- */
  // 高德 SDK 约 1MB，加载即创建会把首屏 TBT 顶到 6s+（见 map-tbt-options.md）。
  // 新契约：首屏只渲染占位与景点列表；用户点「显示地图」后才注入 iframe。
  // 这里用本地 settle，不依赖后面才声明的 waitFor（const 有 TDZ）。
  const settle = (ms) => new Promise((r) => setTimeout(r, ms || 30));
  const mapWrap = doc.querySelector("#amap-wrap");
  const loadBtn = doc.querySelector("#map-load");

  ok("地图页首屏不创建 iframe（按需加载）", !doc.querySelector("#amap-wrap iframe"));
  ok("地图页首屏显示占位与「显示地图」按钮",
     !!loadBtn && (mapWrap.textContent || "").indexOf("地图按需加载") >= 0);
  ok("占位按钮满足移动端点击区（min-height 48px）",
     !!loadBtn && (loadBtn.getAttribute("style") || "").indexOf("min-height:48px") >= 0,
     loadBtn && loadBtn.getAttribute("style"));
  ok("占位态下景点列表照常渲染（不能白屏）",
     doc.querySelectorAll("#spot-list .spot-item").length > 0,
     doc.querySelectorAll("#spot-list .spot-item").length);

  if (loadBtn) loadBtn.dispatchEvent(new mapDom.window.MouseEvent("click", { bubbles: true }));
  await settle(100);

  const iframeAfterClick = doc.querySelector("#amap-wrap iframe");
  ok("点击「显示地图」后才创建 iframe", !!iframeAfterClick);
  ok("点击后 iframe 里引用了高德 JS API",
     !!iframeAfterClick &&
       (iframeAfterClick.getAttribute("srcdoc") || "").indexOf("webapi.amap.com/maps") >= 0);
  ok("点击后占位按钮被移除", !doc.querySelector("#map-load"));
  ok("点击后只有一个 iframe（不重复创建）",
     doc.querySelectorAll("#amap-wrap iframe").length === 1,
     doc.querySelectorAll("#amap-wrap iframe").length);

  // 已加载后切城市：仍是同一个 iframe，且不应回退到占位态
  const citySwitcher = doc.querySelector("#map-city");
  citySwitcher.value = "上海";
  citySwitcher.dispatchEvent(new mapDom.window.Event("change", { bubbles: true }));
  await settle(100);
  ok("切换城市后仍只有一个 iframe", doc.querySelectorAll("#amap-wrap iframe").length === 1);
  ok("切换城市后不回退到占位态", !doc.querySelector("#map-load"));
  // 复位到北京：后面的用例依赖这个初始态
  citySwitcher.value = "北京";
  citySwitcher.dispatchEvent(new mapDom.window.Event("change", { bubbles: true }));
  await settle(100);

  /* ---------- 3. 最长匹配（本次修复重点） ---------- */
  function filterBy(text) {
    const q = doc.querySelector("#map-query");
    const go = doc.querySelector("#map-go");
    q.value = text;
    go.dispatchEvent(new mapDom.window.MouseEvent("click", { bubbles: true }));
    const h3 = doc.querySelector("#spot-list h3");
    return h3 ? h3.textContent.trim().split(" ")[0] : "";
  }
  ok("「峨眉山 3 天」→ 峨眉山（不是眉山）", filterBy("峨眉山 3 天") === "峨眉山", filterBy("峨眉山 3 天"));
  ok("「马鞍山 2 天」→ 马鞍山（不是鞍山）", filterBy("马鞍山 2 天") === "马鞍山", filterBy("马鞍山 2 天"));
  ok("「长白山 3 天」→ 长白山（不是白山）", filterBy("长白山 3 天") === "长白山", filterBy("长白山 3 天"));
  ok("「北京 3 天」→ 北京", filterBy("北京 3 天") === "北京", filterBy("北京 3 天"));

  /* ---------- 4. 别名落点 ---------- */
  const aliasCases = [
    ["想去梵净山", "铜仁"],
    ["额尔古纳湿地", "呼伦贝尔"],
    ["开平碉楼看看", "江门"],
    ["德天瀑布", "崇左"],
    ["羊卓雍措", "山南"],
    ["青海湖骑行", "共和"],
    ["阿拉善沙漠", "阿拉善左旗"],
    ["吉林雾凇", "吉林市"],
    ["香港购物", "中国香港"],
    ["澳门美食", "中国澳门"],
  ];
  aliasCases.forEach(([q, want]) => {
    const got = filterBy(q);
    ok("别名「" + q + "」→ " + want, got === want, got);
  });

  /* ---------- 5. 景点自定义增删 ---------- */
  const w = mapDom.window;
  w.confirm = function () { return true; };
  const click = (el) => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));

  // 先重置回「北京 + 无筛选」（前面的别名用例把页面留在了中国澳门）
  doc.querySelector("#map-query").value = "";
  const citySelEl = doc.querySelector("#map-city");
  citySelEl.value = "北京";
  citySelEl.dispatchEvent(new w.Event("change", { bubbles: true }));

  const spotNames = () => Array.from(doc.querySelectorAll("#spot-list .spot-item .spot-txt strong"))
    .map((e) => e.textContent.trim());
  const baseCount = spotNames().length;
  ok("景点列表已渲染", baseCount > 0, baseCount);
  ok("每条景点都有删除按钮", doc.querySelectorAll("#spot-list .spot-del").length === baseCount,
     doc.querySelectorAll("#spot-list .spot-del").length);
  ok("初始没有「恢复默认」按钮", !doc.querySelector('#spot-list [data-act="reset"]'));
  ok("添加表单初始是收起的", doc.querySelector("#spot-form").hidden);

  // ---- 添加 ----
  click(doc.querySelector('#spot-list [data-act="add"]'));
  ok("点「＋ 添加」展开表单", !doc.querySelector("#spot-form").hidden);
  doc.querySelector("#sf-name").value = "亮马河";
  doc.querySelector("#sf-cat").value = "自然";
  click(doc.querySelector('#spot-list [data-act="save"]'));
  ok("添加后景点数 +1", spotNames().length === baseCount + 1, spotNames().length);
  ok("新景点出现在列表", spotNames().includes("亮马河"));
  ok("新景点带「自定义」角标",
     Array.from(doc.querySelectorAll("#spot-list .spot-badge")).some((e) => e.textContent.includes("自定义")));
  ok("列表标题带「已自定义」角标",
     (doc.querySelector("#spot-list .spot-head h3") || {}).textContent.includes("已自定义"));
  ok("添加后出现「恢复默认」按钮", !!doc.querySelector('#spot-list [data-act="reset"]'));
  ok("添加已持久化到 localStorage",
     (w.localStorage.getItem("tc_spot_overrides") || "").indexOf("亮马河") >= 0);
  // 地图自 025c213 起改为按需加载（首屏只渲染占位，点「显示地图」才创建 iframe），
  // 而 iframe 的 srcdoc 是在异步链里写的（loadPublicConfig → /api/config → 注入）。
  // 固定 sleep 30ms 在慢机器上会读到「地图加载中…」甚至还没有 iframe，属于竞态。
  // 这里改成轮询到「条件成立」为止：断言的是最终状态，不是多久达成。
  const waitFor = async (fn, ms = 3000) => {
    const end = Date.now() + ms;
    for (;;) {
      const v = fn();
      if (v) return v;
      if (Date.now() > end) return null;
      await new Promise((r) => setTimeout(r, 20));
    }
  };

  const mapFrame = await waitFor(() => {
    const f = doc.querySelector("#amap-wrap iframe");
    return f && f.getAttribute("srcdoc").indexOf("亮马河") >= 0 ? f : null;
  });
  ok("自定义景点也进了地图数据", !!mapFrame,
     mapFrame ? "" : "3s 内 iframe 的 srcdoc 里没有「亮马河」（地图可能仍停在占位态）");

  // ---- 重名 ----
  click(doc.querySelector('#spot-list [data-act="add"]'));
  doc.querySelector("#sf-name").value = "亮马河";
  click(doc.querySelector('#spot-list [data-act="save"]'));
  ok("重名景点被拒绝", doc.querySelector("#sf-err").textContent.indexOf("已存在") >= 0,
     doc.querySelector("#sf-err").textContent);
  ok("重名被拒绝后数量不变", spotNames().length === baseCount + 1, spotNames().length);

  // ---- 非法输入 ----
  doc.querySelector("#sf-name").value = "测试点";
  doc.querySelector("#sf-lat").value = "999";
  doc.querySelector("#sf-lng").value = "116.4";
  click(doc.querySelector('#spot-list [data-act="save"]'));
  ok("越界经纬度被拒绝", doc.querySelector("#sf-err").textContent.indexOf("超出中国范围") >= 0,
     doc.querySelector("#sf-err").textContent);

  doc.querySelector("#sf-lat").value = "abc";
  click(doc.querySelector('#spot-list [data-act="save"]'));
  ok("非数字纬度被拒绝", doc.querySelector("#sf-err").textContent.indexOf("不是有效数字") >= 0,
     doc.querySelector("#sf-err").textContent);

  doc.querySelector("#sf-name").value = "";
  doc.querySelector("#sf-lat").value = "";
  click(doc.querySelector('#spot-list [data-act="save"]'));
  ok("空名称被拒绝", doc.querySelector("#sf-err").textContent.indexOf("请填写") >= 0);

  click(doc.querySelector('#spot-list [data-act="cancel"]'));
  ok("点「取消」收起表单", doc.querySelector("#spot-form").hidden);

  // ---- 注入防护：名字里带 </script> 和标签 ----
  click(doc.querySelector('#spot-list [data-act="add"]'));
  const evil = '</script><img src=x onerror=alert(1)>';
  doc.querySelector("#sf-name").value = evil;
  doc.querySelector("#sf-lat").value = "";
  doc.querySelector("#sf-lng").value = "";
  click(doc.querySelector('#spot-list [data-act="save"]'));
  ok("含 </script> 的景点名被正常保存", spotNames().some((n) => n === evil), spotNames()[spotNames().length - 1]);
  ok("名字里的尖括号被转义（列表里没有真的 img 元素）",
     doc.querySelectorAll("#spot-list img").length === 0);
  // 同上一处：srcdoc 是异步写入的，轮询到条件成立为止，不要固定 sleep。
  const escapedFrame = await waitFor(() => {
    const f = doc.querySelector("#amap-wrap iframe");
    return f && f.getAttribute("srcdoc").indexOf("\\u003c") >= 0 ? f : null;
  });
  ok("地图数据里的尖括号被转成 \\u003c（否则会截断 iframe 脚本）", !!escapedFrame,
     escapedFrame ? "" : "3s 内 srcdoc 里没出现转义后的 \\u003c");

  // ---- 删除 ----
  const beforeDel = spotNames().length;
  click(doc.querySelector("#spot-list .spot-del"));
  ok("点🗑删除后景点数 -1", spotNames().length === beforeDel - 1, spotNames().length);
  ok("删除已持久化", (w.localStorage.getItem("tc_spot_overrides") || "").indexOf("removed") >= 0);

  // ---- 恢复默认 ----
  click(doc.querySelector('#spot-list [data-act="reset"]'));
  ok("恢复默认后回到原始景点数", spotNames().length === baseCount, spotNames().length);
  ok("恢复默认后角标消失", !doc.querySelector("#spot-list .spot-badge"));
  ok("恢复默认后 localStorage 里该城市被清空",
     !(JSON.parse(w.localStorage.getItem("tc_spot_overrides") || "{}")["北京"]));

  // ---- 自定义景点参与自然语言筛选 ----
  click(doc.querySelector('#spot-list [data-act="add"]'));
  doc.querySelector("#sf-name").value = "我的秘密基地";
  doc.querySelector("#sf-cat").value = "公园";
  click(doc.querySelector('#spot-list [data-act="save"]'));
  const qEl = doc.querySelector("#map-query");
  qEl.value = "北京 3 天，想去我的秘密基地";
  click(doc.querySelector("#map-go"));
  ok("自定义景点能被「必去」规则命中",
     !!doc.querySelector("#spot-list .spot-txt") &&
     Array.from(doc.querySelectorAll("#spot-list .spot-item")).some(
       (it) => it.textContent.indexOf("我的秘密基地") >= 0 && it.textContent.indexOf("✅") >= 0),
     (doc.querySelector("#spot-list") || {}).textContent?.slice(0, 60));
  // 收尾
  qEl.value = "";
  click(doc.querySelector("#map-go"));

  /* ---------- 6. 交通页 ---------- */
  const tdoc = trDom.window.document;
  const fromSel = tdoc.querySelector("#tr-from");
  const toSel = tdoc.querySelector("#tr-to");
  ok("交通页出发城市下拉框存在", !!fromSel);
  ok("交通页到达城市下拉框存在", !!toSel);
  ok("交通页出发框已分组", fromSel && fromSel.querySelectorAll("optgroup").length >= 20);
  ok("交通页到达框已分组", toSel && toSel.querySelectorAll("optgroup").length >= 20);
  ok("交通页默认 北京 → 上海", fromSel && toSel && fromSel.value === "北京" && toSel.value === "上海",
     fromSel && toSel ? fromSel.value + "→" + toSel.value : "");
  ok("交通页两框选项数一致",
     fromSel && toSel && fromSel.querySelectorAll("option").length === toSel.querySelectorAll("option").length);

  /* ---------- 7. geo-data.js 数据质量 ---------- */
  // 这份数据是手写的，最容易出的问题是：分类写错、坐标手滑、同城重名、城市景点被删空。
  const CATS = ["地标", "古迹", "公园", "街区", "商圈", "自然", "乐园", "亲子", "体验", "场馆", "美食"];
  let spotTotal = 0, badCat = [], badBbox = [], dupName = [], tooFar = [], thin = [];
  const catCount = {}, foodCities = [];

  allCities.forEach((c) => {
    const info = geoObj[c];
    const names = new Set();
    if (info.spots.length < 3) thin.push(c + "(" + info.spots.length + ")");
    let hasFood = false;
    info.spots.forEach((s) => {
      spotTotal++;
      catCount[s[3]] = (catCount[s[3]] || 0) + 1;
      if (s[3] === "美食") hasFood = true;
      if (CATS.indexOf(s[3]) < 0) badCat.push(c + "/" + s[0] + "=" + s[3]);
      if (!(s[1] >= 3 && s[1] <= 54 && s[2] >= 73 && s[2] <= 136)) badBbox.push(c + "/" + s[0]);
      if (names.has(s[0])) dupName.push(c + "/" + s[0]);
      names.add(s[0]);
      // 景点离城市中心不该超过 6°（约 600km），超过基本是坐标写错了
      if (Math.abs(s[1] - info.center[0]) > 6 || Math.abs(s[2] - info.center[1]) > 6) tooFar.push(c + "/" + s[0]);
    });
    if (hasFood) foodCities.push(c);
  });

  ok("城市数 >= 350", allCities.length >= 350, allCities.length);
  ok("景点总数 >= 1500", spotTotal >= 1500, spotTotal);
  ok("每座城市至少 3 个景点", thin.length === 0, thin.slice(0, 5).join(","));
  ok("分类都在白名单内", badCat.length === 0, badCat.slice(0, 5).join(","));
  ok("坐标都落在中国范围内", badBbox.length === 0, badBbox.slice(0, 5).join(","));
  ok("同城没有重名景点", dupName.length === 0, dupName.slice(0, 5).join(","));
  ok("景点没有离城市中心 >6° 的（坐标手滑）", tooFar.length === 0, tooFar.slice(0, 5).join(","));
  ok("存在「美食」分类（首页/功能页承诺了美食探店）", (catCount["美食"] || 0) > 0, catCount["美食"]);
  ok("「美食」覆盖 >= 40 座城市", foodCities.length >= 40, foodCities.length);
  ok("所有分类都至少有一个景点", CATS.every((c) => catCount[c] > 0),
     CATS.filter((c) => !catCount[c]).join(","));

  console.log(`\n通过 ${pass} / ${pass + fail}`);
  process.exit(fail ? 1 : 0);
}, 800);
