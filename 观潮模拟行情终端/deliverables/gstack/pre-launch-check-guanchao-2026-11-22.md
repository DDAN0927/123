# 观潮 / Aether Capital · 上线前全检（代码审查 + 安全审计 + QA 测试）

**日期**：2026-11-22
**场景**：上线前全检（代码审查 / 安全审计 / QA 测试与发布检查）
**参与成员**：产品官（product-reviewer）+ 安全卫士（security-officer）+ 质量门神（qa-lead）
**审查基线**：`master` @ `d69c3d9`，工作区另有 `index.html` 未提交改动（+133 / −15，合成数据角标 + 文案 + `safeCloudBase`）
**上一轮参照**：`deliverables/gstack/code-audit-guanchao-2026-11-21.md`（37 条，3 条 P0）

---

## 📌 TL;DR（执行摘要）

- 整体结论：🔴 **No-Go（条件性）** —— 3 条阻塞项 + 1 条条件阻断项（限流并发绕过：若本次公开开放注册，则升级为阻塞）。都不是架构问题，合计改动量约 2 小时（5 行角标修复 + 3 段文案 + 3 个配置值 + 1 处限流写后判）。
- 自动化基线是健康的：**74/74 用例通过**（单测 32 + 后端提醒 6 + 页内自检 36），4 段内联脚本 `node --check` 全过，桌面/移动/live 快照三种上下文 **0 页面错误、0 console.error**。**但这 74 条不覆盖限流闸门**——并发用例的 N 只有 2/3，小于阈值 5，永远测不到 429（详见 P1-11）。
- 三条历史 P0 与 SEC-02~05 经复核：**SEC-01/04 已闭环**（SEC-04 按「不硬锁邮箱」的原定目标判定达成）；**SEC-02/03/05 只闭环了一半**——计数器确实原子了，但「读后判」的闸门没关，并发可击穿（已由安全官与质量门神独立复现）。
- 本轮未提交改动的核心目标「合成数据必须标注」完成度约 60%：角标机制本身可用，但被一条 CSS 覆盖导致**空角标常显**（P0 视觉缺陷），且指数卡仍把硬编码常量标成「实时」。
- 下一步：修 3 条阻塞 → （若开放注册）再修限流 → 落地 3 项部署配置 → 复跑 74 条 → 转 Go。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🔴 **No-Go**（3 条阻塞项清零后可转 🟢 Go；若公开开放注册，限流项一并清零） |
| 严重度分布 | 🔴 4 / 🟠 14 / 🟡 11 / 🟢 7（去重合并后 36 条） |
| 关键行动项 | 10 条（3 组 P0 阻塞 + 1 条条件阻断 + 6 条上线前/后续） |
| 建议负责人 | 前端：BLK-1 / BLK-3 / P1-1；后端：P1-0 / P1-3~7；发布：BLK-2 / P1-9 |
| 阻塞性质 | 无架构级返工；最高风险是「部署成功但功能全废」（`ALLOWED_ORIGIN` 留空） |

---

## 1. 各成员核心结论

### 🔍 产品官（代码审查 + 产品可信度）

- 核心判断：**代码质量可以上，产品可信度还不能上**。38 条单测全绿、diff 无新增 XSS/P0 逻辑缺陷，历史 P0 与 SEC-02~05 的代码确实改了；但「数据真实性」这条主线只做了一半——`INDICES` 是**全文件无写入的硬编码常量**，`renderIndices` 却给每张卡打「实时」，还带「成交 1.12 万亿」「南向 +42.6 亿」「VIX 14.2」；`#heroChart` 的 aria-label 写死「实时价格走势图」；DATABASE strip 仍列 8 项未实现能力。
- 关键建议：`synthNote` 现在只对 `1D` 返回角标，而抽屉默认区间就是 `1M`、`loadRealKline` 只在 `s.live` 内调用——**导入标的的 1M–5Y 全程合成且永远无角标**，比原 FE-03 的 1D 问题更严重；智策评分对真实标的是「常数 + 随机游走」（120 只标的 `资金:66`/`基本面:40` 完全相同，score 值域仅 32~71，≥82 档位不可达），却对外称「按模型评分排序」。
- 已确认修复：FE-01、FE-02（`peerPECache` 三条替换路径均 clear）、FE-06（500/500/200 两侧对齐）、FE-07、BL-03、BL-06、SEC-01/02/03/04/05/12/18 的代码侧改动。
- 性能复核：`pickSignalStocks` 整链约 4 ms、`renderTable` 7.6 ms —— **不是瓶颈，不需要优化**（推翻上一轮 FE-02 之外的性能担忧）。

### 🛡️ 安全卫士（OWASP 2021 + STRIDE）

- 核心判断：**认证地基扎实，限流层只是「计数对了，闸门没关上」**。SQL 20 处全参数化、token 256 位随机、`/api/state` 按 session 的 `user_id` 隔离（无 IDOR）、`timingSafeEqual` 自实现、无 cookie 故无经典 CSRF；52 处 `innerHTML` 逐点核过，**未找到可利用 XSS**。
- 关键发现（均自写探针实测，未打外网）：同 IP **并发 20 次注册 → 20 个全 200，users 表真建 20 行**；**并发 20 次错误登录 → 20 个全 401**（顺序才是第 6 次 429）——`ipGate()` 先 SELECT、再跑 ~100 ms 的 PBKDF2、最后才 `bumpLock`，有效配额 = 并发数 × 5。cron 发信无预算，实测 60 用户命中 = **61 子请求**，超免费版 50 上限后本轮静默中断。
- 关键建议：限流改「写后判」（`INSERT … ON CONFLICT … RETURNING fails`，在昂贵哈希**之前**拒绝）；cron 单轮发信上限 ≤20；强制 `Content-Type: application/json` 让跨站 no-cors 请求触发预检（否则攻击页 6 次即可锁死受害者 IP）；补 CSP + `frame-ancestors 'none'`。
- 闭环判定：SEC-01、**SEC-04** 已闭环（SEC-04 按「不硬锁邮箱」的原定目标判定——`bumpOnly` 恒写 `locked_until=0`、`ipGate` 只查硬锁，目标确实达成；并发下 `emailBackoffMs` 因读-改-写恒读 `fails=0` 而失效，属「拖慢串行爆破」这一附加收益折损，不构成「知道邮箱就能锁死他人」的回归）；SEC-02/03/05 **部分闭环**（原子计数 ✅ / 闸门顺序 ❌ / 发信预算 ❌ / 任意键入库 ❌）。现有单测的并发用例只断言计数器且 N=2/3 ≤ 阈值 5，**从没测到过阈值**，这是漏网的根因。

