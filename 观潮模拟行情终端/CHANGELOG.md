# CHANGELOG

说明:2026-11-21 起本环境已可执行代码并提交 git,记录改为以 commit 为准。"验证"一栏只写实际做过的事。

## 未发布 · 阶段四第 2 轮(2026-11-23,UX 第 3 期:数据可读性,3d0e17c)

探针 `_stage3/verify-readable.js`(8/8);selftest 38→40。

### fix(readability): 四个数据可信问题(3d0e17c)
- **Q10 财务柱**:每组柱顶标营收/净利金额(`finNum` 兼容万亿/百亿/小体量),颜色与图例对应;柱区 132→150px。
- **Q19 诊断三价位自洽**:进场区间按评分分档——≥82 覆盖现价分批建仓 / 68–81 现价为区间上沿逢低 / 55–67 整体低于现价(等待回踩不再自相矛盾)/ <55 观望不设进场位;失效价 = min(MA60 结构锚,进场下沿 −5%),地板现价 −15%,**失效价距进场下沿恒 ≥5%**(原最小 0.9%);新增「现价对照」行。selftest 全市场扫不变量。
- **Q17 今日盈亏口径**:= 持仓当日波动 + 当日已实现(含费用)。`account` 增 `dayStamp/dayRealized`,`execSell` 落账,跨日懒重置,旧备份无字段自动迁移;清仓砍仓日不再显示 +¥0 而累计收益 −¥26。标签加 title 说明口径。
- **Q25 金额横加**:交易摘要(委托金额/费用/可用资金)统一两位小数,「委托金额+费用 = 现金减少额」精确成立(原 money0 各自取整横加差 1 元)。
- 探针教训:买卖往返后的现金差 = 全部费用(162.45),不能当买入单腿现金流断言。
- 回归:round2/touch/acct/py 全 PASS;finchart/diagplan 截图人工复核。

## 未发布 · 阶段四第 1 轮(2026-11-23,UX 第 2 期:资产常显 / 首屏解耦 / 拼音检索)

三个 commit(3dbb1fc / 59f789a / b9b9b72),探针 `_stage3/verify-{acct,py}.js`。

### feat(mobile): 移动端资产常显(59f789a,R6 第 1 步)
- `#acctChip` ≤560 由 `display:none` 改为「总资产」单行(约 95px):图标/SIM 标签/涨跌幅全藏,只留 12.5px 数字;561–760 沿用紧凑 chip。
- 拿掉两处 `display:none!important` 后 375 导航空间不够(约 367px > 335px 可用),价格提醒入口按设置/主题的 `.nav-m` 模式移入移动菜单,`data-mact="alerts"` 接线。
- 验证:verify-acct 7/7——375/414 chip 可见、`¥1,000,000` 可见、navRight 不溢出、菜单提醒入口可开抽屉。

### perf(boot): 首屏解耦(3dbb1fc,R9)
- boot 原是 400–800ms 单个同步长任务,FCP(676–1068ms)晚于 DCL(581ms)就是被它挡住的。
- 拆两阶段:首帧前只做便宜接线(inert/acctChip/wireEvents/时钟/主题);万级宇宙构建 + 折叠线下渲染 + initHero + selftest 挪进首帧后的 `setTimeout(0)`。浏览器在两阶段间获得绘制机会。
- **selftest 依赖宇宙构建,随迁到延迟块内**(顺序不能错)。
- 实测(probe-vitals,3 次/视口):mobile FCP 516–944 → **528–624ms**,desktop 常态 600–1068 → **500–552ms**(desktop run1 1356 为冷启动噪声);CLS 0 → 0.021(远低于 0.1)。

### feat(search): 拼音首字母检索(b9b9b72,R4)
- 不引拼音库:`Intl.Collator('zh-CN-u-co-pinyin')` 对 22 个 GB 边界字(八嚓咑妸发旮…)定位首字母;每标的懒计算缓存 `_py`。
- 统一 `stockMatch()`(代码/名称/英文/拼音首字母),替换 palette、终端、板块抽屉三处重复表达式。palette 占位符本就承诺「拼音首字母」,此次兑现。
- 验证:verify-py 7/7——gzmt→贵州茅台、ndsd→宁德时代、混合串 hs300、中文/代码回归。**探针教训**:`window.BY_CODE` 取不到(top-level const 不挂 window,全局词法环境才可达);`textContent.slice(0,30)` 会被行首空白坑,用 innerText+压缩空白。

## 未发布 · 阶段三第四轮(2026-11-23,R7 信任文案销项,cc8929b)

UX 第 1 期路线图最后一项。三处不实宣称改为如实标注:

