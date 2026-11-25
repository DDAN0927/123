# 外部项目架构研究：QuantFlow Pro 基金投资决策辅助

> 研究对象：https://fund-assessment.onrender.com/static/index.html
> 研究时间：2026-11-24
> 取证方式：`curl` 抓原文（5 份）、`/openapi.json` 全量解析（148 路由）、3 个前端模块源码、2 个真实 API 响应
> 对照项目：观潮·模拟行情终端（`index.html`，8 243 行 / 225 函数）

---

## 0. 结论先说

**它和观潮不是一个物种。** 它是「FastAPI 后端 + 多页面 SPA 式前端」的全栈量化系统（148 个路由）；观潮是「单文件纯前端模拟终端」。所以**不能整体照搬架构**，照搬只会把 8 千行炸成 6 万行。

但它有 **4 处设计，观潮当下就能用，且直接命中观潮自己的伤口**（尤其是刚修完的 P1-3 温度计）：

| # | 它的设计 | 观潮的对应缺口 | 价值 |
|---|---|---|---|
| 1 | 接口自带 `data_quality` 信封（几维可用 / 哪几维缺失） | 温度计四维"永远都有值"，没有"某维不可用"的概念 | ⭐⭐⭐ |
| 2 | 面板四态统一（loading / empty / error / ready） | 空态文案散落在各渲染函数里各写一套 | ⭐⭐⭐ |
| 3 | 骨架层带回滚开关（`?shell=off`） | 新功能出事故只能整文件回滚 | ⭐⭐ |
| 4 | 新鲜度徽章唯一入口，禁止各页自拼时间文案 | `synthNote` / `synthBadge` 各自拼口径串 | ⭐⭐ |

---

## 1. 实测技术栈（全部一手取证，非推测）

### 1.1 后端

| 项 | 实测值 | 依据 |
|---|---|---|
| 框架 | **FastAPI**（uvicorn） | 响应头 `x-render-origin-server: uvicorn` |
| 规格 | OpenAPI **3.1**，标题「QuantFlow Pro 量化交易系统」v1.0.0 | `/openapi.json` |
| 路由数 | **148** 条 | 同上 |
| 分组 | **19 个 tag**（行情 35 / 组合阶段六 16 / 基金 11 / 策略 10 / AI Agent 10 / 时段预测 9 / 配置 8 / 策略进化 7 / 国际市场 7 / 话术库 7 / 监控 6 / 短线复盘 6 / 仪表盘 5 / 交易 4 / 消息面 4 / 重仓股板块 3 / 技能调度 3 / MCP 2 / 数据源健康 1） | 同上 |
| 文档 | `/docs` 启用 Swagger UI（CDN 引入 swagger-ui-dist@5） | 实测 200 |
| 鉴权 | **Bearer token**，缺失时返回 `401 {"detail":"缺少 Authorization 请求头"}` | 实测 `/api/config/settings` |
| 数据源 | **akshare**（健康检查里 `"akshare":true`） | `/api/health` |
| AI | 多 provider 装配，`ai_keys` 里 `agnes:true` 其余 false，`ai_providers:["zhipu_glm",…]` | 同上 |
| 部署 | Render（免费实例，冷启动有 interstitial 等待页） | 首次 WebFetch 命中等待页 |

### 1.2 前端

| 项 | 实测值 | 依据 |
|---|---|---|
| 框架 | **零框架、零构建**（无 React/Vue，无 `type="module"`） | `grep 'type="module"'` = 0 |
| index.html | **10 335 行** / 562 974 B | `wc -l` |
| 外部 JS | **20 个** `/static/js/*.js`（wizard / freshness / signal-progress / sectors / stage6-portfolio / evolution / ai-script / prediction / sector-board / market-style / recommendations / workbench / strategy-fit / data-gate / chanlun / signal-scan / institution-holdings / global-market / version-modal / qf-shell） | HTML `<script src>` |
| 外部 CSS | **10+ 个**，含 `tokens.css` / `stage5-typography.css` / `hud.css` / `stage6.css` / `prediction.css` / `stage5-responsive.css` / `stage5-motion.css` / `aurora-theme.css` / `workbench.css` / `global-market.css` | `<link rel=stylesheet>` |
| 内联 script | 24 个块 | `grep -c '<script'` |
| 页面视图 | **25 个** `#page-*` 容器 | `grep 'id="page-'` |
| 导航 | `switchPage('xxx')` 全局函数 + `data-page` 属性，一级 5 个（行情/持仓/策略/监控/设置）+ subtab 二级 | HTML 1093–1124 行 |
| 缓存策略 | 手写查询串版本号，如 `sector-board.js?v=20261122c`、`qf-shell.js?v=20261122a` | `<script src>` |

---

## 2. 它前端真正的架构：一个「渐进增强骨架层」

这是该项目最值得读的部分。`qf-shell.js`（51 788 B）开头的注释本身就是一份架构说明书，摘其硬约束原文：