### ✅ 质量门神（QA 测试与发布）

- 核心判断：**功能主干健康，但未提交改动带一个确定性 P0 视觉缺陷**。74/74 全绿、0 页面错误；`?selftest` 36/36；脚本抽段 `node --check` 4/4（含拼接后校验，无跨块重复声明）。
- 关键发现：`.synth-badge{display:inline-flex}`（index.html:252）是作者样式，会覆盖 UA 的 `[hidden]{display:none}`，`setSynthBadge()` 里的 `el.hidden = !text` **完全失效**。实测切到 1M 时 `hidden=true` 但 `getComputedStyle().display === "flex"`、尺寸 16×6、带琥珀色描边与底色——首屏 hero、详情抽屉（默认 1M，一开就有）、基本面 tab 各出现一个**空胶囊**。同文件已有三处同类防护（`.dh-pane[hidden]` / `.filter-chip[hidden]` / `.fav-group-row[hidden]`），唯独漏了 `.synth-badge`。加一行 `.synth-badge[hidden]{display:none}` 后实测空态 16×6 → 0×0，填充态 56×23 不受影响。
- 关键建议：角标「该显示时必须显示」的分支全部正常（7 例逻辑表全对，18 例 `safeCloudBase` 行为表全对），问题只在空态；`heroMeta` 文案改动无选择器/逻辑依赖，无回归。发布侧 3 个配置占位符未填，其中 `ALLOWED_ORIGIN=""` 是「部署成功但云同步 100% 不可用」的典型坑。
- 诚实标注未执行：云同步端到端、邮件实发、跨浏览器、东财真实数据路径（本机 IP 被封）——全部因「后端未部署 / 环境限制」，非跳过。

---

## 2. 综合审查发现（去重合并，按严重度）