- **「沪深交易中」写死** → `tickMktStatus()` 按 A 股真实时段计算(周一至周五 09:30–11:30 / 13:00–15:00,Asia/Shanghai,不含节假日),随秒级时钟刷新;收盘后绿点停跳(`.dot-off` 转灰)。
- **终端「行情延迟 18–30ms」**原为 `Math.round(18+random*12)` 编造的随机数 → 改为按数据来源如实标注:`模拟行情 · 本地生成` / `快照行情 · 非实时流`。
- **hero「68.4% 信号方向准确率」**补「(演示)」标注。

验证:`verify-r7.js` 5/5 PASS——实时时段显示「交易中」;假日期驱动(周六全天/周三上午)分别判定「已收盘/交易中」且灰点状态正确;termMeta 无编造延迟;触摸目标回归 6/6、selftest 38/38。探针 `_stage3/verify-r7.js`。

至此 UX 报告第 1 期(止血+可信)五项全部完成:R1 过渡提速 ✓ R2 小数位 ✓ R3 hero 可点 ✓ R5 提醒回跳 ✓ R7 信任文案 ✓。SUS 预估 65 → 76–82 区间(报告 §13 推算)。

## 未发布 · 阶段三第三轮(2026-11-23,触摸目标 120 → 0)

375/414 实测 120 个交互目标 <48px(a207560)。**定标**:独立图标按钮 48×48;密集行内控件(标签页/筛选片/工具条)44×44——Apple HIG 44pt,WCAG 2.5.8 相邻留白豁免。此后 QA 口径从「below48」改为「below44」,44–48 区间的 83 个行内控件视为达标。

### 修法
- 图标类:`.icon-btn`/`.dh-star` 提到 48×48;`.tk-star`(自选行星标 ×20)44×44。
- 文本链接:`.brand`/`.foot-col a`/`.link-arrow`/`.pf-reset` 补垂直 padding(链接没法加宽,加高到 ≥44)。
- 控件类:`.seg`/`.preset-row`/`.cc-range`/`.dh-ranges`/`.ind-toggle`/`.cmp-ranges`/`.term-btn`/`.kbd-btn`/`.data-import`/`.set-btn`/`.set-select`/`.mini-select`/`.btn-sync`/`.pager` 与 15 个表单控件统一 44px 高;`.mini-select` 箭头 `background-position` 随高度重算;`.pager` 允许换行(7 个 44px 按钮 375 下单行放不下)。
- 全部装在 `@media (max-width:760px)` 且置于主样式块**末尾**,桌面密集布局零改动。

### 踩坑与验证
- **关闭态弹窗 scale(.98)**:rect 缩 2%,44px 量成 43.1,凭空多出假报。探针必须过滤 `pointer-events:none`(关闭弹窗),或只在弹窗打开时量。
- 行高 21.875px + padding 11px = 43.875,舍入显示 44 但原始值 <44——临界值要留 1px 余量。
- 验证:`verify-touch.js` 6/6 PASS(375/414 below44=0、两者无横向溢出、`?selftest` 38/38、1440 无回归);终端工具条/表尾/hero 卡三张移动端截图人工复核无破版。
- 探针存于 `_stage3/verify-touch.js`、截图 `layout/touch-375-*.png`。

## 未发布 · 阶段三第二轮(2026-11-23,并行评审返修落地)

三路并行评审(QA 矩阵 / UX 旅程 / 设计审计)报告落盘后的集中返修,共 5 个 commit。
报告存于 `deliverables/gstack/_stage{3,4,5}/`;修复验证探针 `_stage3/verify-round2.js`,7/7 PASS、`?selftest` 38/38。

### fix(theme): 补 5 个未定义令牌,主操作按钮恢复填充(37445e3)
- `var(--brand)`/`var(--brand-ink)` 被引用 15 处但从未定义,「添加提醒」「加入」「同步」三个主按钮渲染成纯文本。用 `--ink`/`--bg` 派生,暗色正白底黑字、亮色自动反转。

### fix(a11y): 亮色主题 5 个令牌按 AA 重标定,对比度失败 368 → 0(4a92da6)
- `--up/--down/--accent/--faint/--mute` 仅调暗一档,色相与「涨红跌绿」语义不变(改前实测 4.48/4.10/4.37/4.39/5.4)。dark 保持 0 处不达标。

### fix(fmt): 涨跌额小数位正负不对称(b25ad59)
- 根因:`fmt.px()` 分支 `v < 1` 未取绝对值,任何负数恒真落入 4 位小数,`-12345.6` 印成 `-12,345.6000` 而正数是 `+12,346`;右对齐数字列小数点无法对齐。
- 方案:先取 `Math.abs` 再分档(修后 `-20.6393 → -20.64`,与 `20.6393` 同宽)。

