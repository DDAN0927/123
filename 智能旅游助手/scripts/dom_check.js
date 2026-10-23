/**
 * 前端 DOM 集成校验（jsdom）：
 * 按真实加载顺序（geo-data → app.js → main.js）在 DOMContentLoaded 上跑一遍，覆盖：
 *   1) 移动端汉堡菜单此前在应用页完全失效（main.js 早于 app.js 注入导航）——现应可用；
 *   2) 应用页导航、聊天页（历史会话 / 协作轨迹容器 / 输入区）应正确渲染；
 *   3) 点赞/点踩上报的 message_index 必须绑定到「那条消息」，而不是点击时的当前计数
 *      —— 否则给第 1 条回答点赞会记到第 3 条上。
 *
 * 用法（需 jsdom）：
 *   NODE_PATH=<managed-node-workspace>/node_modules node scripts/dom_check.js
 */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const root = path.join(__dirname, "..", "frontend", "static");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");

const html = read("chat.html");
const geo = read("assets/js/geo-data.js");
const appjs = read("assets/js/app.js");
const mainjs = read("assets/js/main.js");

// 内联注入时需转义源码里的 </script>，否则会被 HTML 解析器提前截断
const inline = (s) => s.replace(/<\/script>/gi, "<\\/script>");

// 一段带 3 条助手消息的历史会话，用来验证反馈索引
const HISTORY = {
  session_id: "s1",
  messages: [
    { role: "user", content: "帮我规划北京 3 天", ts: 1 },
    { role: "assistant", content: "### 第 1 天\n故宫、天安门", ts: 2 },
    { role: "user", content: "那上海呢", ts: 3 },
    { role: "assistant", content: "### 第 2 天\n外滩、豫园", ts: 4 },
    { role: "user", content: "还有成都", ts: 5 },
    { role: "assistant", content: "### 第 3 天\n宽窄巷子、武侯祠", ts: 6 },
  ],
};

// 把外链脚本替换为内联脚本，保证按真实顺序执行；并在最前面注入环境桩与登录态
const stub = `
window.matchMedia = function () { return { matches: false, addEventListener: function(){}, removeEventListener: function(){} }; };
window.IntersectionObserver = function () { this.observe=function(){}; this.unobserve=function(){}; this.disconnect=function(){}; };
window.requestAnimationFrame = function (cb) { return setTimeout(function(){ cb(0); }, 0); };
window.cancelAnimationFrame = function (id) { clearTimeout(id); };
window.scrollTo = function () {};
window.confirm = function () { return true; };
localStorage.setItem("tc_token", "test-token");
localStorage.setItem("tc_user", JSON.stringify({ username: "tester", role: "admin" }));
localStorage.setItem("tc_sessions_tester", JSON.stringify([
  { id: "s1", title: "北京三日", message_count: 6, updated_at: 1 }
]));
window.__feedback = [];
window.fetch = function (url, opts) {
  var u = String(url), method = (opts && opts.method) || "GET", body;
  var reply = function (payload, okFlag, status) {
    return Promise.resolve({
      ok: okFlag === undefined ? true : okFlag,
      status: status || 200,
      body: null,
      text: function () { return Promise.resolve(JSON.stringify(payload)); },
      json: function () { return Promise.resolve(payload); },
    });
  };
  if (u.indexOf("/api/agents") >= 0) {
    body = { supervisor: {}, experts: [
      { name: "planner", title: "行程规划师", icon: "🗓️", description: "", tools: [] },
      { name: "food", title: "美食顾问", icon: "🍜", description: "", tools: [] }
    ] };
  } else if (u.indexOf("/api/chat/history/") >= 0) {
    body = ${JSON.stringify(HISTORY)};
  } else if (u.indexOf("/api/chat/feedback") >= 0) {
    window.__feedback.push(JSON.parse((opts && opts.body) || "{}"));
    body = { ok: true };
  } else if (u.indexOf("/api/chat/sessions") >= 0) {
    body = [];
  } else if (u.indexOf("/api/knowledge/coverage") >= 0) {
    body = {
      cities: ["上海", "北京", "成都", "杭州", "西安", "重庆"],
      count: 6, map_cities: 355, map_spots: 1558,
    };
  } else if (u.indexOf("/api/auth/register") >= 0) {
    // 模拟 FastAPI 的 422：detail 是「数组」，前端必须压成人话
    var p = JSON.parse((opts && opts.body) || "{}");
    if (/[<>"']/.test(p.username || "")) {
      return reply({ detail: [{
        type: "string_pattern_mismatch", loc: ["body", "username"],
        msg: "String should match pattern '^[\\\\w\\\\u4e00-\\\\u9fff.@-]+$'", input: p.username,
      }] }, false, 422);
    }
    body = { token: "t", username: p.username, role: "user" };
  } else { body = {}; }
  return reply(body);
};
`;