| # | 严重度 | 类别 | 位置 | 问题 | 建议 | 来源 |
|---|--------|------|------|------|------|------|
| BLK-1 | 🔴 P0 | 视觉缺陷 | index.html:252 / 257-258 / 3356-3361 | `.synth-badge{display:inline-flex}` 是作者样式，恒胜 UA 的 `[hidden]{display:none}`（与特异度无关），`el.hidden` 只改语义、视觉失效 → 空胶囊在**抽屉默认 1M（最高频交互）**、hero 非 1D、基本面 tab 共 4 处 100% 复现；尺寸精确可算 16×6，与实测吻合。属**纯视觉缺陷**（`hidden` 语义仍在，AT 不可见、键盘焦点也进不去，**不是 a11y 问题**） | ① `.synth-badge[hidden]{display:none}` ② `.synth-line[hidden]{display:none}` ③ `setSynthBadge` 同步隐藏 wrapper，**必须限定 `parentElement.classList.contains('synth-line')`**——`#heroSynth` 的父元素是 `.cc-foot`（含价格/MA20/MA60 图例），无条件隐藏父级会把图例一起藏掉，比原 bug 更严重 | 质量门神 + 产品官（四版 A/B 实测：仅修胶囊仍留 +10px/+8px 空白，完整修法精确还原 HEAD 的 12px/10px） |
| BLK-1b | 🔴 P0（同批） | 布局 | 257-258 / 1883 / 1943 / 1952 | `.synth-line` 是常驻 wrapper，角标隐藏后高度为 0 但 `margin:2px 0 8px` 仍在 → 抽屉约 10px、基本面两处约 8px 的永久空隙（margin 折叠后） | 与 BLK-1 一并修；单列时为 P3 | 产品官 |
| BLK-2 | 🔴 P0 | 部署阻塞 | wrangler.toml:6,12,13 | `database_id` 仍是占位符（部署即失败）；`ALLOWED_ORIGIN=""`（浏览器拒绝全部跨域，云同步全废）；`ALERT_FROM=alerts@example.com`（Resend 必拒） | 填真实值 + `wrangler secret put RESEND_API_KEY` | 安全卫士 + 质量门神 |
| BLK-3 | 🔴 P0 | 数据真实性 | 2605-2612 / 3429 / 1491 / 1664-1671 | `INDICES` 硬编码常量（全文件无写入）却渲染「实时」+ 虚构成交额/南向/VIX；`#heroChart` aria-label 写死「实时」；DATABASE strip 列 8 项未实现能力 | 指数卡改「静态示例」去「实时」；aria-label 去「实时」；未实现项标「演示」或删除 | 产品官 |
| P1-0 | 🟠 P1（条件 P0） | 认证/DoS | worker.js:203-208、286-291、230-252 | 限流「读在计数前」：并发 20 次注册全部 200（真建 20 行）、并发 20 次错误登录全部 401；有效配额 = 并发数 × 5。注册侧更纯粹是 check-then-act（没有慢哈希，仅事件循环让渡）。**若本次公开开放注册，本条升级为阻断项** | 必须「写后判」：单条 `INSERT … ON CONFLICT … RETURNING fails`，用**返回值**判阈，在昂贵哈希之前拒绝。仅把 `ipGate` 与 `bumpLock` 两行调换**不够**——中间仍有 await 边界 | 安全卫士 + 质量门神（独立复现一致，定级已达成共识：P1 + 条件升级） |
| P1-1 | 🟠 P1 | 数据真实性 | 3352-3355 / 5088 / 5203 / 5296 | `synthNote` 仅 `1D` 返回角标；抽屉默认 `1M`、`loadRealKline` 只在 `s.live` 内调用 → 导入标的 1M–5Y 全程合成且无标注；hero 从不调 `loadRealKline`，切 1M/6M/1Y 全合成却显示「SZSE · 1M」 | 角标判定改为「无 `_realKline` 即标」；hero 补 `loadRealKline` | 产品官 |
| P1-2 | 🟠 P1 | 数据真实性 | 4774 / 4913-4920 / 3367-3382 | 智策评分 35% 权重是常数（`conv:50, revG:0, rating:'hold', dy:0`）+ `hashStr` 随机游走；120 只标的 `资金:66`/`基本面:40` 完全相同，score 仅 32~71，「积极关注」档不可达 | 卡面标「演示评分」，或先批量拉真实 K 线再评分 | 产品官（**单一来源**，未经第二方复算；结论基于抽取函数 + 120 只真实形态标的的独立探针） |
| P1-3 | 🟠 P1 | DoS | worker.js:450-484（对比 421-424） | `MAX_ALERT_CODES` 只管行情查询，发信每命中 1 次 fetch 无上限；实测 60 用户 = 61 子请求 > 50，第 51 名之后本轮静默不发 | 单轮发信上限 ≤20，余量留待下轮 | 安全卫士 |
| P1-4 | 🟠 P1 | CSRF/DoS | worker.js:57 及登录入口 | 不校验 `Content-Type` / `Origin`；攻击页 `fetch(mode:'no-cors', Content-Type:'text/plain')` 免预检，实测 6 次后受害者正确密码返回 429 | 非 JSON 直接 415（强制预检）+ 校验 Origin | 安全卫士 |
| P1-5 | 🟠 P1 | 纵深防御 | index.html（无 CSP）/ jsonp:7164-7189 / sinaPage:7204-7238 | 无 CSP、无 frame 保护；token 存 localStorage；第三方 JSONP 脚本在本源执行，可直读 `guanchao-cloud-v1` | 前端托管侧下发 CSP + `frame-ancestors 'none'`；评估 token 迁移 | 安全卫士 + 质量门神 |
| P1-6 | 🟠 P1 | 认证设计 | worker.js:220-221、schema | 注册即发 token、邮箱从不验证；配合 P1-0 可批量建号并向任意邮箱发信 | 邮箱验证或注册后限制发信；公开注册前必须解决 | 安全卫士 |
| P1-7 | 🟠 P1 | 密码学 | worker.js:14-16 | PBKDF2 100k（平台上限）< OWASP 600k，最小密码仅 8 位；D1 泄露即可 GPU 离线爆破 | 加 `PASSWORD_PEPPER` 秘密 + 最小 12 位 + 弱密码黑名单 | 安全卫士 |
| P1-8 | 🟠 P1 | 可用性 | index.html:6850-6856 | `safeCloudBase` 只放行 `*.workers.dev`/localhost/同源；`https://api.mydomain.com`、`https://guanchao.pages.dev`、`http://localhost:8787` 全被拒 → 自定义域用户按 README 填地址必然失败，本机也无法联调 | 判据改为「`u.protocol==='https:'` 且 `!u.username && !u.password && u.pathname==='/' && !u.search && !u.hash && (同源 \|\| host==='localhost' \|\| host==='127.0.0.1' \|\| endsWith('.workers.dev'))」；**不要为联调放开 http**，本地联调单独加开关 | 产品官 + 质量门神 |
| P1-9 | 🟠 P1 | 发布流程 | index.html:APP_VERSION / CHANGELOG.md | 本批 +133/−15 改动无 CHANGELOG 条目，`APP_VERSION` 仍 1.7.0、`BUILD_DATE` 仍 2026-11-19 | 补条目 + bump 版本 | 质量门神 |
| P1-10 | 🟠 P1 | 健壮性 | 7379-7405 | 新浪兜底 64 页循环 + 120s 预算，无 `AbortController`/取消位，关弹窗后继续跑满 | 加取消标志，`closeSyncModal` 置位 | 产品官 |
| P1-11 | 🟠 P1 | 测试 | tests/unit/auth.test.mjs:67-95 | **「74/74 全绿」不能推出「限流安全」**：两条并发用例的 N 只有 2 和 3，均 < `LOGIN_MAX_FAILS=5`，永远碰不到阈值，只断言计数器原子性；断言 429 的三条全是顺序 `for` 循环。并发路径零覆盖，这正是 P1-0 逃逸的根因。另：新逻辑（`synthNote`/`setSynthBadge`/`safeCloudBase`/`renderCloudTarget`/`pickSignalStocks`）与云同步全链路亦零覆盖 | 补「并发 20 错密码 → 429 数 ≥15」「并发 20 注册 → 429 数 ≥15」；再补 `safeCloudBase` 18 例与 `synthNote` 4 分支 | 质量门神 + 产品官 |
| P1-12 | 🟠 P1 | 功能静默失效 / 可定向利用 | worker.js:408-424 | `MAX_ALERT_CODES=800` 是**全局共享**配额（所有用户代码汇进一个 Set 后统一截断），截断按 Set 插入序 = `LIMIT 1000` 扫描序，**确定性**（实测三轮集合完全相同）。攻击链：注册 5 个账号（P1-0 让这很容易）→ 每账号塞满 200 条提醒（`MAX_ALERTS=200`）→ 代码填不存在的 `ZZZ0001…ZZZ1000`（`CODE_RE` 允许字母开头，`secid()` 也合法）→ 800 配额被垃圾占满，**真实用户提醒全部落到第 801+ 位，永久不被检查**。用户侧：一条都不响、界面仍显示「监控中」、零错误，不会报障；且下一轮仍是同一批垃圾在前 800，**不可自愈** | 改「截断」为「按轮次轮转」：`offset = cursor % codes.length`，环形切片取 800，游标存 `cache` 表 `key='alert_cursor'`（**无需改 schema**），保证每代码在 N 轮内必被查到 | 安全卫士（P2→P1，理由：定向可利用 + 完全静默 + 不可自愈，三者同时成立） |
| P1-13 | 🟠 P1 | 安全配置误导 | backend/README.md 第 3 节 / worker.js:57 | README 教用户把 `ALLOWED_ORIGIN` 填 `*`（本地调试用），而代码**不拦 `*`**（worker.js:57 只判 `allowed && origin === allowed`，`*` 会原样回显）。**必须与 P1-0 同批修**：P1-0 只解决「同一 IP 的并发」，`*` 放行后攻击者可**换着 IP 打**，IP 维度限流照样形同虚设。危害面澄清：Worker 全程未设 `Access-Control-Allow-Credentials`，认证走 `Authorization: Bearer` + localStorage，**不存在跨站盗用已登录 Cookie 的路径**；泄露面是响应体里的 token 与公开接口 | README 删掉 `*` 的说法并明确「必须精确 origin」；`cors()` 加一行 `if (env.ALLOWED_ORIGIN === '*')` 不返回 ACAO（配错时默认拒绝） | 安全卫士 + 质量门神（双方逐字核实） |
| P2-1 | 🟡 P2 | 可用性 | worker.js:404-406 | `LIMIT 1000` 无 `ORDER BY`、无游标 → 第 1001 个用户起永久失检（触发门槛 1000+ 用户，故 P2；与 P1-12 同根因，建议一并改成游标） | 游标分页 | 安全卫士 + 产品官 |
| P2-2 | 🟡 P2 | 信息泄露 | worker.js:194、512 | 500/502 回显 `e.message`（含表名/列名/上游 URL） | 对外只给 code + requestId | 安全卫士 |
| P2-3 | 🟡 P2 | 资源耗尽 | worker.js:350-375 / 115-117 | `/api/state` 无写频率限制；`readBody` 直接 `req.json()`，实测 2MB body 照收 | `updated_at` 最小间隔 + `Content-Length` 早退 | 安全卫士 |
| P2-4 | 🟡 P2 | 缓存击穿 | worker.js snapshot 路径 | 无认证、无 in-flight 锁，实测 5 并发 = 150 次上游抓取 | `refreshing_until` 乐观锁 + IP 限流 | 安全卫士 |
| P2-5 | 🟡 P2 | 一致性 | worker.js:404 vs 463 | cron 读-改-写会整行覆盖竞态窗口内用户的改动：实测「新增提醒 a2 + 改 cash=123456」在 cron 写回后 **a2 丢失、cash 回滚到 100000**，用户无感、换设备才暴露。**注意：不会重复发信**——`putState`（358-367）用服务端 `old.hit` 覆盖入参 `hit`，这条合并挡住了重复发信（该合并逻辑本身零测试覆盖） | `UPDATE … AND updated_at=?` 乐观锁；并给 hit 合并补一条单测 | 产品官（实测修正安全官原「重复发信」表述） |
| P2-6 | 🟡 P2 | 资源耗尽 | worker.js cron 全量解析 | 每轮 `JSON.parse` 最多 1000×400KB，实测 60 行 152ms → 外推 1000 行 ≈2.5s，免费版 CPU 限额下会打死 cron | 拆 alerts 明细表 | 安全卫士 |
| P2-7 | 🟡 P2 | 安全 | index.html:6613-6619 / 6847 | 备份导入仍会恢复 `cloud.base`。**主路径证据**：README 教用户「直接打开 index.html」→ 页面是 `file://`，`sameHost` 恒 false，白名单是唯一防线；而白名单含 `*.workers.dev`，**任何人都能免费申请该后缀子域**。攻击者诱导用户导入一份「恶意备份」，下次登录的邮箱与密码就会 POST 到攻击者 Worker（有界面警告 + `renderCloudTarget` 显示目标域，故 P2） | 备份**永不恢复 base**，地址只允许手输；`safeCloudBase` 保留给「手输地址」与「同源」两处 | 安全卫士 + 产品官（补 `file://` 主路径证据） |
| P2-8 | 🟡 P2 | 响应式 | 244-248 / 946 | `.cc-foot` 无 `flex-wrap`；≤760px 仅改 padding，新增 nowrap 角标（~105px）+ legend + heroMeta 在 360px 必溢出 | `flex-wrap:wrap` 或窄屏隐藏角标文字 | 产品官 |
| P2-10 | 🟡 P2 | UX | 6919 | `renderCloudTarget` 用 `value \|\| cloud.base`，输入框清空后仍显示旧域名 | 判 `value === ''` | 产品官 |
| P2-11 | 🟡 P2 | UX | 云同步弹窗 | 地址被拒时输入框静默清空、⚠ 提示同时消失，用户只看到「我填的地址没了」 | 清空时保留 warn 文案 | 质量门神 |
| P2-12 | 🟡 P2 | 工程 | 仓库根 | `node --test tests/unit/` 在 Node v22 + Windows 报 `Cannot find module`，必须 `node --test "tests/unit/*.test.mjs"`；无 package.json / 无 CI | 加 `package.json` 的 `test` 脚本 + 一条 CI | 质量门神 |
| P3-1 | 🟢 P3 | 纵深防御 | 7000 / 2597 | `cleanValue` 允许 `__proto__` 键；`GROUP_MAP[sector]` 未用 `Object.create(null)`（与 2415 不一致） | 键过滤 + 统一索引构造 | 产品官 + 安全卫士 |
| P3-2 | 🟢 P3 | 代码质量 | 2068-2087（`#legacyCloudTpl`） | 17 个 legacy id 躺在 inert `<template>` 内：**活动 DOM 重复 id = 0**（Playwright 实测 `dupInLiveDoc: []`），`$()`/`$$` 均不会遍历 template，故**不是缺陷**；但死标记已误导过评审，且全文件零引用 | 删除整段或把 id 改 `legacy-*` 前缀 | 质量门神（已证伪「16 个重复 id」的原判） |
| P3-3 | 🟢 P3 | 性能 | 5059-5061 | `scoreVerdict` 内部已调 `computeDiag`，外面又调一次 → 每卡 2× | 复用 `dg.score` | 产品官 |
| P3-4 | 🟢 P3 | 可访问性 | 251-258 | 角标字号 9.5px 为全页最小，与 `heroMeta` 10.5px 只差 1px，与「必须一眼可见」的注释矛盾 | 提到 11px 或加图标 | 产品官 |
| P3-5 | 🟢 P3 | 文案 | 7 | meta description 仍写「实时行情」 | 改「行情」 | 产品官 |
| P3-6 | 🟢 P3 | 一致性 | 3354 vs 4774 | 模拟标的 1D 打「模拟数据」角标，同抽屉财务/估值块不打（`est` 只判 live/imported） | 统一判定口径 | 产品官 |
| P3-7 | 🟢 P3 | 移动端 | 首屏 | 390px 下 13px 横向溢出（`.hero-glow` right=418 / `.tape-track`），A/B 对照 HEAD 与工作区一致 → **非本次回归** | 排入后续迭代 | 质量门神 |