### fix(ui): 设计审计 §C 三项落地(4f3efad)
- **C5 浮层避让**:`.signal-chip` 原 `left:-26px;bottom:64px`,向左溢出卡片 25px 且压住 X 轴刻度带 54px(09:30/10:30 被遮)。改桌面 `left:14px;bottom:88px`(距画布下沿 32px),≤1140px 钉卡片顶部;≤760 断点只保留字号/内边距压缩。
- **C6 抽屉提速**:四个 `.drawer` 类面板 `transform .6s → .24s`。transitionend 实测 652ms → 273ms(含内容渲染),内容就绪本就只要 4–38ms,原 95% 是纯等待。
- **C3 移动菜单浮层化**:展开菜单原与底面同色(`--bg-2`)无浮层感,改 `var(--panel)` + `--line-2` 边框 + 投影。注意:规则在第二个 `<style>` 块(约 5213 行),追加到主块会被源序覆盖。

### feat(ux): hero 可点 + 提醒回跳(049a35f)
- **R3**:hero 图表卡股票名/代码区加 `role=button` + 键盘支持,点击直达个股抽屉,悬停下划线提示。
- **R5**:提醒行加 `data-code`,点击关闭提醒面板并打开对应个股抽屉,补悬停反馈。原先提醒触发后是死胡同——只能删,不能跳。
- 验证:浮层溢出 25→0px、距轴带 32px;hero 点击/回车均开抽屉;提醒行点击面板关、抽屉开(贵州茅台);C3 背景实测 `rgb(255,255,255)` + 投影生效。

## 未发布 · 阶段三首轮(2026-11-23,多端页面矩阵的布局缺陷)

阶段三开局扫 7 档视口(1920/1440/1366/1024/768/414/375)实测到的三条布局缺陷。
`index.html` 7,175 → 7,207 行(+32),均为 CSS 与移动端菜单入口,无业务逻辑改动。

### fix(nav): 1141–1469px 导航项逐字换行(0cdeced)
- 根因:`.nav-links` 未声明 `flex:none`、`<a>` 无 `white-space:nowrap`;`.nav-right` 子元素宽度固定不让位,压缩全落在导航项上,中文按字断行,`<a>` 高 40 → 63px。搜索按钮「搜索股票」同批变两行。触发区间正好覆盖 1440 与 1366。
- 方案:`flex:none` + `nowrap`;`.kbd-btn` 同步 `nowrap;flex:none`;让位改由 `.mkt-status` 承担,断点 1100 → 1520px(它与首屏「数据流在线」语义重复,是唯一可无损让位的元素)。
- 验证:12 档宽度实测,修复后 1181–1512 全部 `linksW == linksScrollW == 345`、高恒 40px;七档视口横向溢出 0。

### fix(nav): 移动端导航溢出裁切,图标提到 48×48(6d5290a)
- 根因:≤760 时 5 个 34px 图标 + 18px 间隙 = 228px,`.wrap` 在 375 下内容宽仅 320px、`.brand` 占 106px,`#mobileMenu` 的右边界实测 435(375 视口),被裁 60px;414 下超 21px。34×34 亦低于 48px 触摸标准。
- 方案:`.nav .icon-btn` 在 ≤760 提到 48×48(作用域限定 `.nav`,不动抽屉/弹窗关闭按钮);≤560 隐藏 `#settingsBtn`/`#themeToggle`,两个入口以 `.nav-m` 移入移动菜单面板(沿用 `.nav-pf` 的「桌面隐藏、`.is-open` 显示」模式),`wireEvents` 内绑定 `openSettings()` / `setTheme()`。
- 验证:375 下 `.nav-right` 右边界 370 → 340,菜单 48×48 完整可见;展开菜单 8 项、行高 51px;点「明暗主题」`data-theme` 由 light 变 dark 且面板收起;点「设置」弹窗打开,宽 360px 无溢出。

### fix(term): 行情终端在 ≤414px 撑破容器,整页横向溢出 28px(c6ff43c)
- 根因:`@media (max-width:1180px)` 把 `.term-layout` 改单列 `1fr`,grid 项默认 `min-width:auto` = min-content;`.term-search{flex:1 1 240px}` 内 `input{width:100%}` 也缺 `min-width:0`,输入框 min-content(约 316px)一路顶上,链条无一处允许收缩。375 下 `.term` 383px、`#termSearch` 316px,整页溢出 28px。
- 方案:单列改 `minmax(0,1fr)`;`.term-search` 与其 `input` 补 `min-width:0`。两处缺一不可。
- 验证:375 下 `.term` 383 → 320,横向溢出 28 → 0;414 同样归零;七档视口溢出量均为 -15(仅滚动条)。