```
STAGE8 · qf-shell.js —— QuantFlow Pro 终端化骨架（零框架 / 零构建 / 原生 ES5+DOM）
全局命名空间：window.QF
  QF.shell   boot / buildNavIndex / migrate / sync / wrapSwitchPage / chromeHeight / pinToggle / enabled
  QF.flyout  侧栏 hover/focus 二级浮层（fixed，规避 overflow:hidden 裁剪）
  QF.indexbar 顶部指数情绪条
  QF.panel   面板三态（loading / empty / error / ready）+ QF.missing
  QF.table   .qf-table 增强（粘性表头、排序 + MutationObserver 单次重放）
  QF.wb      工作台模板（localStorage qf.wb.layout.v1，坏 JSON fail-safe）

硬约束：
  ① 不引入任何依赖；不改后端；不改存量渲染函数业务逻辑（只在空/错态分支加 1~2 行）；
  ② 所有列表/面板渲染用 textContent / createElement，全文件不拼接 HTML 字符串；
  ③ 回滚开关：?shell=off 或 localStorage['qf.shell.off']='1' → 本文件首段直接 return
```

四个可迁移的设计判断：

**① 用「包装」而非「重写」接入存量代码。**
`wrapSwitchPage` 不是替换 `switchPage`，是包一层——切页前后插入自己关心的逻辑（同步侧栏高亮、懒加载）。这样 148 个路由的页面不用改一行。观潮若要加架构层，这也是唯一安全的姿势。

**② 回滚开关写在文件第一个判定，早于任何 DOM 操作。**
```js
if (isShellOff()) { window.QF.shell.enabled = false; return; }
```
配合 `try/catch` 包住 localStorage 读（隐私模式禁用时不抛错，按"未关闭"处理）。这比"发新版→出问题→再发回滚版"快一个数量级。

**③ 硬性禁止拼 HTML 字符串。**
`mk(tag, cls, text)` 里第三参强制走 `textContent`。项目里所有表格/列表都这么建 DOM。观潮目前是「拼字符串 + `escapeHTML` 转义」——能防注水，但依赖每一处都记得转义；它是从机制上不给拼接的机会。

**④ localStorage 坏 JSON fail-safe。**
读布局配置时 `JSON.parse` 裹 try/catch，失败即用默认布局，不抛错、不白屏。

---

## 3. 「数据质量门禁」：观潮最该学的部分

`data-gate.js`（11 022 B）开头的设计意图原文：

```
数据质量门禁（三道防线）
  采集：指数 / 全市场涨跌家数 / 涨跌停 / 板块覆盖
  数仓：主力净流入字段完整度 / 复盘数据质量
  投研：资金面可用性 / 数据源健康
原则：缺失即失败或降级，不补 0；
      门禁结论只说明"这屏数据能不能当结论看"，不预测行情、不构成投资建议。
```

它有三个层次，逐层递进：

**层次一：每条检查项是结构化对象，不是一句话。**

```js
check(key, group, name, status, value, desc)
// status ∈ pass | warn | fail
```

于是可以按组汇总、可以数「几条 pass 几条 fail」，而不是散落的 `if (!x) showTip('数据缺失')`。

**层次二：缺失一律降级，绝不补 0。**

这是整份代码里最硬的一条原则。观潮的纪律面板已经在做类似的事（样本 <5 判"样本不足"、旧记录缺 `chg` 落"缺失态"），但没有把它抽象成统一规则，只在这一个面板里实现。

**层次三：门禁只回答「能不能当结论看」，不做行情预测。**

这是产品定位层面的克制：门禁的职责边界被明确写进注释，防止它慢慢长成一个"建议引擎"。

### 3.1 更狠的一招：把质量元数据塞进业务响应里

实测 `/api/market/thermometer` 的真实响应（节选）：

```json
{"data":{
  "score":52.8, "level":"中性", "action":"观望,等待方向", "score_available":true,
  "data_quality":{
    "available_dims":1, "total_dims":4,
    "missing_dims":["capital_flow","sector_rotation","sentiment"]
  },
  "components":{
    "index_trend":{"score":59.2,"weight":0.3,"available":true},
    "sector_rotation":{"score":50,"note":"板块数据不可用","available":false},
    "capital_flow":{"score":50.0,"northbound_net":null,"northbound_available":false,"available":false,"complete":false}
  }}}
```

注意它怎么处理不可用的维度：**分数置 50（中性），并打上 `available:false` + `note`，同时顶层承认 `available_dims:1 / total_dims:4`。**

也就是说，用户看到 52.8 分的同时，能一眼知道"这分数是 1 个维度撑起来的，另外 3 个维度没数据"。**它不隐藏残缺，而是把残缺做成数据的一部分。**

这正好是观潮 P1-3 的下一层。观潮刚修完"波动维度恒为 4"，但那修的是"算错了"；**它没有解决"如果某一维根本没数据该怎么办"** ——因为观潮是模拟数据，四维永远算得出来。一旦将来接真实数据（或用户导入残缺标的），现在这套代码会算出假分数而不自知。

### 3.2 数据源健康台账

实测 `/api/data/health`：