### 历史问题状态复核

| 判定 | 条目 |
|---|---|
| ✅ 已闭环 | SEC-01（`alertHit` 四分支）、**SEC-04**（`bumpOnly` 恒写 `locked_until=0`、`ipGate` 只查硬锁，「不硬锁邮箱」目标达成；附注：并发下 backoff 恒 0，附加收益折损）、SEC-12（`esc()` 已接邮件）、SEC-18（cron try/catch）、FE-01（`isSimulatable`）、FE-02（`peerPECache` + 三条 clear 路径）、FE-06（500/500/200 两侧对齐）、BL-03、BL-06 |
| 🟠 部分闭环 | **SEC-02**（计数原子 ✅ / 闸门顺序 ❌）、**SEC-03**（结构校验 ✅ / 发信预算 ❌ / 任意键入库 ❌ / 无游标 ❌）、**SEC-05**（串行限流 ✅ / 并发全穿 ❌）、**FE-03**（仅 1D）、**FE-04**（sim 未标）、**FE-05**（已动态化但评分口径失真）、**FE-07**（控制逻辑本身正确、18 例行为表全对，但白名单放行任意 `*.workers.dev`——任何人都能免费申请，攻击者同后缀可收凭据）、**FE-11**（`account.positions` 仍 `{}`，被 `CODE_RE` 挡住） |
| ❌ 仍存在 | SEC-06（用户 LIMIT 无游标）、SEC-07（错误回显）、SEC-08（state 无写限速）、SEC-09（cron 全量解析）、SEC-10（snapshot 击穿）、SEC-11（PBKDF2 强度）、SEC-13（假哈希迭代时序差）、SEC-14（409 枚举）、SEC-17（cron 丢更新）、**SEC-19**（请求体无上限）、**SEC-20**（跨站锁 IP）、**SEC-21**（发信无预算）、**SEC-22**（代码截断饥饿）、**SEC-23**（README 教 `*`）、FE-13、FE-14、**FE-19**（safeCloudBase 过窄）、BL-02、BL-07 |
| ⚪ 无法验证 | SEC-11（PBKDF2 100k 是否超免费版 10ms，需部署）、BL-01（东财是否仍按 IP 封禁，本机不可压测）、BL-02/BL-07（需真实浏览器）、任何 Worker 线上运行时行为 |