### 阶段三同时确认的基线
- `?selftest` **38/38** 通过(内置模拟全市场),0 console error、0 pageerror。
- 横向滚动:7 档视口全部 0(修复前 375 为 28px)。
- 仍不达标:375/414 下触摸目标 <48px 的交互元素 **120 个**(本次只修了导航图标),清单待质量门神补齐。

### 尚未完成(→ 已于第二轮解决,见上)
- ~~暗色模式对比度~~:4a92da6 已修,368 → 0。
- 抽屉/弹窗关闭按钮、`.seg button`、`.term-btn`、分页按钮仍为 34px 上下(触摸目标 120 个待修,未动)。

## 1.8.0(2026-11-22,摘除云同步模块)

取消公网部署后,把前端里整套云同步一并摘掉。`index.html` 7,617 → 7,175 行(-442),390,155 → 369,793 字节(-20.4KB)。

### 删除范围
- **JS 传输层**:`CLOUD_KEY`、`cloud` 状态对象、`safeCloudBase` / `CLOUD_HOST_ALLOW`、`loadCloud` / `saveCloud` / `getCloudBase`、`cloudRequest`、`buildCloudState`、`applyCloudState`、`cloudPush` / `cloudPull` / `scheduleCloudPush`、`cloudAuth`、`renderCloudUI` / `renderCloudTarget` / `setCloudStatus`、`CLOUD_STATE_MAX`。共约 240 行,含 13 处 `scheduleCloudPush()` 调用点。
- **HTML**:`<template id="legacyCloudTpl">`(42 行遗留死模板,即此前安全审计误报的"16 个重复 ID"来源)、设置弹窗内的云同步整段(28 行)、导航 `账户登录` 链接与 `#userBtn` 账户按钮。
- **CSS**:`.cloud-label/-input/-grid/-account/-auto/-field/-row/-user/-check/-status`、`.icon-btn.is-cloud`、`.nav-links a.nav-login`、`#userBtn` 断点。
- **数据源分支**:`syncEastmoney` 里的 Worker 快照首选分支、`#syncStart` 里的云端分片拉取分支、`SOURCE_LABEL.worker`。
- **备份导入/导出**:导出不再写 `cloud` 字段;导入不再读取并校验 `d.cloud.base`(原 FE-07 防护随功能下线一并移除)。
- **死代码**:`reconcileFavGroups()` 仅被 `applyCloudState` 调用,一并删除。

### 保留与重命名
- 设置弹窗保留(`#settingsModal`),含「本机偏好」「备份与重置」两段;`.cloud-scrim/-modal/-head/-body/-sec/-actions/-about` → `.settings-*`,`#cloudModal/#cloudScrim/#cloudClose/#cloudVersion/#cloudBtn` → `#settings*`,`openCloudModal/closeCloudModal` → `openSettings/closeSettings`。
- `sanitizeCloudState` → `sanitizeState`:备份导入仍在用,不是云专属。
- 导航云朵图标换成齿轮,`aria-label` 改为「设置」。
- 版本号 1.7.1 → 1.8.0;`#settingsVersion`、`#aboutVersion`、`#aboutBuild`、`#footVersion` 改为读 `APP_VERSION` / `BUILD_DATE`(原先页脚与关于块硬编码 `v1.7.0`、`BUILD 2026-11-19`,已过期)。

### 验证
- 四段 `<script>` 逐个 `node --check` 全部通过。
- Playwright 1440×1000:`legacyCloudTpl` 0 个、含 `cloud` 的 id/class 各 0 个、`#userBtn` 与 `[data-opencloud]` 各 0 个、活动文档重复 ID 0 个。
- 设置弹窗:560×581 正常打开,标题「设置」,两段小节、8 个按钮,`Esc` 可关,遮罩与 `inert` 同步正确。
- 内联自检 **38/38 通过**;页面 0 console error、0 pageerror。
- 交互冒烟:开抽屉 / 收藏 / 加提醒 / 开模拟账户 / 导出 均无新报错。
- 角标回归:抽屉与 hero 在模拟标的上显示「模拟数据」56×23;基本面/估值角标保持 `hidden` 且 0×0;hero `.cc-foot` 图例「价格 MA20 MA60」完整。

## 未发布 · 取消公网部署(2026-11-22,commit 577cef2)

决定不做公网部署,移除部署相关文件:

