/**
 * 校验前端 Markdown 渲染器：直接从 app.js 中提取 escapeHtml / mdInline / renderMarkdown，
 * 用真实的大模型回答（含标题、表格、列表、加粗、引用）跑一遍，确保：
 *   1) 表格被正确解析为 <table><thead><tbody>；
 *   2) 标题/列表/加粗/引用/分隔线均生成对应标签；
 *   3) HTML 被转义，恶意内容不会逃逸为真实标签（XSS 防护）。
 *
 * 用法：node scripts/md_render_check.js
 */
const fs = require("fs");
const path = require("path");

const src = fs.readFileSync(
  path.join(__dirname, "..", "frontend", "static", "assets", "js", "app.js"), "utf8"
);

const startMark = "function escapeHtml(";
const endMark = "/* ---------- 打字机逐字显示";
const s = src.indexOf(startMark);
const e = src.indexOf(endMark);
if (s < 0 || e < 0 || e <= s) {
  console.error("❌ 无法从 app.js 中定位 Markdown 渲染器源码");
  process.exit(1);
}
const code = src.slice(s, e);

// 在受限作用域中求值，取出三个函数
const factory = new Function(`${code}; return { escapeHtml, mdInline, renderMarkdown };`);
const { renderMarkdown } = factory();

const md = [
  "# 🏯 北京3天行程规划",
  "",
  "> 三天按**地理就近排序**，避免来回折返。",
  "",
  "## ⚠️ 行前必读",
  "",
  "- 故宫**周一闭馆**，提前7天放票",
  "- 地铁用**亿通行APP**扫码乘车",
  "",
  "| 时段 | 安排 |",
  "| --- | --- |",
  "| 上午 7:30-12:30 | **天安门广场**（需提前预约） |",
  "| 下午 14:00-17:00 | 故宫 → 景山 |",
  "",
  "1. 第一天：中轴线",
  "2. 第二天：长城",
  "",
  "---",
  "",
  "`inline code` 与 [高德地图](https://amap.com) 链接。",
  "",
  "<script>alert('xss')</script>",
  "",
  "普通段落文本。",
].join("\n");

const html = renderMarkdown(md);
const checks = [
  ["标题 h1", /<h1>/.test(html)],
  ["标题 h2", /<h2>/.test(html)],
  ["无序列表", /<ul><li>/.test(html)],
  ["有序列表", /<ol><li>/.test(html)],
  ["表格 thead", /<thead><tr><th>时段<\/th><th>安排<\/th><\/tr><\/thead>/.test(html)],
  ["表格 tbody 行数=2", (html.match(/<tbody>[\s\S]*<\/tbody>/) || [""])[0].split("<tr>").length - 1 === 2],
  ["加粗", /<strong>地理就近排序<\/strong>/.test(html)],
  ["引用", /<blockquote>/.test(html)],
  ["分隔线", /<hr>/.test(html)],
  ["行内代码", /<code>inline code<\/code>/.test(html)],
  ["外链新窗口", /<a href="https:\/\/amap\.com" target="_blank" rel="noopener">/.test(html)],
  ["XSS 被转义", html.includes("&lt;script&gt;") && !/<script>/i.test(html)],
  ["表格分隔行未渲染为数据行", !/<td>-{2,}<\/td>/.test(html)],
];

// ---- 回归：模型输出的表格经常省略「最后一列的收尾竖线」 ----
// 旧实现要求整行以 | 结尾，导致最后一行掉出表格、页面上露出裸管道符。
const mdNoTailPipe = [
  "| 项目 | 估算 |",
  "| --- | --- |",
  "| 住宿 2 晚 | 900 |",
  "| 餐饮（3 天，含烤鸭） | 300",
  "",
  "合计约 1200 元。",
].join("\n");
const html2 = renderMarkdown(mdNoTailPipe);
const bodyRows2 = ((html2.match(/<tbody>[\s\S]*<\/tbody>/) || [""])[0].split("<tr>").length - 1);
checks.push(
  ["末列缺收尾竖线仍解析为表格", /<tbody>/.test(html2)],
  ["末列缺收尾竖线时行数=2", bodyRows2 === 2],
  ["无裸管道符残留", !/<p>[^<]*\|[^<]*<\/p>/.test(html2)],
  ["表格之后的段落正常", /<p>合计约 1200 元。<\/p>/.test(html2)],
);

let bad = 0;
for (const [name, ok] of checks) {
  console.log(`${ok ? "✅" : "❌"} ${name}`);
  if (!ok) bad++;
}

if (process.env.SHOW_HTML === "1") console.log("\n--- 渲染结果 ---\n" + html);
console.log(`\n通过 ${checks.length - bad} / ${checks.length}`);
process.exit(bad ? 1 : 0);