> **编号说明**：本报告正文用 `BLK-* / P1-* / P2-* / P3-*` 作为主键；历史项沿用 2026-11-21 报告编号；本轮新增安全项从 SEC-19 起（SEC-19→P2-3、SEC-20→P1-4、SEC-21→P1-3、SEC-22→P1-12、SEC-23→P1-13、FE-19→P1-8），避免与历史编号撞车。其中 SEC-22 与产品官 PR-07、FE-19 与 PR-08 是**同一条问题的两种编号**，已合并计一次，未重复计数。

---

## 3. 阻塞项清单（Go 的唯一条件）

| # | 阻塞项 | 完成标准 | 预估 |
|---|---|---|---|
| 1 | 空角标常显 + wrapper 空隙（BLK-1 + BLK-1b） | `.synth-badge[hidden]{display:none}` + `.synth-line[hidden]{display:none}`；抽屉默认 1M / hero 非 1D / 基本面 tab 四处 `getBoundingClientRect()` 为 0×0、无残留空隙，填充态尺寸不变 | 2 行 CSS |
| 2 | 数据真实性标注（BLK-3） | 指数卡去「实时」与虚构数字；`#heroChart` aria-label 去「实时」；DATABASE strip 未实现项标「演示」或删除 | 纯文案，~30 min |
| 3 | 部署配置（BLK-2） | `database_id` / `ALLOWED_ORIGIN`（精确 origin，禁 `*`）/ `ALERT_FROM` 三项落地；`RESEND_API_KEY` 走 secret；`/api/health` 与 CORS 头 curl 验证 | 30 min（依赖 Cloudflare 账号） |
| 4 | 限流并发绕过（P1-0，**条件阻断**） | 并发 20 次注册只成功 ≤5；并发 20 次错误登录第 6 个起 429；`tests/unit/auth.test.mjs` 并发用例提到阈值以上；补两条断言（并发注册 429 数 ≥15、并发登录 429 数 ≥15） | ~1 h |