- 删除 `backend/`(`worker.js`、`wrangler.toml`、`schema.sql`、`migrate-002-auth.sql`、`README.md`、`test/`)与 `tests/`(`auth`/`state`/`alerts` 单测 + D1 替身),共 10 个文件。
- 删除前核查:仓库无 git remote,从未 push;Cloudflare 未登录成功(`whoami` = not authenticated),未执行过任何 `deploy`。**代码未离开本机**。
- 备份:`_backup/backend-tests-2026-11-22.tar.gz`;git 提交 `0c25cad` 内完整保留。恢复:`git checkout 0c25cad -- backend tests`。
- `index.html` 未改动,云同步入口保留但无服务端可连。`CLOUD_HOST_ALLOW` 与 `safeCloudBase()` 仍在第 6884 行起。

## 1.7.1(2026-11-22,上线前全检的阻塞项修复)

全检报告:`deliverables/gstack/pre-launch-check-guanchao-2026-11-22.md`(36 条,3 组阻塞 + 1 条条件阻断)。

### fix(ui): 空角标常显 + wrapper 留白
- 根因:`.synth-badge{display:inline-flex}` 是作者样式,压过 UA 的 `[hidden]{display:none}`,导致 `el.hidden` 只改语义、视觉上仍渲染一个 16×6 的空琥珀色胶囊。抽屉默认区间是 1M,所以**每次打开详情页必现**;hero 切非 1D、内置标的进基本面 tab 同样。
- 方案:补 `.synth-badge[hidden]{display:none}` 与 `.synth-line[hidden]{display:none}`;`setSynthBadge()` 同步收起 wrapper,但**限定 `parentElement.classList.contains('synth-line')`**——hero 的父元素是 `.cc-foot`,无条件隐藏会把价格/MA20/MA60 图例一起藏掉。
- 验证:Playwright 1440×1000 实测,hero 1M 角标 0×0、图例「价格 MA20 MA60」仍可见、`.cc-foot` 高 45px;抽屉 1M 角标与 wrapper 均 0×0;基本面两处间距回到 HEAD 的 12px / 10px;手动塞文案时角标 56×23 正常显示;0 页面错误。

### fix(copy): 数据真实性标注补完
- 指数卡 `实时` → `静态示例`,并去掉「成交 1.12 万亿」「南向 +42.6 亿」「VIX 14.2」「年内 +38.6%」等虚构数字,改为市场描述;区块说明补「指数卡为静态示例,非实时行情」。
- hero `aria-label` 去掉「实时」;滚动条 aria-label、meta description 同步。
- 抽屉时间标签:模拟标的由「实时 · 模拟」改为「模拟 · 非真实」。
- DATABASE strip:未实现能力(股东持仓/龙虎榜/北向/期权链/链上地址/p99)统一标「演示」;「财报 8 年 · 3,120 家」改为「财务趋势 4 年 · 估算」。

### fix(auth): 限流改「先写后判」,并发不再穿透
- 根因:`ipGate()` 先 SELECT 判锁、再 UPSERT 计数,并发请求全部读到 `locked_until=0` 而放行。实测旧实现:20 并发注册 20/20 成功(真建 20 行)、20 并发错密码登录 20/20 返 401。
- 方案:合并为单条 `INSERT … ON CONFLICT … RETURNING fails, locked_until`,先自增拿新值再判阈;阈值语义为「第 5 次仍放行、第 6 次起 429」。登录成功回退 1 次预占配额(不清零),避免正常用户被自己锁死。
- 验证:20 并发注册 → 5×200 / 15×429,users 表 5 行;20 并发错密码 → 5×401 / 15×429。新增 2 条并发断言,单测 37/37、后端提醒 6/6 全绿。

### fix(cors): 拒绝 `ALLOWED_ORIGIN='*'`
- `cors()` 对 `*` 不再回显 ACAO(配错时默认拒绝);README 删掉「本地调试用 `*`」并说明理由。
- 同步补充 README:前端只接受 `https` + 同源/`*.workers.dev`/localhost,自定义域名需加白名单。

### fix(cron): 代码截断改为按轮次轮转,不再永久饿死尾部
- 根因:`MAX_ALERT_CODES=800` 是全局共享配额,`codes.length = 800` 按插入序做确定性截断。造 1000 个代码跑三轮,每轮查的都是同一批 800 个,第 801–1000 个一次都没查过。5 个账号 × 200 条垃圾代码即可占满配额,让全站真实提醒永久静默且不可自愈。
- 方案:游标存 `cache` 表 `key='alert_cursor'`(不改 schema),按 `offset` 做环形切片;每轮推进 800,保证每个代码在 `ceil(N/800)` 轮内必被查到。
- 验证:新增 `SEC-22` 用例——1000 个代码跑两轮,第一轮/第二轮各 800 个且集合不同,两轮并集 = 1000;原有「6000 代码 → 20 次 fetch + warn」仍通过。

