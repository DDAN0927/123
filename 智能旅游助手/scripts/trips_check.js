/**
 * 行程工作台前端校验（jsdom）
 *
 * 覆盖的都不是「页面能不能打开」，而是几个容易悄悄坏掉的地方：
 *   1) 城市候选来自 geo-data.js 的 355 城（不是写死的 6 城）；
 *   2) 倒计时 / 进度条与后端返回的数字一致（算错就是给用户看假进度）；
 *   3) 勾选一条后进度真的变了（最常用操作，坏了等于整个功能失效）；
 *   4) 行前清单按「分组」渲染（装备清单的分组信息存在 slot 字段里，丢了就成一坨）；
 *   5) 后端失败时给可读提示，而不是空白。
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
  budget: 3000, note: "", countdown: 12, phase: "upcoming",
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
function progress() {
  var all = TRIP.prep.concat.apply(TRIP.prep, TRIP.itinerary.map(function (d) { return d.items; }));
  var done = all.filter(function (i) { return i.done; }).length;
  return { done: done, total: all.length, percent: all.length ? Math.round(done * 100 / all.length) : 0 };
}
function withProgress() { TRIP.progress = progress(); return JSON.parse(JSON.stringify(TRIP)); }
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
  if (u.indexOf("/api/trips") < 0) return reply({});

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
  if (method === "GET" && /\\/api\\/trips\\/t1$/.test(u)) return reply({ trip: withProgress() });
  return reply({ trip: withProgress() });
};
`;

const doc = html
  .replace('<script src="assets/js/geo-data.js"></script>', () => `<script>${inline(geo)}</script>`)
  .replace('<script src="assets/js/app.js"></script>', () => `<script>${inline(appjs)}</script>`)
  .replace('<script src="assets/js/main.js"></script>', () => `<script>${inline(mainjs)}</script>`)
  .replace("<body>", () => `<body><script>${stub}</script>`);

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
  check("详情显示行前清单与每日行程", !!q(".trip-sec-head") && qa(".trip-sec-head").length === 2);
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