> **条件升级条款**：P1-0 若本次**公开开放注册**，则升级为阻断项（P0），必须在开放前完成；若首发为邀请制/不开放注册，可按 P1 排期。安全官附加条件：**若公开开放注册**，P1-6（邮箱不验证 + 无限建号 = 任意地址发信通道）也必须在开放前解决。

---

## 4. 上线检查清单（部署前逐条勾）

**配置**
- [ ] `wrangler d1 create guanchao` → `database_id` 填入 `wrangler.toml:6`
- [ ] `ALLOWED_ORIGIN` = 精确前端 origin（不带尾斜杠、不留空、不用 `*`）
- [ ] `ALERT_FROM` = Resend 已验证域名下的发件地址
- [ ] `wrangler secret put RESEND_API_KEY`（不配则邮件静默不发，发布说明需写明）
- [ ] `wrangler d1 execute guanchao --remote --file=./backend/schema.sql`；旧库补 `migrate-002-auth.sql`
- [ ] `.dev.vars` / `.env` 未进 git（已核干净）

**响应头（前端托管侧，Worker 管不到页面）**
- [ ] `Content-Security-Policy`：`default-src 'self'; script-src 'self' 'unsafe-inline' https://push2.eastmoney.com https://push2his.eastmoney.com https://vip.stock.finance.sina.com.cn; connect-src 'self' https:; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`
- [ ] `X-Frame-Options: DENY`、`Strict-Transport-Security: max-age=31536000`

**回归**
- [ ] `node --test "tests/unit/*.test.mjs"`（32） + `node --test backend/test/alert.test.mjs`（6） + `?selftest`（36）= 74/74
- [ ] CHANGELOG 补本批条目，`APP_VERSION` / `BUILD_DATE` bump
- [ ] README 同步 `safeCloudBase` 白名单限制（否则用户按旧文档填自定义域必失败）

**部署后立即验证（硬门槛）**
- [ ] 注册 + 登录各 1 次成功；`wrangler tail` 看单次请求 `cpuTime` / `wallTime` / `outcome`，确认 **< 10 ms CPU 且 outcome=ok**。PBKDF2 100k 若超免费版限额，登录注册会直接 500（此前的测试全走 Node，碰不到这个限制）
- [ ] `curl <worker>/api/health` → `{"ok":true}`；带 `Origin` 头确认返回 `Access-Control-Allow-Origin`
- [ ] 页面 → 云朵 → 填地址 → 注册/登录 → `renderCloudTarget` 显示目标域名
- [ ] 跨设备：A 加自选/提醒 → B 登录拉到
- [ ] `wrangler tail` 观察 cron 6 轮（30 min）无 `console.error`、`mailed` 未触顶

---

## 5. 回滚预案

| 层 | 方式 | 说明 |
|---|---|---|
| Worker | `wrangler deployments list` → `wrangler rollback <deployment-id>` | 回滚后立即复验 `/api/health` |
| D1 | 本轮无需回滚 | `schema.sql` 全为 `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN`，无破坏性 DDL；`migrate-002` 新增列对旧代码兼容（旧代码不读该列） |
| 前端 | `git show <last-good-sha>:index.html` 覆盖后重新发布 | 单文件无构建产物，秒级生效 |
| 凭据 | `wrangler secret delete RESEND_API_KEY` + 轮换 Resend key | 只停邮件，不影响同步 |

**回滚触发线**：5xx 持续 > 2 min，或登录/同步任一主路径不可用 → 立即回滚。

**上线后 30 min 观察**：`/api/health` 5xx = 0；`wrangler tail` 异常日志 = 0；前端 `/api/*` 无 CORS 失败；同步往返 P95 < 2 s；`login_attempts` 无异常锁死行；cron 6 轮跑满。

---

## ✅ 行动清单

| # | 行动 | 负责方 | 紧急度 | 验收标准 |
|---|------|--------|--------|---------|
| 1 | 空角标常显 + wrapper 空隙（BLK-1 + BLK-1b）：2 条 CSS + 3 行 JS | 前端 | P0 | `.synth-badge[hidden]{display:none}` + `.synth-line[hidden]{display:none}`；`setSynthBadge` 里 `if (w.classList.contains('synth-line')) w.hidden = !text`（**不要无条件隐藏 parentElement，否则 hero 图例被一起藏掉**）。验收：抽屉默认 1M / hero 非 1D / 基本面 tab 四处空态 0×0；财务趋势 h4→图 12px、估值 h4→文字 10px（与 HEAD 一致）；hero 1M 下图例仍可见；`getComputedStyle` 断言放 `runSelfTests` 或 Playwright，**不能放 `node --test`**（无布局引擎） |
| 2 | 指数卡去「实时」与虚构数字、aria-label 去「实时」、DATABASE strip 未实现项标「演示」 | 前端 | P0 | 全页 grep「实时」只剩真实数据路径；指数卡有「静态示例」标识 |
| 3 | 落地 3 项部署配置 + `RESEND_API_KEY` secret | 发布 | P0 | `/api/health` 200 且带正确 ACAO；Resend 测试信可达 |
| 4 | 限流改「写后判」：注册与登录都在 PBKDF2 之前用 `INSERT … ON CONFLICT … RETURNING fails` 判阈；同批删掉 README 的 `*` 并让代码拒绝 `*` | 后端 | P1（条件 P0） | 并发 20 注册 ≤5 成功、并发 20 登录第 6 起 429；补断言「并发注册 429 数 ≥15」「并发登录 429 数 ≥15」；`ALLOWED_ORIGIN='*'` 被拒或仅 dev 放行 |
| 5 | `synthNote` 扩为「无 `_realKline` 即标」，hero 补 `loadRealKline` | 前端 | P1 | 导入标的 1M/1Y 出现角标；hero 切区间后角标与数据来源一致 |
| 6 | cron 单轮发信上限 ≤20；非 JSON 请求 415；`/api/state` 加最小写间隔 | 后端 | P1 | 60 用户命中时子请求 ≤50；跨站 no-cors 请求被 415 |
| 7 | 补单测：**并发限流闸门**（20 并发注册/登录断言 429 数）、`safeCloudBase` 18 例、`synthNote` 4 分支、角标 `display`、`hit` 合并 | 前端 + 后端 | P1 | 新增 ≥20 条断言，纳入基线；并发用例的 N 必须 > 阈值 5 |
| 8 | `safeCloudBase` 放宽到自定义域 + 被拒时保留 warn 文案 + 更新 README | 前端 | P1 | `https://api.mydomain.com` 可用；拒绝时提示不消失 |
| 9 | 游标轮转修两处饥饿：`LIMIT 1000`（用户）与 `codes.length=800`（代码，P1-12） | 后端 | P1 | 造 1000 个代码跑 3 轮，第 801–1000 个至少被查 1 次；第 1001 个用户能在 N 轮内被检查到 |
| 10 | 补 CHANGELOG + bump 版本 + 加 `package.json` test 脚本 | 发布 | P2 | CHANGELOG 有本批条目；`npm test` 在 Windows 直接可跑 |

