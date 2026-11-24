# CHANGELOG

说明:2026-11-21 起本环境已可执行代码并提交 git,记录改为以 commit 为准。"验证"一栏只写实际做过的事。

## 未发布 · 持仓「无法定价」与三处结论面板的数据质量(2026-11-24,把信封从温度计推广到持仓域)

温度计那次立的规矩是「算不出来就说算不出来」;这次把它推广到**持仓相关的三个结论面板**(持仓总览 / 分散度 / 纪律复盘),并修掉一个真实可达的数据蒸发。

### 复现(改前实测,不是构造)
600519 + NVDA 各 100 股 + 现金 50 万,然后走真实路径同步 A 股快照(`resetUniverseTo`):

| | 改前 | 改后 |
|---|---|---|
| 总资产 | 681,074 → **662,450** | 681,074 → 662,450(**含说明**) |
| 持仓表 | 2 行 → **1 行** | 2 行(孤儿行标注「不在当前股票池 / 无法定价」) |
| 界面提示 | **无** | 「1/2 只持仓可定价 · 1 只无法定价(成本 ¥18,640),未计入总资产与市值 · NVDA」 |
| 纪律·止损 | **✓ 止损在位 · 全部在位** | 「— 止损在位 · 已验 1/2 只」 |

金额没错(不编造价格是对的),错的是**一句话都不说**;而纪律面板那句绿灯尤其糟:它只查了 1 只,却报了「全部」。

### 做了什么
- `resolveHoldings()`:持仓统一分成「可定价 / 无法定价」两堆,`accountMetrics` 与 `renderPortfolio` 共用。此前两处各自 `if (!s) return null` 跳过,是蒸发与口径不一致的共同来源。掉池持仓**只报成本、不猜价格**。
- 面板级数据质量信封 `dataQuality(available, total, {notes})` + `dqLineHTML()`,形状对齐后端 `core/envelope.py`(`available/total/missing/degraded/note`)。温度计是**维度级**信封(每维各自 available),粒度不同,注释里写清别硬合并。
- 分散度:权重只覆盖可定价市值 —— 面板上写明,并标「+N 未定价」;相关系数覆盖率(`x/y 对可算`)与窗口根数改为**按实际算出来的值**报,不再写死「近 120 根」。
- 纪律复盘三处校正:
  - 评级分母:5 条规则只判得出 3 条时,旧实现显示「3/3 守住」读起来是满分;现在带「· 2 项缺失」,且**完美判定要求全项可判**,否则不给百分比、不给 `is-pass`。
  - 追高规则:旧实现「有一笔缺 chg 就整条废掉」,19 笔有效样本白扔;现在按可用子集判定并标注覆盖率(`6/8`),但可用样本不足 5 笔仍判缺失(不拿 2 笔硬判 50% 追高)。
  - 止损规则:诊断止损取不到时判缺失,不再当成「在位」。
- 孤儿行灰化 + 斜体代码 + `cursor:default`(不可点击),新文字在亮暗两套主题下实测 5.46~10.96:1。

### 为什么不迁后端
这一轮**没有**把持仓计算搬到 FastAPI,理由与温度计那次同源,而且更硬:持仓标的可以是前端 5,212 只里的任意一只,后端 `/api/market/universe` 只有 31 只精选,`GET /api/market/kline?code=000001` 直接 404。搬过去就是「同一功能两种口径」。规则:先量数据覆盖率,再谈架构层。