### fix(ui): 非 1D 区间的合成走势同样标注
- 根因:`synthNote` 只对 `1D` 返回角标,而抽屉默认区间是 `1M`、`loadRealKline` 只在 `s.live` 内调用 → 导入标的的 1M–5Y 全程合成且无任何标注。
- 方案:非 1D 时「已加载真实 K 线(`_realKline`)不标,其余一律标」;真实/导入标的文案为「模拟走势 · 非真实 K 线」,内置模拟为「模拟数据」。
- 验证:Playwright 遍历 hero 1D/1M/6M/1Y 与抽屉 1M/1D/基本面,**可见空角标数 = 0**;注入 live 标的未加载 K 线 → 显示「模拟走势 · 非真实 K 线」,`_realKline=true` 后隐藏。页内自检新增 2 条(共 **38/38**)。

### fix(cron): 发信加单轮预算,超出整户顺延
- 根因:`MAX_ALERT_CODES` 只管行情查询,发信每命中 1 个用户就 1 次 fetch、无上限。实测 60 用户命中 = 61 次子请求,超免费版 50 次后本轮中断,第 51 名之后静默不发。
- 方案:新增 `MAX_MAILS_PER_ROUND=20`;命中但超预算的用户**整户顺延**——不写 `hit`、不落库,下一轮重新判定。若先写 hit 再发信,超预算就等于静默吞掉这条提醒。
- 验证:新增 `SEC-21`——25 个用户全部命中,`mailed=20`、`deferred=5`、实际发信 20 封、只落库 20 条;顺延用户未被写 hit。

### fix(auth): 强制 JSON Content-Type,阻断跨站简单请求
- 根因:不校验 `Content-Type` 时,攻击页面可用 `fetch(mode:'no-cors', Content-Type:'text/plain')` 免预检打 `/api/login`,拿受害者 IP 消耗登录配额(实测 6 次即可锁死)。
- 方案:`/api/register`、`/api/login`、`/api/state` 写操作要求 `application/json`,否则 415。跨站简单请求无法携带该类型,必须先过预检,而预检会被 `ALLOWED_ORIGIN` 拒绝。
- 验证:新增 `SEC-20b`——`text/plain` 打注册/登录均返回 415;现有 37 条用例全绿。

### fix(copy): 智策明确标注「演示评分」
- 根因:评分中「资金/基本面」对未加载真实 K 线的标的是估算字段,120 只标的这两项完全相同,分数实际只落在 30~70,却写「按模型评分排序」。
- 方案:文案改为「演示评分」,`title` 说明「基于模拟走势与估算字段,仅用于展示排序方式,不构成投资建议」。

### 尚未完成(需账号或后续迭代)
- `wrangler.toml` 的 `database_id` / `ALLOWED_ORIGIN` / `ALERT_FROM` 仍为占位符,需用真实 Cloudflare 资源填写。
- 限流项为「条件阻断」:若公开开放注册,必须在开放前修完(本次已修);邮箱验证(P1-6)仍未做。
- P1-5(邮箱验证)、P1-6(PBKDF2 强度)、P1-8(safeCloudBase 白名单过窄)等见报告。

---

## 阶段三 · 第一轮(2026-11-21,阶段一审计后的 P0 修复)

阶段一审计报告:`deliverables/gstack/code-audit-guanchao-2026-11-21.md`(37 条问题,3 条 P0)。

### fix(alert): 百分比提醒按涨跌幅判定
- 根因:`worker.js` cron 用二元分支 `a.dir === 'above' ? price >= a.price : price <= a.price`,前端新增的 `pct_up` / `pct_down` 全部落进 else,拿股价(元)比百分比阈值。高价股永不触发,低价股立即误发,`hit` 写回后不可逆。
- 方案:`alertHit()` 显式穷举四方向;行情抓取补存 `f3` 涨跌幅;`alertLine()` 按方向生成文案;未知方向一律不触发。
- 验证:`node --test backend/test/alert.test.mjs` 6/6 通过(高价股 6% 涨触发、3 元股涨 2% 不触发、NaN 不触发、未知方向不触发、文案逐字比对)。**未部署。**

### fix(market): 真实快照不再被随机漂移
- 根因:`liveTick()` 的可漂移池只排除了加密标的,`s.live` / `s.imported` 也在池内;hero 走马灯对固定代码 `300750` 无条件漂移。界面标签却写「实时 · 东方财富」。
- 方案:新增 `isSimulatable()`,两处漂移统一走该判定。
- 验证:Playwright + 本机 Edge,标记 3000 只为 live 后连续 tick 200 次,修复前必被改写(首次即抓到 300750 从 258.55 漂到 261.77),修复后 0 只被改写,同期模拟标的仍有 27 只正常漂移。