// 注意：这里必须用「替换函数」而不是替换字符串。
// String.replace 会把替换值里的 $' / $& / $1 当特殊记号解释 —— 桩代码里一旦出现 $'
// （例如正则字面量后面的引号），整段脚本就会被替换成 HTML 的剩余部分，直接语法崩掉。
const doc = html
  .replace('<script src="assets/js/geo-data.js"></script>', () => `<script>${inline(geo)}</script>`)
  .replace('<script src="assets/js/app.js"></script>', () => `<script>${inline(appjs)}</script>`)
  .replace('<script src="assets/js/main.js"></script>', () => `<script>${inline(mainjs)}</script>`)
  .replace("<body>", () => `<body><script>${stub}</script>`);

const dom = new JSDOM(doc, {
  url: "http://localhost/chat.html",
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

(async () => {
  await wait(600);

  const q = (s) => document.querySelector(s);
  const qa = (s) => document.querySelectorAll(s);

  // ---- 导航 ----
  const navLinks = q(".nav-links");
  check("应用页导航已注入 AI旅行咨询", navLinks && navLinks.textContent.includes("AI旅行咨询"));
  check("应用页导航含管理员入口", navLinks && navLinks.innerHTML.includes("admin.html"));

  // ---- 移动端菜单（本次修复重点）----
  const burger = q(".nav-burger");
  check("汉堡按钮已渲染", !!burger);
  const menu = q(".mobile-menu");
  check("移动端菜单容器已创建", !!menu);
  const menuLinks = qa(".mobile-menu .mobile-menu-inner a");
  check("移动端菜单已填充导航项(>=7)", menuLinks.length >= 7, `实际 ${menuLinks.length} 项`);

  if (burger) {
    burger.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    check("点击汉堡按钮可打开菜单(body.menu-open)", document.body.classList.contains("menu-open"));
    burger.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    check("再次点击可关闭菜单", !document.body.classList.contains("menu-open"));
  }

  // ---- 聊天页 ----
  check("聊天页主容器已渲染", !!q("#chat-app .chat-wrap"));
  check("会话历史区块存在", !!q("#cs-sessions"));
  check("消息区存在", !!q("#chat-msgs"));
  check("输入框与发送按钮存在", !!q("#chat-in") && !!q("#chat-send"));
  // 地图 355 城 ≠ 攻略库 6 城，用户提问前就该看到这个边界
  check(
    "输入框上方展示知识库覆盖范围",
    (q("#chat-kb-hint") || {}).textContent?.includes("6 城"),
    (q("#chat-kb-hint") || {}).textContent
  );
  check("新建对话按钮存在", !!q("#chat-new"));
  check("顾问团列表已渲染", qa(".cs-list .cs-agent").length === 2, qa(".cs-list .cs-agent").length);
  check("首屏欢迎语已展示", (q("#chat-msgs") || {}).textContent?.includes("tester"));
  check("未登录用户不再显示登录门", !q(".app-gate"));

  // ---- 历史会话列表 ----
  const sess = q('.cs-session[data-id="s1"]');
  check("本地历史会话已渲染", !!sess);
  check("历史会话标题正确", sess && sess.textContent.includes("北京三日"));

  // ---- 反馈索引回归：打开历史会话，给第 1 条回答点👍 ----
  if (sess) {
    sess.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    await wait(150);

    const bots = qa("#chat-msgs .msg.bot");
    check("历史会话已还原 3 条助手消息", bots.length === 3, `实际 ${bots.length}`);

    const likeBtn = bots[0] && bots[0].querySelector('[data-act="like"]');
    check("第 1 条回答有反馈按钮", !!likeBtn);
    if (likeBtn) {
      likeBtn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
      await wait(80);
      const sent = window.__feedback[0];
      check("反馈已上报", !!sent);
      // 关键：第 1 条回答的索引必须是 1，而不是「点击时的当前计数」3
      check("第 1 条回答上报 message_index=1（不是 3）",
        sent && sent.message_index === 1, sent && `实际 ${sent.message_index}`);
      check("反馈 rating=like", sent && sent.rating === "like", sent && sent.rating);
      check("反馈带上 session_id", sent && sent.session_id === "s1", sent && sent.session_id);
    }

    // 再给第 3 条点赞，索引应为 3
    const like3 = bots[2] && bots[2].querySelector('[data-act="like"]');
    if (like3) {
      like3.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
      await wait(80);
      const sent3 = window.__feedback[1];
      check("第 3 条回答上报 message_index=3",
        sent3 && sent3.message_index === 3, sent3 && `实际 ${sent3.message_index}`);
    }
  }

  // ---- 422 校验错误必须显示成人话，而不是 "[object Object]" ----
  // FastAPI 的 detail 在 422 时是数组，之前直接 textContent 赋值会渲染成 [object Object]
  const modal = q("#login-modal");
  check("登录弹窗已注入", !!modal);
  if (modal) {
    modal.querySelector("#mod-toggle").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    check("点「去注册」切到注册模式",
      modal.querySelector("#mod-pwd2").style.display === "block");
    modal.querySelector("#mod-user").value = "<script>x</script>";
    modal.querySelector("#mod-pwd").value = "pw123456";
    modal.querySelector("#mod-pwd2").value = "pw123456";
    modal.querySelector("#mod-submit").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    await wait(120);
    const errText = modal.querySelector("#mod-err").textContent || "";
    check("422 错误提示是人话（不是 [object Object]）",
      errText.indexOf("[object Object]") < 0 && errText.indexOf("pattern") >= 0, errText);
  }

  // ---- 页面其他组件未报错 ----
  check("自定义光标脚本已执行", qa(".cursor-ring").length === 1);

  // ---- 鉴权头：必须用 X-Auth-Token ----
  // 魔搭创空间（*.ms.show）的边缘 WAF 会拦掉**任何**带 Authorization: Bearer 的请求
  // （与 token 内容无关，应用层根本收不到）。前端一旦改回标准头，线上所有需要登录的
  // 功能都会 403，所以在这里钉死。两处都要覆盖：普通 fetch 与 SSE 流式请求。
  const tokenHeaderCount = (appjs.match(/X-Auth-Token/g) || []).length;
  check("app.js 用 X-Auth-Token 携带鉴权（普通请求 + SSE 流式各一处）",
    tokenHeaderCount >= 2, `${tokenHeaderCount} 处`);
  check("app.js 不再用 Authorization 请求头（会被平台 WAF 拦截）",
    !/["']Authorization["']\s*:/.test(appjs));

  // ============================================================
  // 运营管理页：标签切换 + 内容库渲染（独立文档，避免污染上面的断言）
  // ============================================================
  const adminHtml = read("admin.html");
  const NOTES = Array.from({ length: 20 }, (_, i) => ({
    id: "n" + i,
    source: i === 0 ? "xiaohongshu" : (i === 1 ? "douyin" : "manual"),
    title: "攻略标题 " + i,
    content: "正文内容 " + i + " —— 用于验证列表渲染与展开。",
    city: i < 10 ? "北京" : "重庆",
    tags: "测试",
    url: "",
    author: "作者" + i,
    imported_by: "admin",
    created_at: 1760000000 + i,
  }));
  // 故意让「总数(45) > 本页条数(20)」，以验证前端确实是从 X-Total-Count 读总数，
  // 而不是拿数组长度当总数（那样分页器会永远只有 1 页）。
  const adminStub = `
window.matchMedia = function () { return { matches: false, addEventListener: function(){}, removeEventListener: function(){} }; };
window.IntersectionObserver = function () { this.observe=function(){}; this.unobserve=function(){}; this.disconnect=function(){}; };
window.requestAnimationFrame = function (cb) { return setTimeout(function(){ cb(0); }, 0); };
window.cancelAnimationFrame = function (id) { clearTimeout(id); };
window.scrollTo = function () {};
window.confirm = function () { return true; };
localStorage.setItem("tc_token", "test-token");
localStorage.setItem("tc_user", JSON.stringify({ username: "admin", role: "admin" }));
window.fetch = function (url, opts) {
  var u = String(url);
  var mk = function (payload, total) {
    return Promise.resolve({
      ok: true, status: 200,
      headers: { get: function (k) {
        return String(k).toLowerCase() === "x-total-count" ? String(total) : null;
      } },
      text: function () { return Promise.resolve(JSON.stringify(payload)); },
      json: function () { return Promise.resolve(payload); },
    });
  };
  if (u.indexOf("/api/notes/stats") >= 0) {
    return mk({ total: 45, by_source: { "小红书": 1, "抖音": 1, "手工录入": 18 },
                city_count: 2, cities: [{ city: "北京", count: 10 }, { city: "重庆", count: 10 }] });
  }
  if (u.indexOf("/api/notes") >= 0) {
    // 让关键词 zzz 查不到东西，用来验证「筛选无结果」的空态文案
    if (u.indexOf("q=zzz") >= 0) return mk([], 0);
    return mk(${JSON.stringify(NOTES)}, 45);
  }
  if (u.indexOf("/api/admin/stats") >= 0) return mk({ total_sessions: 3, total_messages: 9, likes: 1, dislikes: 0 });
  if (u.indexOf("/api/admin/sessions") >= 0) return mk([]);
  if (u.indexOf("/api/admin/users") >= 0) return mk({ users: [] });
  return mk({});
};
`;
  const adminDoc = adminHtml
    .replace('<script src="assets/js/geo-data.js"></script>', () => `<script>${inline(geo)}</script>`)
    .replace('<script src="assets/js/app.js"></script>', () => `<script>${inline(appjs)}</script>`)
    .replace('<script src="assets/js/main.js"></script>', () => `<script>${inline(mainjs)}</script>`)
    .replace("<body>", () => `<body><script>${adminStub}</script>`);

  const adminDom = new JSDOM(adminDoc, {
    url: "http://localhost/admin.html",
    runScripts: "dangerously",
    pretendToBeVisual: true,
  });
  const adminWindow = adminDom.window;
  const adminDocument = adminWindow.document;
  const aq = (s) => adminDocument.querySelector(s);
  const aqa = (s) => adminDocument.querySelectorAll(s);

  await wait(600);

  const tabs = aqa(".admin-tab");
  check("运营管理页渲染出两个标签（运营看板 / 内容库）",
    tabs.length === 2 && tabs[1].textContent.includes("内容库"), `实际 ${tabs.length} 个`);
  check("默认停在运营看板，内容库面板隐藏",
    !aq("#admin-panel-overview").hidden && aq("#admin-panel-notes").hidden);

  tabs[1].dispatchEvent(new adminWindow.MouseEvent("click", { bubbles: true }));
  await wait(400);

  check("点「内容库」后切换面板（看板隐藏、内容库显示）",
    aq("#admin-panel-overview").hidden && !aq("#admin-panel-notes").hidden);
  check("内容库概览卡片渲染（内容总量 45）",
    (aq("#admin-panel-notes").textContent || "").includes("45"));
  check("来源分布小标签渲染",
    aqa(".note-chip").length >= 3, `实际 ${aqa(".note-chip").length} 个`);
  check("列表渲染出本页 20 条",
    aqa(".note-row").length === 20, `实际 ${aqa(".note-row").length} 条`);
  check("来源徽章区分小红书 / 抖音 / 手工录入",
    !!aq(".note-badge-xiaohongshu") && !!aq(".note-badge-douyin") && !!aq(".note-badge-manual"));
  check("城市下拉带条数（北京（10））",
    (aq("#note-flt-city").textContent || "").includes("北京（10）"));
  check("分页总数取自 X-Total-Count（45 条 → 3 页）",
    (aq(".note-pager-info") && aq(".note-pager-info").textContent || "").includes("共 45 条"),
    aq(".note-pager-info") && aq(".note-pager-info").textContent);
  check("导入表单与导出按钮都在",
    !!aq("#note-f-content") && !!aq("#note-save") && !!aq("#note-export"));

  // 点「查看」应展开全文，且不破坏其他行
  const firstView = aq(".note-view");
  const firstFull = aq(".note-row .note-full");
  firstView.dispatchEvent(new adminWindow.MouseEvent("click", { bubbles: true }));
  check("点「查看」展开该条全文",
    firstFull.hidden === false && (firstFull.textContent || "").includes("正文内容 0"));

  // 点「编辑」应把该条内容回填到表单，并出现「取消编辑」
  const firstEdit = aq(".note-edit");
  firstEdit.dispatchEvent(new adminWindow.MouseEvent("click", { bubbles: true }));
  await wait(300);
  check("点「编辑」回填表单并切到编辑态",
    aq("#note-f-content").value.includes("正文内容 0")
    && aq("#note-save").textContent.includes("保存修改")
    && !aq("#note-cancel").hidden);

  // 点「取消编辑」应恢复导入态
  aq("#note-cancel").dispatchEvent(new adminWindow.MouseEvent("click", { bubbles: true }));
  await wait(300);
  check("点「取消编辑」恢复导入态",
    aq("#note-f-content").value === "" && aq("#note-save").textContent.includes("导入"));

  // 筛选无结果时，空态文案必须是「没有匹配的内容」，而不是「还没有内容」
  // —— 后者会让用户以为数据被清空了。
  aq("#note-flt-q").value = "zzz";
  aq("#note-search").dispatchEvent(new adminWindow.MouseEvent("click", { bubbles: true }));
  await wait(400);
  const emptyText = (aq(".app-empty h3") && aq(".app-empty h3").textContent) || "";
  check("筛选无结果时提示「没有匹配的内容」",
    emptyText.includes("没有匹配"), `实际「${emptyText}」`);
  check("筛选无结果时不再显示列表行", aqa(".note-row").length === 0);

  // 重置后应恢复列表
  aq("#note-reset").dispatchEvent(new adminWindow.MouseEvent("click", { bubbles: true }));
  await wait(400);
  check("点「重置」恢复完整列表", aqa(".note-row").length === 20,
    `实际 ${aqa(".note-row").length} 条`);

  adminWindow.close();

  const failed = results.filter(([, ok]) => !ok);
  console.log(`\n通过 ${results.length - failed.length} / ${results.length}`);
  if (failed.length) console.log("失败：" + failed.map(([n]) => n).join("、"));
  process.exit(failed.length ? 1 : 0);
})();