### 验证
- `verify-orphan-holding.js`(新增)**29/29**:真实路径制造孤儿;基线→降级→恢复三段;含 WCAG 4.5:1 亮暗实测。探针自身两处缺陷当场修掉(G 段跑在恢复之后、两次取样落在同一主题)。
- `verify-pf-parity.js`(新增)**14/14**:拿 `git HEAD` 的旧文件与新文件跑同一组持仓对账 —— HHI `0.3139318720418619` 两侧完全一致、相关矩阵逐格一致、五条规则与评级一致,证明「只加语义、没动数值」。首跑出现 8.5e-6 权重差,查实为 `liveTick` 在等待期间漂移 `last/chgPct`,属探针缺陷。
- selftest **49 → 52**,新增 3 组(均在旧实现上会失败)。
- 全量回归 **20 个带断言的探针 333 条断言 0 FAIL**;`contrast.js` 亮/暗 0 违规;`probe-layout` / `probe-mobile` / `probe-invisible` 无新增溢出。

## 未发布 · 温度计数据质量(2026-11-24,借鉴 QuantFlow Pro 的 data_quality 信封)

把「某一维算不出来」从**静默填中性值**改为**结构化标注不可用**,并让权重覆盖不足时不出结论。

### 做了什么
- 四维各自返回 `{score, available, note}`;`computeThermo()` 新增 `dimList / missing / coverage / insufficient`。
- 缺数据时不再兜底:原实现分别兜 `50 / upR=0.5 / 50 / vAvg=1.5`,画面上与真实计算值毫无区别;现改为该维 `available:false`、分数位显示「—」、说明挂在 `title` 上。
- 合成**只对有数据的维度做加权平均并归一化**,不拿 50 去凑 —— 填中性会把任何局部数据稀释成「中性」,恰好是最容易骗过人的假。
- 权重覆盖 < 0.60(即缺两维以上)判 `维度不足`,不给结论、不给操作建议,与纪律面板「样本不足」、分散度「持仓不足 2 只」同一条规矩。四维权重为 .30/.25/.20/.25,故 0.60 恰好把「≥3 维」与「≤2 维」分开。
- 派生指标同口径:`turnover/adr/ret20/vAvg` 算不出时给 `null`,渲染为「—」。其中 `adr` 原为 `downN ? upN/downN : 1`,全涨时是无穷大却显示 1.00,一并改正。
- 顺带修 `#gaugeVal` 只由「滚入视口」那一次动画写入、`renderThermo` 从不更新它的问题(数据降级后大字会停在旧值);数据不足时大字显示「—」而非摆一个数。

### 为什么不放到后端(上一轮曾建议迁后端,此处更正)
温度计四维依赖的是**全量 5,212 只 CN 标的**(宽度=上涨占比、轮动=行业极差、波动=400 只样本 ATR),而后端 mock provider 只有 31 只精选(CN 12)。后端算出来的会是另一个数,前端一旦采用就是「同一功能两种口径」。
把 10,600 只标的的生成器移植到 Python 不划算:`GEN_STOCKS` 依赖顺序 RNG 流 + 数百个中英文词根,任何一处差异都会让后续所有 code/price 错位,属于高成本高风险的伪精确。
**结论:计算留在数据所在的一侧。** 等后端真持有全量数据(接 akshare 或落地全市场快照)时再迁,届时直接复用后端已有的 `DataQuality` 信封。

### 验证
- `verify-thermo-quality.js`(新增)**34/34**:含「用改动前原式重算四维逐维比对」——实测 `{trend:53, breadth:62, rotation:49, volatility:63}`、合成 57,与改动前完全一致,证明重构未改算法;另覆盖四维全缺/缺两维/缺一维三档、DOM 的 is-na 渲染、切主题后缺失态保持、零 pageerror。
- selftest **46 → 49**,新增 3 组:四维全缺标不可用且派生指标给 null、缺两维按覆盖判维度不足、缺一维(0.70)照常给结论。
- 全量回归 17 探针 + selftest 49/49 + 对比度亮/暗 0 违规。

## 未发布 · 全栈化第一阶段(2026-11-24,借鉴 QuantFlow Pro 前后端框架)

把「单文件纯前端模拟终端」升级为前后端分离。**前端仍是那个 `index.html`,没有重写**;后端新增 FastAPI 服务。