```json
{"generated_at":"2026-11-24 05:53:11","overall":"ok",
 "unverified":["sector_stocks","global_news","fund_realtime",…],
 "sources":[{"name":"index_realtime","label":"指数实时行情","status":"ok",
   "last_success_at":"…","last_success_age_s":6,"last_attempt_at":"…",
   "last_error":"","last_count":8,
   "consecutive_failures":0,"total_success":4,"total_failure":0}]}
```

每个数据源都记 `consecutive_failures` / `last_error` / `last_success_age_s`。观潮只有一个模拟行情生成器，没有"源"的概念；但**这个字段设计对观潮导入数据的场景可直接复用**——导入失败几次、上次成功多久前、错误原文是什么。

---

## 4. 它的弱点（别学的地方）

| 弱点 | 证据 | 说明 |
|---|---|---|
| **请求模型严谨，响应模型松散** | 61 个 schema 全是 `XxxRequest`（BuyRequest / BacktestRequest / DispatchRequest…），而响应清一色 `{"additionalProperties": true, "type":"object"}` 裸 dict | 说明后端只对**输入**做校验，**输出**没有契约。前端只能靠约定读字段，一处改名就静默失效。观潮虽是前端，但 `selftest` 里的结构化断言相当于在做"输出契约"，这点观潮反而更严 |
| **架构复杂度失控** | 10 335 行 HTML + 20 JS + 10+ CSS + 25 页面 + 148 路由 | 单页平均 400 行还要跨 30 个资源文件；`?v=20261122o` 这种手写版本号说明构建体系缺位，靠人工保证缓存一致 |
| **靠注释维持规范** | 注释里写「P1-4 / K6 100% 覆盖」「两处数值必须同步维护」 | 没有 lint / 测试守这些约束，全靠人记。观潮有 46 组 selftest + 249 条探针断言，在这点上比它扎实 |
| **对比度还在补** | `index.html :root` 注释：「stage5 R1: 亮色回退对比度过 AA，muted #8B9DB4 = 6.2:1（原 #6e7681 仅 3.8:1）」 | 观潮已做到亮/暗 0 违规并有 `contrast.js` 常驻探针 |

---

## 5. 借鉴清单（按 ROI 排序，标注观潮可落地性）

### P0 · 数据质量信封（最该做）

把"维度可用性"做成结构化字段，贯穿温度计 / 分散度 / 纪律面板三处。

```
{ available: n, total: m, missing: [...], 各维 {score, available, note} }
```

- **温度计**：每维带 `available`，不可用维分数置中性且不参与加权分母；面板显示「1/4 维可用」
- **分散度**：相关系数算不出时（常数序列），矩阵对应格标"—"并计入 missing（观潮已返回 `null`，但没把"缺了几对"报出来）
- **纪律面板**：已有 `pass:null`，可统一成同一套信封

落地成本：约 3 处渲染函数 + 1 个工具函数 + 6~8 条 selftest 用例。**收益：把观潮"诚实"这条主线从"各面板各自诚实"升级为"有一个统一的说法"。**

### P0 · 面板四态统一

`loading / empty / error / ready` 四态收敛到一个 `renderPanelState(el, state, opts)`，替代散落的空态文案。

### P1 · 骨架层回滚开关

新加的面板/图层支持 `?panel=off` 或 `localStorage` 开关，首段判定后 return。观潮已有 3 处 `location.search` 用法，可规范化成一个 `featureFlag(name)` 工具。

### P1 · 新鲜度徽章唯一入口

`Freshness.render({asOf, estimated, lagDays, note})` —— 观潮的 `synthNote` / `synthBadge` 正是干这事，但两者各自拼串。合并成唯一入口后，"禁止各页自拼时间文案"这条规则才有机制保障。

### P2 · z-index 层级规范

它的 `tokens.css` 定义 `base(0) < sticky(30) < nav(40) < overlay(60) < modal(90) < toast(100)` 是"全站唯一允许的取值"。观潮层叠值散落，抽屉调层时容易踩。纯 CSS 变量改造，成本低。

### 明确不借鉴

- **25 页面 + 148 路由的多页结构**：观潮是单屏终端，产品形态不同，照搬即毁
- **FastAPI 后端 + akshare 真实数据**：这是产品定位变更（模拟 → 真实），不是架构优化。观潮当前所有文案都在明示"模拟行情"，接真实数据需要另一套合规与免责设计，需单独立项
- **`?v=` 手写缓存版本号**：观潮是单文件，无此问题

---

## 6. 一句话总结

这个项目的**后端是常规的 FastAPI 分层（148 路由按域分 tag），前端是「零框架 + 渐进增强骨架层」的老派做法**——技术选型上并不先进，甚至有点保守（无构建、无模块化、靠注释维持规范）。

真正值得学的不是它的技术栈，而是**它对「数据不可用」的处理姿态**：不可用的维度照样出现在响应里，打上 `available:false`，顶层坦白 `available_dims:1/total_dims:4`，缺什么列得清清楚楚。

这跟观潮正在做的事是同一条路——只是它已经走到了"把残缺结构化"，观潮还停在"每个面板各自诚实"。
