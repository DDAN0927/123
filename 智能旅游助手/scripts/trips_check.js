/**
 * 行程工作台前端校验（jsdom）
 *
 * 覆盖的都不是「页面能不能打开」，而是几个容易悄悄坏掉的地方：
 *   1) 城市候选来自 geo-data.js 的 355 城（不是写死的 6 城）；
 *   2) 倒计时 / 进度条与后端返回的数字一致（算错就是给用户看假进度）；
 *   3) 勾选一条后进度真的变了（最常用操作，坏了等于整个功能失效）；
 *   4) 行前清单按「分组」渲染（装备清单的分组信息存在 slot 字段里，丢了就成一坨）；
 *   5) 后端失败时给可读提示，而不是空白；
 *   6) 预算面板的「已花/剩余」与明细一致（算错就是给用户看假账）；
 *   7) 模板 / 分享 / AI 改行程三个新入口点下去真的打到了对应接口。
 *
 * 用法（需 jsdom）：
 *   NODE_PATH=<managed-node-workspace>/node_modules node scripts/trips_check.js
 */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const root = path.join(__dirname, "..", "frontend", "static");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");

const html = read("trips.html");
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

// 内存态行程：stub 里维护一份，勾选/添加/删除都要真的改它，
// 否则「勾完进度变了」这类断言等于在测一个假对象。
const stub = `
window.matchMedia = function () { return { matches: false, addEventListener: function(){}, removeEventListener: function(){} }; };
window.IntersectionObserver = function () { this.observe=function(){}; this.unobserve=function(){}; this.disconnect=function(){}; };
window.requestAnimationFrame = function (cb) { return setTimeout(function(){ cb(0); }, 0); };
window.cancelAnimationFrame = function (id) { clearTimeout(id); };
window.scrollTo = function () {};
window.confirm = function () { return true; };
localStorage.setItem("tc_token", "test-token");
localStorage.setItem("tc_user", JSON.stringify({ username: "tester", role: "user" }));

var TRIP = {
  id: "t1", title: "北京 3 天", city: "北京", start_date: "2099-11-01", days: 3,
  budget: 3000, note: "", countdown: 12, phase: "upcoming", share_token: "",
  prep: [
    { id: 11, day_index: 0, slot: "证件与票据", kind: "packing", title: "身份证", note: "", done: false },
    { id: 12, day_index: 0, slot: "证件与票据", kind: "packing", title: "学生证", note: "", done: true },
    { id: 13, day_index: 0, slot: "行前预订", kind: "packing", title: "订故宫门票", note: "", done: false }
  ],
  itinerary: [
    { day: 1, items: [
      { id: 21, day_index: 1, slot: "上午", kind: "spot", title: "故宫", note: "提前 7 天预约", done: false },
      { id: 22, day_index: 1, slot: "晚上", kind: "food", title: "簋街夜宵", note: "", done: false }
    ]}
  ]
};

// 记账：详情接口只带汇总，明细走 /expenses。stub 里两份都真算，
// 否则「已花 ¥60」这类断言只是在核对一个写死的数字。
var EXPENSES = [
  { id: 31, category: "门票", title: "故宫门票", amount: 60, day_index: 1 }
];
function budgetView() {
  var spent = EXPENSES.reduce(function (s, x) { return s + Number(x.amount); }, 0);
  var byCat = {};
  EXPENSES.forEach(function (x) { byCat[x.category] = (byCat[x.category] || 0) + Number(x.amount); });
  var budget = Number(TRIP.budget || 0);
  return {
    budget: budget,
    spent: spent,
    remaining: budget - spent,
    percent: budget > 0 ? Math.round(spent * 100 / budget) : 0,
    by_category: byCat
  };
}

function progress() {
  var all = TRIP.prep.concat.apply(TRIP.prep, TRIP.itinerary.map(function (d) { return d.items; }));
  var done = all.filter(function (i) { return i.done; }).length;
  return { done: done, total: all.length, percent: all.length ? Math.round(done * 100 / all.length) : 0 };
}
function withProgress() {
  TRIP.progress = progress();
  TRIP.expenses = budgetView();
  return JSON.parse(JSON.stringify(TRIP));
}
withProgress();

window.__calls = [];
window.fetch = function (url, opts) {
  var u = String(url), method = ((opts && opts.method) || "GET").toUpperCase();
  window.__calls.push(method + " " + u);
  var reply = function (payload, okFlag, status) {
    return Promise.resolve({
      ok: okFlag === undefined ? true : okFlag,
      status: status || 200,
      body: null,
      text: function () { return Promise.resolve(JSON.stringify(payload)); },
      json: function () { return Promise.resolve(payload); },
    });
  };
  // 高德 Key 走 /api/config 下发：不给的话地图分支会直接渲染「未配置」提示，
  // 测「地图弹窗里到底有没有地图」就永远测不到。
  if (u.indexOf("/api/config") >= 0) {
    return reply({ amap_key: "test-amap-key", amap_security_js_code: "test-js-code" });
  }
  if (u.indexOf("/api/trips") < 0 && u.indexOf("/api/templates") < 0) return reply({});

  if (method === "GET" && /\\/api\\/trips$/.test(u)) {
    return reply({ trips: [withProgress()] });
  }
  if (method === "POST" && /\\/api\\/trips$/.test(u)) {
    var body = JSON.parse((opts && opts.body) || "{}");
    TRIP.city = body.city || TRIP.city;
    TRIP.days = body.days || 3;
    TRIP.budget = body.budget || 0;
    TRIP.title = TRIP.city + " " + TRIP.days + " 天";
    return reply({ trip: withProgress() });
  }
  if (method === "POST" && /\\/packing$/.test(u)) {
    TRIP.prep.push({ id: 14, day_index: 0, slot: "衣物与鞋", kind: "packing", title: "羽绒服", note: "", done: false });
    return reply({ groups: [{ group: "衣物与鞋", items: ["羽绒服"] }], source: "forecast", advice: [] });
  }
  if (method === "GET" && /\\/weather$/.test(u)) {
    return reply({
      supported: true,
      rows: [{ date: "2099-11-01", tmin: 2, tmax: 11, cond: "晴", precip: 10, wind: 12 }],
      advice: ["气温 2~11℃，常规春秋装即可"]
    });
  }
  if (method === "PATCH" && /\\/items\\/\\d+$/.test(u)) {
    var id = parseInt(u.split("/").pop(), 10);
    var payload = JSON.parse((opts && opts.body) || "{}");
    var all = TRIP.prep.concat.apply(TRIP.prep, TRIP.itinerary.map(function (d) { return d.items; }));
    all.forEach(function (i) { if (i.id === id && "done" in payload) i.done = !!payload.done; });
    return reply({ trip: withProgress() });
  }
  if (method === "POST" && /\\/items$/.test(u)) {
    var nb = JSON.parse((opts && opts.body) || "{}");
    var day = nb.day_index || 0;
    var item = { id: 90 + window.__calls.length, day_index: day, slot: "", kind: "spot", title: nb.title, note: "", done: false };
    if (day === 0) TRIP.prep.push(item);
    else {
      var bucket = TRIP.itinerary.filter(function (d) { return d.day === day; })[0];
      if (bucket) bucket.items.push(item);
      else TRIP.itinerary.push({ day: day, items: [item] });
    }
    return reply({ item: item });
  }
  if (method === "DELETE" && /\\/items\\/\\d+$/.test(u)) {
    var did = parseInt(u.split("/").pop(), 10);
    TRIP.prep = TRIP.prep.filter(function (i) { return i.id !== did; });
    TRIP.itinerary.forEach(function (d) { d.items = d.items.filter(function (i) { return i.id !== did; }); });
    return reply({ ok: true });
  }
  if (method === "GET" && /\\/api\\/templates$/.test(u)) {
    return reply({ templates: [
      { key: "classic", name: "经典打卡", description: "第一次来，把地标都走一遍" },
      { key: "food", name: "美食优先", description: "以吃为主线，景点围着餐馆排" }
    ] });
  }
  if (method === "POST" && /\\/templates\\/[a-z]+$/.test(u)) {
    return reply({ items: 8, trip: withProgress() });
  }
  if (method === "GET" && /\\/expenses$/.test(u)) {
    return reply({ expenses: EXPENSES.slice() });
  }
  if (method === "POST" && /\\/expenses$/.test(u)) {
    var eb = JSON.parse((opts && opts.body) || "{}");
    EXPENSES.push({
      id: 40 + EXPENSES.length,
      category: eb.category || "其他",
      title: eb.title || "",
      amount: eb.amount || 0,
      day_index: eb.day_index || 0
    });
    return reply({ trip: withProgress() });
  }
  if (method === "DELETE" && /\\/expenses\\/\\d+$/.test(u)) {
    var xid = parseInt(u.split("/").pop(), 10);
    EXPENSES = EXPENSES.filter(function (x) { return x.id !== xid; });
    return reply({ trip: withProgress() });
  }
  if (method === "POST" && /\\/share$/.test(u)) {
    TRIP.share_token = "shr123";
    return reply({ url: "/s/shr123", share_token: "shr123", trip: withProgress() });
  }
  if (method === "POST" && /\\/revise$/.test(u)) {
    return reply({ items: 2, trip: withProgress() });
  }
  if (method === "GET" && /\\/api\\/trips\\/t1$/.test(u)) return reply({ trip: withProgress() });
  return reply({ trip: withProgress() });
};
`;