### 研究对象实测
`https://fund-assessment.onrender.com` = FastAPI(uvicorn) + OpenAPI 3.1 + **148 路由 / 19 tag**;前端 10335 行 HTML + 20 个 JS + 10+ CSS、**零框架零构建**(无 `type=module`)、25 个 `#page-*` 视图。完整研究见 `deliverables/gstack/framework-study-quantflow-2026-11-24.md`。

借鉴三项 / 不借两项:
- **借**:数据质量信封(`data_quality.available_dims/total_dims/missing_dims`)、按域分 tag 的分层、骨架层回滚开关(首段判定即 return)
- **不借**:25 页面 + 148 路由的多页形态(观潮是单屏终端,照搬即毁)、它「只有请求有模型、响应是 `additionalProperties:true` 裸 dict」的做法(响应同样要有契约)

### feat(backend): FastAPI 骨架 + 行情 API(556f98b)
- 分层:`providers/`(行情来源协议 + mock 实现)、`services/`(切片/聚合/均线)、`routers/`(行情、健康检查)、`core/`(质量信封、标的注册表)
- 接口:`/api/health`、`/api/market/universe`、`/quote/{code}`、`/kline`(日/周/月)、`/bars`(增量同步)
- **1D 分时返回 422 而非编造**:前端分时是 `genIntraday` 本地合成,后端再造一份就是两个真相
- 标的资产由脚本从前端抽取(`extract_universe.js` → `data/universe.json`,31 只:CN 12/US 10/HK 6/CRYPTO 3),不手抄

### feat(frontend): 后端数据桥(04b63b1)
- 只换数据来源,不动渲染函数,`series` 仍同步读取 → 200+ 函数零改动
- 开关:`?api=off` 强制本地(行为与升级前完全一致)/ 不带参数同源自动探测 / `file://` 默认本地 / `?api=on` 强制连后端
- 同步 31 只 × 1300 根、并发 4;过半失败标 `degraded` 而非装作成功;同步过的标的打 `_src='api'` 以区分来源

### 验证(实测)
| 项 | 结果 |
|---|---|
| 序列一致性(`test_parity.py`) | 4 标的 × 1300 根,最大相对误差 **7.8e-15**,日期 100% 对齐 |
| K 线一致性(`test_parity_api.py`) | **30/30** 用例(3 标的 × 10 组区间/周期),含 `1W/周K=1 根`、`1M/月K=2 根` 边界,最大 **5.3e-15** |
| 前端接入(`verify-api-bridge.js`) | **18/18**(同源接入 / `?api=off` / `file://` 三场景) |
| 全量回归 | 17 探针全 exit=0、selftest **46/46**、对比度亮/暗 **0 违规** |

一致性基准由前端**真实源码**产出(从 `index.html` 抽函数在 node 里跑),不是凭记忆重写。表述只说「一致到 1e-12」,不宣称「逐字节相同」——`math.*` 与 JS `Math.*` 有浮点末位差异。

### 踩到的两个坑(已写入注释与测试)
1. **时区**:后端返回本地口径 `YYYY-MM-DD`;前端 `new Date('2026-11-17')` 会按 UTC 解释并在 +08:00 倒退一天,必须 `new Date('2026/11/17')`。
2. **假绿**:第一版探针在 `QF_API.synced` 写入前就断言"数值一致",而本地生成的数值同样对得上,于是"通过了"却证明不了数据走了后端 → 加 `_src` 标记后才能真断言。

## 未发布 · QA 验收返修(2026-11-24,质量门神 3 个 P1)

首次验收结论 🔴 No-Go。回归本身全绿(16 探针 236 断言、selftest 46/46、对比度 0 违规),但自设计攻击打出 3 个 P1,均已在三个独立 commit 修掉。