---

## ⚠️ 待完善 / 已知局限

- **后端全程未部署**：所有 Worker 结论来自静态阅读 + 本地 SQLite/桩 fetch 探针，非线上行为。**PBKDF2 100k 是否超免费版 10 ms CPU 是部署后的硬门槛**——超限则登录/注册直接 500，而本地测试走 Node 永远碰不到；已在检查清单列为「部署后立即验证」第一项。
- **P1-12 严重度为主理人裁定**：安全官原定 P2（依据「需 5 用户 × 200 条提醒」），主理人按「确定性截断 + 静默功能失效 + 用户完全无感」上调为 P1，理由与证据均记录在问题表，若工程负责人认为触发概率可接受可下调。
- **云同步、邮件实发、跨浏览器、东财真实数据路径四类用例未执行**（后端未部署 / 本机 IP 被封 / 仅 Chromium 131）。上线冒烟清单里已标「无法验证」。
- **东财 `push2` 对本机 IP 仍封禁**，BL-01 无法复测；BL-05（新浪兜底覆盖率）也未在本轮复测。
- **PR-09/PR-16 的溢出与字号结论**基于 CSS 声明与内容宽度推算，非实测截图（仅 390px 全局溢出为实测）。
- **`?selftest` 36 条本身不含角标断言，且全部是纯逻辑断言，没有一条涉及 CSS 计算样式或布局尺寸**——这是本次 P0 能同时穿过 32 条单测 + 36 条页内自检的结构性原因，不只是「某个函数没测」。`node --test` 没有布局引擎，`getComputedStyle` 类断言只能放 `runSelfTests`（浏览器内）或 Playwright。
- **P1-0 的分级已达成共识（曾有分歧，已收敛）**：安全官按「P0 专指上线即故障」主张 P1，质量门神最初倾向 P0；最终统一为 **P1 首位 + 条件升级条款**——若公开开放注册则升为阻断项。两位成员均独立复现（20/20 登录穿透、20/20 注册成功），结论本身无争议。
- **「全绿」不等于「修好」**：本轮有两条判断在交叉复核中被推翻——FE-07 曾被列为「已闭环」（实际白名单放行任意 `*.workers.dev`，攻击者可收凭据）、SEC-17 曾被描述为「会重复发信」（实测 `putState` 的 `old.hit` 合并挡住了重复发信，真实后果是**静默丢失用户并发改动**）。报告已按实测修正，但这也说明：**提交信息与单成员结论都不能直接采信，必须落到可复现的探针**。
- **行窗抽样会漏掉收敛路径**：安全官承认首轮「写侧覆盖入参 hit」是从 `putState` 行窗推断的，产品官用真实 PUT 复测才推翻。凡涉及「读-改-写」的结论，必须跑真实调用链，不能只读相邻行。
- **并发用例的 N 必须大于阈值**：现有 32 条单测的并发用例 N=2/3，小于 `LOGIN_MAX_FAILS=5`，所以「74/74 全绿」与「限流有效」之间没有逻辑关系。建议把「N=20 并发断言 429」固化为回归闸门。
- **本次方法论结论（建议写进团队规范）**：凡涉及「顺序 / 并发 / 截断 / 白名单」四类问题，**静态审查 + 现有单测会系统性漏判**——它们不体现在单个函数里，而体现在调用顺序与资源上限上。必须配「攻击视角探针」（并发打点、构造超量数据、真实渲染取 computedStyle）才能发现。本轮 5 条 P0 中有 4 条属于这一类。
- **安全官与质量门神对 `safeCloudBase` 严重度判定不同**（P2 DX vs P1 可用性），本报告按「README 教用户填地址却失败」的实际影响取 P1。

---

## 📚 成员产出索引

- 产品官（product-reviewer）：本轮结论 20 条（PR-01~16 + 复核 SEC-06/07/08/17），附 3 个 `/tmp` 探针（`probe_signals.mjs` 等）与微基准结果，正文见团队消息记录。
- 安全卫士（security-officer）：STRIDE 表 + OWASP Top 10 结论表 + 6 个只读探针（真 SQLite / 桩 fetch，脚本在 `C:/tmp/`），SEC-02~05 逐条实测判定。**量化数据出处**：61 子请求（P1-3）、150 次上游（P2-4）、152ms→2.5s 外推（P2-6）、跨站 6 次锁 IP（P1-4）均由安全官的 `probe3~6` 测得。
- 质量门神（qa-lead）：测试矩阵 74/74、角标 A/B 取证（`deliverables/gstack/_baseline/qa/shot-B-hero-1M.png`、`shot-C-finSynth.png`、`shot-mobile.png`）、`verify-badges.mjs` / `verify-2..12.mjs`（含四版间距终验）、`fixed-preview.html` / `fixed2-preview.html`、18 例冒烟清单。**其独立探针为 `C:/tmp/gate-bypass.mjs`、`probe2.mjs`**（与安全官的 `probe3~6` 是两套独立实现，20/20 穿透结论互相印证）。
- 上一轮基线：`deliverables/gstack/code-audit-guanchao-2026-11-21.md`（37 条 / 3 条 P0）。