const doc = subScript(
  subScript(
    subScript(html, "assets/js/geo-data.js", inline(geo)),
    "assets/js/app.js",
    inline(appjs)
  ),
  "assets/js/main.js",
  inline(mainjs)
).replace("<body>", () => `<body><script>${stub}</script>`);

const dom = new JSDOM(doc, {
  url: "http://localhost/trips.html",
  runScripts: "dangerously",
  pretendToBeVisual: true,
});
const { window } = dom;
const document = window.document;

const results = [];
const check = (name, ok, extra) => {
  results.push([name, !!ok]);
  console.log(`${ok ? "✅" : "❌"} ${name}${extra !== undefined && !ok ? " — " + extra : ""}`);
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const q = (sel) => document.querySelector(sel);
const qa = (sel) => Array.from(document.querySelectorAll(sel));

(async () => {
  await wait(400);

  check("页面主容器已渲染", !!q("#trips-app .trip-new"));
  check("新建表单含目的地/日期/天数/预算", !!q("#trip-city") && !!q("#trip-date") && !!q("#trip-days") && !!q("#trip-budget"));
  check("城市候选来自 geo-data（355 城）", qa("#trip-city-list option").length === 355,
    qa("#trip-city-list option").length);

  const cards = qa(".trip-card");
  check("行程列表渲染出卡片", cards.length === 1, cards.length);
  check("卡片显示倒计时", (cards[0] || {}).textContent.includes("还有 12 天出发"),
    (cards[0] || {}).textContent);
  check("卡片显示完成进度", (cards[0] || {}).textContent.includes("已完成 1/5"),
    (cards[0] || {}).textContent);
  const barW = (q(".trip-card .trip-bar i") || {}).style?.width;
  check("进度条宽度与百分比一致（1/5=20%）", barW === "20%", barW);

  cards[0].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(200);

  check("点击卡片进入详情", !!q(".trip-hero"));
  // 用标题文本判定而不是数 .trip-sec-head 的个数：详情页的分区会随功能增加
  // （预算面板也带一个 sec-head），数数量会在每次加功能时误报。
  const secHeads = qa(".trip-sec-head h3").map((n) => n.textContent.trim());
  check("详情显示行前清单与每日行程",
    secHeads.includes("行前清单") && secHeads.includes("每日行程"), secHeads.join(","));
  const acts = qa(".trip-actions [data-act]").map((b) => b.dataset.act);
  check("动作栏含模板/分享/导出入口",
    ["template", "share", "export"].every((a) => acts.includes(a)), acts.join(","));
  check("行前清单按分组渲染（证件与票据/行前预订）",
    qa(".trip-group-name").map((n) => n.textContent.trim()).join(",") === "证件与票据,行前预订",
    qa(".trip-group-name").map((n) => n.textContent.trim()));
  check("已完成条目带删除线样式", qa(".trip-item.done").length === 1, qa(".trip-item.done").length);
  check("每日行程按天分块", qa(".trip-day").length === 1 && (q(".trip-day-name") || {}).textContent.includes("第 1 天"));
  check("行程条目显示备注", (q(".trip-day") || {}).textContent.includes("提前 7 天预约"));

  // 勾选一条未完成的 → 进度应变
  const box = qa(".trip-check").find((b) => !b.checked);
  box.checked = true;
  box.dispatchEvent(new window.Event("change", { bubbles: true }));
  await wait(250);
  check("勾选后进度更新为 2/5", (q(".trip-foot") || {}).textContent.includes("2/5"),
    (q(".trip-foot") || {}).textContent);
  check("勾选请求打到 PATCH items", window.__calls.some((c) => c.startsWith("PATCH") && c.includes("/items/")));

  // 生成装备清单
  const packBtn = qa(".trip-actions [data-act]").find((b) => b.dataset.act === "packing");
  packBtn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  check("生成装备清单后新增分组", qa(".trip-group-name").some((n) => n.textContent.includes("衣物与鞋")),
    qa(".trip-group-name").map((n) => n.textContent.trim()));

  // 天气
  const wxBtn = qa(".trip-actions [data-act]").find((b) => b.dataset.act === "weather");
  wxBtn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  check("天气面板渲染温度与建议",
    (q("#trip-weather") || {}).textContent.includes("2~11℃") &&
    (q("#trip-weather") || {}).textContent.includes("常规春秋装"),
    (q("#trip-weather") || {}).textContent);

  // 添加一条
  const input = q('.trip-add-input[data-day="0"]');
  input.value = "充电宝";
  q('.trip-add-btn[data-day="0"]').dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  check("手动添加条目后出现在清单里", q("#trips-app").textContent.includes("充电宝"));

  // ---- 预算面板：汇总由详情接口给，明细走 /expenses
  check("预算面板显示已花与剩余",
    (q(".trip-budget") || {}).textContent.includes("已花 ¥60") &&
    (q(".trip-budget") || {}).textContent.includes("剩余 ¥2940"),
    (q(".trip-budget") || {}).textContent);
  check("预算进度条按 60/3000=2% 渲染",
    (q(".budget-bar i") || {}).style?.width === "2%", (q(".budget-bar i") || {}).style?.width);
  check("花费明细列出每一笔", (q("#budget-list") || {}).textContent.includes("故宫门票"),
    (q("#budget-list") || {}).textContent);
  check("花费明细标注分类与所属天",
    (q(".budget-item") || {}).textContent.includes("门票") &&
    (q(".budget-item") || {}).textContent.includes("第1天"),
    (q(".budget-item") || {}).textContent);

  q("#budget-title").value = "颐和园门票";
  q("#budget-amount").value = "30";
  q("#budget-add").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  check("记一笔后总额更新为 90",
    (q(".trip-budget") || {}).textContent.includes("已花 ¥90"), (q(".trip-budget") || {}).textContent);
  check("记账请求打到 POST expenses",
    window.__calls.includes("POST /api/trips/t1/expenses"));

  // ---- 模板库
  qa(".trip-actions [data-act]").find((b) => b.dataset.act === "template")
    .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  check("模板行展开并列出模板",
    qa(".trip-tpl").length === 2 && !q("#trip-tpl-row").hidden, qa(".trip-tpl").length);
  q(".trip-tpl").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  check("套用模板请求打到 POST templates/{key}",
    window.__calls.includes("POST /api/trips/t1/templates/classic"));

  // ---- 分享
  qa(".trip-actions [data-act]").find((b) => b.dataset.act === "share")
    .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  check("分享请求打到 POST share", window.__calls.includes("POST /api/trips/t1/share"));

  // ---- AI 改行程
  q("#trip-revise-input").value = "第三天想换室内，怕下雨";
  q("#trip-revise-btn").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  check("AI 改行程请求打到 POST revise",
    window.__calls.includes("POST /api/trips/t1/revise"));
  // 前面勾过一条，加上初始的「学生证」共 2 条已完成；改行程后必须还是 2 条
  check("改完重新渲染详情（勾选状态仍在）", !!q(".trip-hero") && qa(".trip-item.done").length === 2,
    qa(".trip-item.done").length);

  // ---- 行程地图：把每日条目对到景点库坐标
  // 测的不是「弹窗能不能开」，而是三件容易悄悄坏的事：
  //   ① 条目名跟景点库不会字字相同（「故宫」vs「故宫博物院」）也要能对上；
  //   ② 对不上的条目必须明确列出来，不能静默丢掉（用户会以为地图漏了地点）；
  //   ③ 计数要跟实际一致（写着 3/3 却少画一个点，比不画更糟）。
  const mapBtn0 = qa(".trip-actions [data-act]").find((b) => b.dataset.act === "map");
  check("动作栏含行程地图入口", !!mapBtn0 && mapBtn0.textContent.includes("地图"));

  // 塞一条对不上景点库的（「自由活动」），然后重开详情让新数据进渲染
  window.TRIP.itinerary[0].items.push({
    id: 99, day_index: 1, slot: "下午", kind: "doc", title: "自由活动", note: "", done: false,
  });
  q("#trip-back").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(200);
  q(".trip-card").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(250);
  qa(".trip-actions [data-act]").find((b) => b.dataset.act === "map")
    .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await wait(400);

  const mm = q("#trip-map-modal");
  check("点开地图弹出弹窗", !!mm);
  check("包含匹配能对上景点库（故宫→故宫博物院，2/3）",
    !!mm && mm.textContent.includes("已上图 2/3"), mm && mm.textContent.replace(/\s+/g, " ").slice(0, 90));
  check("按天生成图例", !!mm && mm.textContent.includes("第 1 天"),
    mm && mm.textContent.replace(/\s+/g, " ").slice(0, 120));
  check("对不上的条目单独列出而不是静默丢弃",
    !!mm && mm.textContent.includes("未上图") && mm.textContent.includes("自由活动"),
    mm && mm.textContent.replace(/\s+/g, " ").slice(0, 180));
  check("地图用 iframe 承载（AMap 脚本不污染主文档）",
    !!mm && !!mm.querySelector("#trip-map-canvas iframe"));
  const srcdoc = (mm && mm.querySelector("#trip-map-canvas iframe") || {}).getAttribute
    ? mm.querySelector("#trip-map-canvas iframe").getAttribute("srcdoc") : "";
  check("iframe 里带上了下发的 Key 与按天分色的折线",
    srcdoc.includes("test-amap-key") && srcdoc.includes("Polyline"),
    srcdoc.slice(0, 60));

  // ---- 空状态：示例行程入口
  // 新用户（以及答辩时自己点开链接的老师）第一次进来是空白页。这里钉住三件事：
  // 有引导、有入口、点了真的打到 POST /api/trips/sample 且带城市。
  // 用第二个 DOM 而不是在同一个实例里改数据：renderTripList 是内部函数，
  // 从外面没法让它重新拉一次空列表，硬造反而测不到真实路径。
  const emptyDoc = doc.replace(
    "return reply({ trips: [withProgress()] });",
    "return reply({ trips: [] });"
  );
  const dom2 = new JSDOM(emptyDoc, {
    url: "http://localhost/trips.html",
    runScripts: "dangerously",
    pretendToBeVisual: true,
  });
  await wait(400);
  const d2 = dom2.window.document;
  const emptyBox = d2.querySelector(".app-empty");
  check("空行程时给出引导而不是一片空白", !!emptyBox && emptyBox.textContent.includes("还没有行程"),
    emptyBox && emptyBox.textContent.trim().slice(0, 40));
  const sampleBtn = d2.querySelector("#trip-sample");
  check("空状态提供示例行程入口", !!sampleBtn && sampleBtn.textContent.includes("示例"),
    sampleBtn && sampleBtn.textContent);
  if (sampleBtn) {
    sampleBtn.dispatchEvent(new dom2.window.MouseEvent("click", { bubbles: true }));
    await wait(300);
    check("点击后请求 POST /api/trips/sample",
      dom2.window.__calls.includes("POST /api/trips/sample"),
      dom2.window.__calls.slice(-3).join(" | "));
  }
  dom2.window.close();

  const failed = results.filter((r) => !r[1]);
  console.log(`\n通过 ${results.length - failed.length} / ${results.length}`);
  if (failed.length) {
    console.log("失败项：" + failed.map((r) => r[0]).join("、"));
  }
  // jsdom 里 main.js 的光标动画会一直挂着定时器，不显式退出就永远不结束
  dom.window.close();
  process.exit(failed.length ? 1 : 0);
})().catch((e) => {
  console.error("运行失败:", e);
  process.exit(1);
});