### fix(kline): 1D/周K 空白图崩溃(8a9f61a)
- 复现:打开个股 → 点 1D → 点 周K。K 线区整块画白,抛 `TypeError: Cannot read properties of undefined (reading 't')`。
- 根因:1D 选周K 会换到 1W(5 根日线),周聚合后只剩 1 根 → `labelCount = min(5,1) = 1` → `i/(labelCount-1)` 分母 0 → `idx = NaN` → `data[NaN].t` 抛错,draw 中断。
- 修法三层:①`draw()` 单根不做插值除法;②周期与区间做容量校验,不足就抬档(周K ≥50 根日线、月K ≥210 根,1M→3M / 1Y);③反向路径(周K 状态点 1D)强制回落日K——QA 只报了单向,反向同样可达。
- 顺带:崩溃会让 `updateOhlc`/`setSynthBadge` 都不执行,角标滞留旧周期口径(故障态下诚实标注变成假话);日K 图例列着 MA5/10/20 但日K 不画快线 → 图例改为由「是否真有有效点」驱动;MA 快线改不透明绘制(半透明把 token 4.22 打成像素 3.28)。

### fix(portfolio): 相关矩阵表头错列(26a470d)
- `.corr-head` 只声明 `repeat(var(--cn),1fr)` 却渲染 1+cn 个 span → 列名整体右移一格、末位换行,按列头读矩阵会读错标的。改 `64px repeat(var(--cn),1fr)`。
- 同批修口径不实:`DIVER_CORR_WINDOW=120` 只用于文案,实际算的是全量 1300 根(AAPL×MSFT 实测 -0.005 vs -0.105,差 20 倍)→ 真切 `slice(-120)`。
- 清死代码:`void sells`、`renderDiversification` 未使用的 `m`。

### fix(thermo): 波动维度恒为 4(18f9c7f)
- 原式 `85 - vAvg*55` 在实测 atrPct(均值 3.56、区间 1.47–7.42)处恒为负,clamp 后**恒等下界 4** → 四维实际是三维+常数,且复合分上界 73.75 < 80,「过热」档永久不可达。等于把硬编码 64 换成硬编码 4 + 一个死档位。
- 改按锚点标定 `cl(104 - vAvg*11.5)`:1.5% → 87、3.5% → 64、7.5% → 18;「过热」重新可达(上界 94.5)。

### 探针补强
`verify-borrow` 21 → 32 断言:1D↔周K 双向崩溃守卫(含画布像素非空)、周/月K 根数下界 ≥10(原「≤170」单边断言下 2 根也 PASS)、相关矩阵表头列数与同行校验、温度计波动维度可分辨性、MA 图例诚实性。

### 未修但已知(记在报告里,不影响上线)
纪律面板「不追高」是全有或全无(一笔旧记录缺 `chg` 就让整条规则缺失,符合规格但可改成按可统计样本算);纪律芯片用红绿、相关矩阵用中性色,两套语义并存;`renderThermo` 的 `thermoCache` 写入守卫与 `initReveal` 的读取口径不完全统一。

## 未发布 · 借鉴升级(2026-11-23,借鉴 QuantFlow Pro 四项:纪律面板 / K线聚合 / 分散度 / 温度计)

五个 commit(72e0066 / 39d05e9 / c6fc784 / 本次 test+docs / de9557c 的 gitignore chore)。
参考项目为单文件 `fund-ref.html`(558KB),只取算法与交互口径,不取样式。

### feat(portfolio): 交易复盘纪律面板 + 持仓分散度诊断(72e0066)
- **纪律面板**:5 条规则(不追高 / 止损在位 / 频率节制 / 单票≤40% / 单行业≤50%)渲染成三态芯片(✓ 通过、! 未守、— 缺失)。纯本地规则引擎,从 `account.trades` / `positions` 即时推导,**零新增存储**;缺失项只标注、不计入命中率;样本 <5 笔直接判「样本不足」,不硬给结论。成交记录追加 `chg` 字段,旧记录缺该字段时落缺失态而非判失败(向后兼容)。
- **分散度诊断**:HHI、有效持仓 `1/HHI`、近 120 日 Pearson 相关矩阵(最多展示前 8 大权重)。相关性是**风险维度不是涨跌信号**,故矩阵走中性色阶,不用红涨绿跌;持仓 <2 走空态;导入标的标注「合成回放」。
- 集中度阈值抽出 `CONC_LIMIT`(stock .4 / group .5)供 X-RAY 与纪律面板共用,删掉两处硬编码。