### fix(sync): 东财 clist 被重置时走新浪兜底
- 根因(实测):`push2.eastmoney.com/api/qt/clist/get` 在 push2 / 82.push2 / 7.push2 / push2delay / push2his 五个主机上全部连接中断,同主机 `ulist.np` 与 `push2his` 的 kline 均返回 200 —— 端点级重置,与参数无关。
- 方案:三级数据源(Worker 快照 → 东财 clist → 新浪 `Market_Center`);新浪 `num=100` 缺 CORS 头故取 `num=80`;该接口对浏览器约 40% 随机失败,故按页重试 3 次、失败跳过、末尾补一轮;快照持久化 `source`,标签按真实来源显示,缺页时提示「同步完成(部分) · 缺失 N 页」。
- 验证:端到端点击「同步真实 A 股」两次,分别 4,378 只 / 3,898 只,标签为「数据源:新浪财经」,缺失 15 / 21 页如实显示;重载后标签不变。

### chore(repo): 恢复 .gitignore 并忽略评估产物
- 上一轮结束时 `.gitignore` 在工作区被删除,`deliverables/**/node_modules` 数千文件涌入 `git status`。已从 HEAD 恢复并追加 `deliverables/`。

### 回归
- `?selftest` 36/36:内置模拟全市场与注入的 live 快照各跑一次,均 0 FAIL,无页面 JS 错误。

### 尚未完成
- 三条 P0 中 BL-01 只做到"可用"而非"完整":新浪兜底受随机失败影响,缺页 15-21 页(约 20%),完整数据仍依赖 Worker 服务端抓取或东财端点恢复。
- 其余 P1/P2/P3(34 条)未动,清单见阶段一报告。
- PBKDF2 100k 是否超免费版 10ms CPU 仍需部署后实测。

---

## 历史记录(阶段一审计之前,保留)

### 自检结果(旧)

| 时间 | 环境 | 数据 | 结果 |
| --- | --- | --- | --- |
| 修复前(基线) | 用户本机浏览器,`?selftest` | 已缓存的东方财富真实 A 股快照(推断,见下) | 27/34 通过 |
| 修复后 | Cowork Artifact 预览,临时强制打开面板 | 内置模拟全市场(预览里没有本地缓存) | 36/36 通过 |

基线 FAIL 的 7 条:rowHTML 转义、renderSmartChips 转义、原型键防护、交易撮合、智能选股解析、百分比提醒、自选分组。

推断依据:基线里「代码唯一」PASS、「交易撮合」FAIL。内置数据下前者会 FAIL(见下方 fix(数据)),后者会 PASS;真实 A 股快照里没有 NVDA,正好相反。

**尚未取得:** 修复后在用户本机真实快照下的结果。

---

## 阶段二 · 第二轮

### fix(安全): 渲染层统一转义
- 根因:`rowHTML`、`renderSmartChips` 以及走马灯、涨跌榜、板块、侧栏、板块详情、持仓、提醒、对比、标签页、标签、基本面、诊断、智策等渲染函数,把名称、代码、行业、概念直接拼进 `innerHTML`。CSV / 东方财富数据在入口已剔除 `<>&"'`,所以这里属于纵深防御;但智能选股的标签来自用户输入,原来就能注入。
- 方案:以上位置全部经过 `escapeHTML()`。
- 验证:rowHTML、smartChips 两条用例 PASS(预览环境)。

### fix(安全): 代码索引不再命中原型属性
- 根因:`BY_CODE` 由 `Object.fromEntries` 生成,`BY_CODE['constructor']` 返回 `Object` 函数。在提醒或对比框输入 `constructor` 会被当作有效标的,随后读 `.last` 出错。
- 方案:新增 `indexByCode()`,用 `Object.create(null)` 建索引,5 处赋值统一改用它。
- 验证:原型键防护用例 PASS,新增断言 `findStock('constructor') === null`。

### fix(安全): 备份导入走与云端相同的清洗
- 根因:`importAllData` 把备份里的 account / alerts / compare 原样写进 localStorage,刷新后在持仓与成交列表里渲染。
- 方案:先过 `sanitizeCloudState`,主题只接受 `light` / `dark`。

### fix(云同步): 云端按钮事件重复绑定
- 根因:`wireEvents` 里云同步按钮绑定了两遍。点一次「登录」会并发发出两次登录请求,两次都计入新加的登录限流;点「注册」时第二次必然报「已注册」。
- 方案:删掉第一组绑定,保留第二组,Worker 地址仍去掉末尾斜杠。
- 同时去掉提醒新增 / 删除、星标、买入、卖出里重复的 `scheduleCloudPush()`。上一轮 CHANGELOG 写了已去掉,实际只改了表格星标一处。