---

## 🛠 后续修复记录（2026-11-22 下午，同会话执行）

> 本节记录报告出具后的实际修复，用于区分「审计结论」与「当前代码状态」。上方各节保留审计时的原始判定，不改写。

| 条目 | 状态 | 改动 | 验证 |
|---|---|---|---|
| BLK-1 / BLK-1b 空角标常显 | ✅ 已修 | `.synth-badge[hidden]{display:none}` + `.synth-line[hidden]{display:none}`；`setSynthBadge` 同步收起 wrapper 并限定 `.synth-line` | Playwright 1440×1000：hero 1M 角标 0×0、图例「价格 MA20 MA60」仍可见、`.cc-foot` 高 45px；抽屉默认 1M 角标与 wrapper 均 0×0；基本面间距回到 **12px / 10px**；塞文案时 56×23 正常显示 |
| BLK-3 数据真实性标注 | ✅ 已修 | 指数卡 `实时`→`静态示例`，去掉「成交 1.12 万亿」「南向 +42.6 亿」「VIX 14.2」「年内 +38.6%」等虚构数字；hero aria-label、滚动条 aria-label、meta description 去「实时」；抽屉模拟标的由「实时 · 模拟」改「模拟 · 非真实」；DATABASE strip 未实现项统一标「演示」，财报改「财务趋势 4 年 · 估算」 | 截图 `final-top.png` / `final-overview.png`；DOM 文本核验 `沪深两市静态示例` |
| P1-0 限流并发绕过 | ✅ 已修（代码侧） | 合并为单条 `INSERT … ON CONFLICT … RETURNING fails, locked_until`，先自增再判阈；成功登录回退 1 次预占配额 | 20 并发注册 → **5×200 / 15×429**（users 表 5 行）；20 并发错密码 → **5×401 / 15×429**；新增 2 条并发断言 |
| P1-13 README 教 `*` | ✅ 已修 | `cors()` 对 `*` 不再回显 ACAO；README 删除「本地调试用 `*`」并说明理由；补前端地址白名单说明 | 代码静态检查；README 人工核对 |
| P1-12 cron 代码截断饥饿 | ✅ 已修 | `rotateAlertCodes()`：游标存 `cache` 表 `key='alert_cursor'`，按 offset 环形切片，每轮推进 800（不改 schema） | 新增 `SEC-22`：1000 个代码跑两轮，各 800 个且集合不同，两轮并集 **1000**；原「6000 → 20 次 fetch + warn」仍通过 |
| P1-1 非 1D 合成数据无角标 | ✅ 已修 | `synthNote`：非 1D 时「有 `_realKline` 不标，其余一律标」；真实/导入标的文案「模拟走势 · 非真实 K 线」 | Playwright 遍历 hero 1D/1M/6M/1Y 与抽屉 1M/1D/基本面，**可见空角标 = 0**；注入 live 未加载 K 线显示标注、`_realKline=true` 后隐藏；自检新增 2 条 |
| P1-3 cron 发信无预算 | ✅ 已修 | `MAX_MAILS_PER_ROUND=20`；超预算用户**整户顺延**（不写 hit、不落库），下轮重新判定 | 新增 `SEC-21`：25 用户全命中 → mailed 20 / deferred 5 / 实际发信 20 封 / 只落库 20 条 |
| P1-4 跨站简单请求 | ✅ 已修 | `/api/register`、`/api/login`、`/api/state` 写操作强制 `application/json`，否则 415 | 新增 `SEC-20b`：`text/plain` 打注册/登录均 415 |
| P1-2 智策评分口径 | ✅ 已修（文案） | 文案改「演示评分」，`title` 说明基于模拟走势与估算字段 | 页面实测 `#sigMeta` = 「共 5 条建议 · 演示评分 · 覆盖 沪深 / 美股 / 港股」，0 错误 |
| P1-9 CHANGELOG / 版本 | ✅ 已补 | `APP_VERSION` 1.7.0→**1.7.1**、`BUILD_DATE`→2026-11-22；CHANGELOG 新增 1.7.1 条目（含验证方式） | — |
| BLK-2 部署配置 | ⛔ 未完成（需账号） | 三个占位符仍需真实 Cloudflare 资源：`database_id`、`ALLOWED_ORIGIN`、`ALERT_FROM` | 无法在本地完成 |

**回归结果（修复后）**

| 用例集 | 结果 |
|---|---|
| `node --test "tests/unit/*.test.mjs"` | **37/37 通过**（原 32 + 2 条并发闸门 + 1 条 cron 轮转 + 1 条发信预算 + 1 条 415） |
| `node --test backend/test/alert.test.mjs` | **6/6 通过** |
| 页内 `?selftest` | **38/38 通过**（原 36 + 2 条角标口径），0 页面错误 |
| 内联脚本语法（4 段 + 拼接后） | **5/5 通过** |
| 浏览器渲染（1440×1000） | 0 pageerror；角标空态/填充态/图例/间距全部符合预期 |

**仍未处理（按报告优先级）**：P1-5（未验证邮箱）、P1-6（PBKDF2 强度）、P1-8（safeCloudBase 白名单过窄）、P1-10（同步无取消）、P1-11 剩余覆盖缺口、P2 系列。已提交 `7918fa6`、`c794a57` 与本轮提交。

---

> 本报告由软件工坊 AI 协作生成，关键决策请由工程负责人复核。所有 P0 结论均有实测证据或代码行号支撑；未执行项已明确标注。