### feat(kline): 周/月 K 聚合 + MA5/10/20 + 加载防竞态(39d05e9)
- `aggBars` 纯函数聚合:周 K = 5 根日线一组、月 K = 21 根一组;o 取组首、c 取组尾、h/l 取组内极值、v 求和、t 用组首;聚合后超 170 根从最旧端截尾。残行(O/H/L/C 非正)先过滤再聚合。
- MA5/10/20 仅周/月 K 开启;canvas 不认 CSS 变量,改为绘制时读 `--ma5/--ma10/--ma20` 计算值。
- **防竞态**:`_dhSeq` 序列号。`loadRealKline` 有 20s 网络窗口,窗口内切周期或换标的时,晚到回调直接作废,不覆盖新视图。
- 1D 分时无周期概念:选周/月自动切到 1W/1M 路径,`synthNote` 带上聚合口径角标(「月K(21 日聚合)」)。
- **修一处未经验证的宣称**:原注释写「MA 三色对明暗两主题均 ≥3:1」,实测亮底 `#EFEFEA` 上只有 2.27 / 2.17 / 2.91(图形件标准 3:1)不达标。现按主题给值——暗底 `#C9974B/#7BA7D9/#9C7BD9` = 7.52/7.86/5.87,亮底压深一档 `#96682A/#3D6C9E/#7A57B8` = 4.22/4.74/4.69;图例色块改同源变量,消除「图例与折线不同色」。

### feat(thermo): 大盘温度计四维复合评分,替代硬编码 64 分(c6fc784)
- 四维加权:趋势(指数 vs MA20).30 + 宽度(上涨占比).25 + 轮动(行业极差).20 + 波动(ATR% 反向).25,映射 4–97 分与五档文案。日粒度确定性计算(实测两次调用全等),**不进 liveTick**;主题切换只重绘不重算(`thermoCache`)。
- **清剿静态假文案**:原「2.31 万亿」成交额、「北向资金连续三日净流入」、「风险偏好 · 中性偏积极」、「建议维持 6 成仓位」全是写死的,换成真实计算的成交额 / 涨跌比 / 20 日涨幅 / 模拟波动率,并挂方法学角标「四维复合评分 · 本地模拟序列确定性计算 · 非真实市场研判 · 不构成投资建议」。

### test(selftest): 6 组新增用例 + 本节 CHANGELOG
- selftest **40 → 46**:aggBars 聚合口径、drawerBars 残行过滤、温度计确定性/值域/level 自洽、温度计诚实标注(反向断言假文案已清)、pearson 与分散度(等权 HHI 0.25 / 有效持仓 4 / 对角恒 1 / 对称)、纪律三态与追高统计(8 笔样本、3 笔追高)。
- 新增探针 `verify-ma-contrast.js`(27 断言,图形件 3:1 + 图例同源同色)。

### 验证(实测,非推断)
- 16 个探针全 PASS:r7 / r6b / acct / py / round2 / touch / n1 / n2 / n3 / strip / readable / r2motion(15) / tide(33) / bughunt(12) / borrow(21) / ma-contrast(27)。
- `?selftest` **46/46**;`contrast.js` 文本对比度亮/暗均 **0 处** <4.5:1。
- 拆 commit 时逐态冒烟(页面加载 + 零 pageerror + 自检读数),四态分别 40 / 40 / 40 / 46。