### fix(数据): 内置全市场有 2 个重复代码
- 根因:随机生成的美股代码没有避开后面追加的数字资产代码,`代码唯一` 在内置数据下 FAIL。
- 方案:生成完成后删掉与数字资产撞名的模拟美股(10,668 → 10,666 只),其余标的的代码、名称不变。
- 验证:预览环境 `代码唯一` PASS。

### fix(智能选股): 行业词匹配所有同类板块
- 根因:`银行` 只取第一个包含该词的行业。真实快照的行业名带后缀(如「股份制银行Ⅱ」「城商行Ⅱ」),只会命中其中一个。
- 方案:有完全同名的行业就只用它;没有时匹配所有包含该词的行业。概念、细分行业同理。

### feat(提醒): 百分比提醒
- 新增条件「涨幅 ≥ %」「跌幅 ≥ %」(`pct_up` / `pct_down`),比较当日涨跌幅,阈值为 0–100 的正数。
- `alertHit()` 统一判定;本地加载、云端清洗、备份导入都接受新方向,百分比阈值超过 100 会被丢弃。
- **待确认:** 后端 `worker.js` 若在服务端检查提醒并发邮件,可能只认识 `above` / `below`。本轮没拿到 worker.js,没有核对。部署前需要确认它会忽略未知方向,而不是把它当作 `below`。

### feat(自选): 自选分组
- 数据:`favGroups = [{ name, codes }]` 是唯一数据源,`isFav` 由它派生。默认分组「默认」不可删除;最多 20 个分组,名称 12 字以内并剔除标签字符。
- 旧数据:没有分组数据时,把原来的扁平自选整体迁入「默认」。扁平列表 `guanchao-favs` 继续写入,兼容旧版本与导出。
- 切换真实 / 导入 / 内置行情不再丢自选:分组保留当前全市场里不存在的代码。
- 界面:终端选中「自选」后显示分组行(切换、新建、两次点击删除);个股详情显示分组标签,点击加入 / 移出;星标在分组视图下加入当前分组,否则加入「默认」。导出自选增加「分组」列。
- 云同步:上传时附带 `favGroups`;拉取时有分组就用分组,只有扁平列表时保留本地分组结构做对账。

### refactor(无障碍): 通用 trapFocus
- 原来只有个股详情和模拟账户会锁定 Tab 焦点。现在按层级找到最上层打开的对话框(搜索、同步、设置、对比、提醒、板块、账户、详情),焦点只在其中循环。

### chore: 移除 REVIEW_* 调试钩子
- 删除 19 个 `REVIEW_*` 常量和 boot 里对应的分支,包括会往空账户塞演示持仓的 `REVIEW_SEED`。
- `?selftest` 改名为 `SELFTEST_ON`,上一轮遗留的 `|| true /*TEMP-BASELINE*/` 已去掉,交付文件不会自动弹面板。

### test: 自检用例
- 新增 `check(条件, 说明)`:失败时把具体哪一步、实际值显示在面板上。
- 交易撮合、智能选股两条改为从当前全市场取标的和行业,内置与真实快照都能跑;交易撮合增加加仓均价、扣款金额断言。
- 自选分组用例改用临时组名 `__自检组`,并断言重名拦截。
- 新增 2 条:百分比提醒阈值清洗、分组名与代码清洗。共 36 条。
- 自检面板背景改用 `--panel`,深色主题下不再是白底浅字。

---

## 阶段二 · 第一轮(上一轮记录,保留)

- fix(安全): 调色板搜索无结果提示 XSS(P1 #1)— 新增 `escapeHTML()`。
- fix(安全): 外部数据入口清洗(P1 #2)— 新增 `sanitizeCloudState`。
- fix(后端): 登录限流(P1 #3)— 按邮箱和 IP,15 分钟失败 5 次锁定 15 分钟,返回 429。**未部署、未运行。**
- fix(后端): PBKDF2 迭代数(P1 #4)— 100,000(Workers 上限),约为 OWASP 建议值 600,000 的 1/6;旧用户登录后透明升级;迁移脚本 `migrate-002-auth.sql`。**未部署、未运行。**
- fix(后端): 常量时间比较、`ALLOWED_ORIGIN` 默认空、安全响应头。**未部署、未运行。**
- fix(前端): 52 周区间单次遍历、调色板单次遍历、主题 key 统一。

## 尚未完成
- 修复后在用户本机(真实快照)的自检结果。
- `backend/README.md` 同步(本轮只拿到 index.html 和 CHANGELOG.md,没有后端文件)。
- 核对 `worker.js` 对 `pct_up` / `pct_down` 与 `favGroups` 的处理。
- 云状态的服务端结构校验。