### 探针维护(顺带修的探针自身问题,非产品代码)
- `verify-r2motion.js` / `verify-tide.js` 用 `process.cwd()` 拼 Playwright 与页面路径,换目录跑就 `MODULE_NOT_FOUND` → 改 `__dirname` 相对解析,与其余探针一致。
- `verify-round2.js` / `verify-touch.js` 把「自检 40/40」写死,每轮新增用例都会假报 → 改断言「分子=分母且总数 ≥46」。
- `probe-selftest.js` 找的是 `#selftestPanel`,实际 id 是 `#selfTestPanel`(驼峰),静默落回 `body.innerText` 取数 → 修正 id,并从 `<b>` 标题解析 N/M。

### 已知局限(不隐藏)
- 温度计四维权重 30/25/20/25 与分档阈值(80/60/40/20)为经验值,**未做历史回测校准**。
- 纪律样本线 5 笔、追高阈值 40%、集中度 40%/50% 同为经验阈值。
- 分散度相关矩阵基于近 120 日,导入标的为合成回放序列(UI 已标注)。
- 温度计为日粒度确定性计算,盘中不实时跳动——设计取舍,非缺陷。

## 未发布 · 阶段五(2026-11-23,设计审计 Round 2 + Round 3,三轮迭代计划落地)

三个 commit(fc89fd6 / fc339ed)。

- **Round 2 动效与交互**(fc89fd6):时长 12 档收口 4 档并令牌化(--t-fast .12s / --t-state .2s / --t-panel .24s / --t-enter .56s),.rv 900→560ms;intel-row hover 由 padding 位移(每次 hover 整行 grid 重排)改为 background 提示;dot-live 脉冲由 box-shadow 无限动画(常驻每帧 repaint)改 ::after transform+opacity 环;prefers-reduced-motion 标准兜底(残余 158 项 → 0);新增 :focus-visible 全局描边、disabled 三态、:active 下压;移除 .btn 常驻 will-change;进度条/柱状容器补 contain。探针 `verify-r2motion.js` 15/15(含 reduced-motion 独立上下文断言)。
- **Round 3 体系**(fc339ed):删除 1304–1420 的 91 行整段重复 CSS 规则(FRAMEWORK COMPONENTS 段重抄,后份悄悄丢失 hover transition);全文 「」→“”(44 处),全角逗号仅留搜索分词正则一处;.breadth-cells 马赛克改为**潮位图**(列=15 个一级行业 × 行=10 档时间回放,最新一行真实板块占比、历史行确定性合成,title/副标注如实披露「回放」)。探针 `verify-tide.js` 33/33(7 档宽度无溢出 + 最新行真实性)。
- **未做**(报告 Round 3 的纯样式大重构,风险收益比不划算,挂起):间距 8px 网格对齐(13%→80% 需动 3761 条 spacing)、断点 13→4 收口、字号 40 档令牌化;移动端行式列表改卡片式属交互模型重构。如需继续,建议单独一轮 + 截图比对。

## 未发布 · 阶段四第 4 轮(2026-11-23,R7 补漏 + R6 第 4 步快览条,任务书全部收尾)

两个 commit(7088d55 / b150900)。**至此 UX 报告全部条目(含可选项)销项。**探针 `verify-strip.js`(12/12)与全量回归(selftest 40/40)。

### fix(trust): R7 补漏——hero 虚假宣称清零(7088d55)
- 前轮 R7 只处理了 mkt-status / termMeta / 68.4%,hero 区两处漏网:①「数据流在线 · 延迟 24ms」(本地静态页无数据流,`#latency` 还在写 16–34ms 随机数)→ 改「模拟行情 · 本地生成 · 非实时」,去掉脉动 live 圆点;②「今日已处理行情快照 1,286,400+」(虚构初始值 + 每 tick 随机 +1200~3800)→ 从 0 起、每 tick +1,标签改「本次会话模拟 tick 次数」。
- 教训:R7 修复后应全局 grep 随机数写入(`Math.random() * 18` 这类),别只看报告点名的三处。
- verify-r7 探针顺手修了时间敏感断言:第一断言写死「当前为周一盘中」,16:42 后重跑必假报;改为按时段推算期望状态。

### feat(strip): R6 第 4 步——首屏指数/自选快览条(b150900)
- hero CTA 下方 `.quick-strip`:6 个指数 chip + 最多 8 个自选 chip(|涨跌| 降序)+ 去终端入口;≤760 显示(桌面 hero 已有面板),横向可滑 + scroll-snap,chip 44px 触控。
- 自选 chip 点击回个股抽屉;指数 chip 按其 mkt 字段切市场过滤并滚到终端;renderTable 作为自选变更公共汇点同步条内容。
- 价格更新走 `qsTickUpdate` 原地改写 `data-qs-px/cg`,**不重建 DOM**——innerHTML 重建会把横向滚动位置打回起点。
- 两个坑:①hero-copy 是 `align-items:flex-start` 的 flex 列,条必须显式 `align-self:stretch;width:100%`,否则按内容宽增长、被 `.hero overflow:hidden` 裁掉且不可滑;②html 全局 `scroll-behavior:smooth`,`scrollLeft` 赋值是动画,探针读值前要等动画到位。
- verify-strip 12/12;r6b 探针同步更新菜单项数(N1 加了第 4 个次级项)。

## 未发布 · 阶段四第 3 轮(2026-11-23,R6 收尾 + UX 第 4/5 期:R6 / N3 / N1 / N2)

五个 commit(8a8dc09 / abc7bfa / 51014c1 / e6640e0),**至此 UX 报告 roadmap 全部销项**。探针 `verify-{r6b,n3,n1,n2}.js`,selftest 40/40。

### feat(mobile): R6 收尾(8a8dc09)
- 移动菜单次级分组:提醒/设置/主题三项降为 `--mute` 13px,组间分隔线(§Q23),与 6 个页面导航视觉分层;今日待办加入后分隔线上移至组首项。
- `.kbd-btn` ≤760 由 44 提到 48,与导航图标对齐(Q04 大小不齐销项)。verify-r6b 13/13。

### feat(kbd): N3 键盘优先看盘流(abc7bfa)
- `j/k` 在终端表格移动光标行(虚线描边),抽屉开着时直接切标的;`Enter` 打开光标行;`1-4` 切抽屉四页;`/` 聚焦搜索;Esc 改逐层关闭(一次只关最上层)。
- **坑**:行情 tick 每 1.2–3.8s 重渲染表格,键盘光标按代码记忆恢复(`kbRestore`),且恢复时**不能** scrollIntoView,否则每次 tick 把视口拽到光标行;筛选/翻页后行不在当前页自然清除。输入框聚焦不劫持。verify-n3 17/17。

### feat(today): N1 今日待办聚合面板(51014c1)
- `#todayPanel` 抽屉三分区:已触发提醒 / 自选异动(|涨跌|≥3%) / 自选快照,行点击回跳个股抽屉;底部「查看自选列表 / 管理提醒」直达。空状态给引导。
- 桌面导航加待办图标(≤560 隐藏),移动菜单加「今日待办」;提醒触发时面板开着同步刷新。verify-n1 19/19(含 6 档宽度导航溢出检查)。

### feat(order): N2 条件单(e6640e0)
- 抽屉交易页新增条件单面板:升破买入 / 跌破止损(止损单须有持仓),触发价方向校验;数量沿用委托数量,≤760 补 44px 触控。
- 撮合复用行情 tick(`checkCondOrders` 与 checkAlerts 同一时间线):到价按当时市价走 execBuy/execSell,**一次性有效、触发即移除保证幂等**;资金/持仓不足触发即作废。localStorage 持久化(`guanchao-cond-v1`,sanitize,上限 20),可撤销。verify-n2 15/15。

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
