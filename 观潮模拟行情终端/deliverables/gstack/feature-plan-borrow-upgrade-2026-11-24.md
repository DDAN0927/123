# 计划书：借鉴升级收尾（2026-11-24 恢复执行版）

**日期**：2026-11-24
**场景**：全流程交付（暂停于「实现+单点验证完毕」与「回归/提交/QA/发布」之间）
**参与**：主理人（编排 + 落盘；本轮无成员独立产出，属单 Agent 直调）
**上一版**：`feature-plan-borrow-upgrade-2026-11-23.md`（4 步，已被本版取代）
**恢复指令**：「继续计划书」→ 从第 1 步顺序执行至第 6 步

---

## 📌 TL;DR

- 借鉴 QuantFlow Pro 的 **4 项升级已全部实现**，单点验证通过：`selftest` 源码 46 个用例（40→46）、`verify-borrow` 21/21
- 但**全量回归被中断未跑完**，`index.html` **未 commit**（工作区 `M index.html`，+437/−26），`site-release/` 未同步 → **线上仍是旧版**（`71d3174f`）
- 剩余 6 步可一轮收口：回归 → 拆 4 commit + CHANGELOG → QA 出 Go/No-Go → 落协作报告 → 线上同步 → 清场
- 唯一未覆盖的验证缺口：**MA 三色按 3:1 图形件标准未跑 `contrast.js`**（第 1 步顺带补）

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| 当前状态 | 🟡 代码就绪、验证不完整、未入库未上线 |
| 阻塞项 | 2（全量回归未确认；git 未提交） |
| 风险项 | 1（MA 三色 3:1 未复核） |
| 行动项 | 6 步，预计一轮完成 |
| 建议负责人 | 主理人（1/2/4/5/6）+ 质量门神（3） |

---

## 1. 暂停点实测核对（本次落盘前 12:46 实测，非引用记忆）

| 核对项 | 实测结果 | 结论 |
|---|---|---|
| `git status --short` | `M index.html`；未跟踪 `.wbapp_*.genie`、`.workbuddy/`、`site-release/` | 无丢失改动，从第 1 步开始安全 |
| `git diff --stat` | `index.html` +437 / −26，单文件 | 四项升级全在一份文件内，拆 commit 需按代码块切 |
| 当前 HEAD | `24e065e fix(account): loadAccount 补 sanitize` | 与记忆一致 |
| `index.html` sha256 | `852ce5a4…`（419,051 B，11-23 18:56） | 含 4 项升级 |
| `site-release/index.html` sha256 | `71d3174f…`（395,369 B，11-23 18:01） | **确认线上为旧版**，差 23,682 B |
| selftest 用例数 | 源码 `^  t('` 计数 = **46** | 与 46/46 口径一致 |
| `verify-borrow.js` 断言 | **21** | 与 21/21 一致 |
| CHANGELOG 顶部条目 | 阶段五（设计审计 Round 2+3），**无借鉴升级一节** | 待第 2 步补 |
| 探针可用清单 | `_stage3/` 下 15 个 `verify-*.js`（14 回归 + borrow） | 第 1 步据此组回归矩阵 |
| `.gitignore` | 已忽略 `deliverables/`、`.workbuddy-ai/`、`_backup/`；**未忽略** `site-release/`、`.workbuddy/`、`.wbapp_*.genie` | 第 2 步需先定杂项归属，否则 4 个功能 commit 被污染 |

---

## 2. 已完成：4 项升级落地清单

| # | 升级项 | 借鉴来源 | 代码锚点（`index.html` 行号） | 关键设计 | 验证 |
|---|---|---|---|---|---|
| 3 | **交易复盘纪律面板**（5 规则三态芯片） | `renderDisciplineCompact` | L4619 `computeDiscipline` / L4679 `renderDiscipline` | 纯本地规则引擎，从 `account.trades/positions` 即时推导，**零新增存储**；三态 ✓通过 / !未守 / —缺失，缺失不计入命中率；`DISCIPLINE_SAMPLE_MIN=5` 样本不足不硬判；成交记录追加 `chg` 字段（旧记录缺失→缺失态，向后兼容） | selftest 1 组 |
| 4 | **K 线 周/月聚合 + MA5/10/20 + 防竞态** | `loadKline` calcMA | L3442 `aggBars` / L3079 MA 计算 / L3241 canvas 绘制 / L5740 `_dhSeq` | 周=5 日一组、月=21 日一组；MA 用固定 hex（canvas 不认 CSS 变量）；`_dhSeq` 序列号防 `loadRealKline` 20s 网络窗口内切周期被晚到响应覆盖；1D 选月 K 自动降级 1M；残行（O/H/L/C 非正）过滤 | selftest 2 组 |
| 2 | **持仓分散度诊断**（HHI / 有效持仓 / 相关矩阵） | 组合分散度 | L4551 `pearson` / L4584 `computeDiversification` / L4587 `renderDiversification` | HHI 与有效持仓 1/HHI；近 120 日 Pearson 相关矩阵（中性色阶，非红涨绿跌，避免与涨跌语义冲突）；持仓 <2 走空态；导入标的标注「合成回放」 | selftest 1 组 |
| 1 | **大盘温度计**（四维复合评分） | `thermometer` | L6007 `computeThermo` / L6062 `renderThermo` / L863 CSS | 趋势(指数 vs MA20) .30 + 宽度(上涨占比) .25 + 轮动(行业极差) .20 + 波动(ATR% 反向) .25，替代硬编码 64 分；**清剿静态假文案**（2.31 万亿成交额、北向净流入、风险偏好套话），换真实计算的成交额 / 涨跌比 / 20 日涨幅 / 模拟波动率 + 方法学角标 + 4 条维度 bar；日粒度确定性计算，**不进 liveTick** | selftest 2 组 |
| — | 探针 | — | `_stage3/verify-borrow.js` | 温度计 / 周期竞态 / 分散度 / 纪律 / 移动端口径 | **21/21** |

**计数**：`selftest` 40 → 46（+6 组，其中 K 线 2 组、温度计 2 组、分散度 1 组、纪律 1 组）。

---

## 3. 六步执行计划（按序，每步含命令 / 验收 / 回退）

### 第 1 步 · 全量回归（含 MA 三色专项）
- **做什么**：重跑 14 个既有探针 + `verify-borrow` + `selftest`，并对 MA 三色补跑 `contrast.js`
- **命令**：
  ```bash
  cd C:/Users/Administrator/Desktop/GG/deliverables/gstack/_stage3
  for f in verify-r7 verify-r6b verify-acct verify-py verify-round2 verify-touch \
           verify-n1 verify-n2 verify-n3 verify-strip verify-readable \
           verify-r2motion verify-tide verify-bughunt verify-borrow; do
    echo "== $f"; node $f.js | tail -4
  done
  node probe-selftest.js          # 读 #selfTestPanel b，期望「46/46」
  ```
- **MA 三色专项**：`#C9974B`(MA5) / `#7BA7D9`(MA10) / `#9C7BD9`(MA20) 画在 K 线 canvas 上，属**图形件 3:1 标准**（非文本 4.5:1）。用 `contrast.js` 按图形件阈值跑，亮/暗两主题各一次；结论写进第 4 步报告。
- **验收**：15 探针全 PASS + `selftest 46/46` + MA 三色 ≥3:1（不足则换色或加描边）
- **回退**：任一 FAIL → 先判是否本轮 4 项引入（`git stash` 回旧版对照跑同一条断言）；老探针 FAIL 多因口径漂移，按「已知坑」清单排查

### 第 2 步 · 分 4 个 commit + CHANGELOG
- **前置（新增，原计划未列）**：先处理杂项，避免污染。建议在一次 `chore(git): ignore 部署镜像与工作区元数据` 里把 `site-release/`、`.workbuddy/`、`.wbapp_*.genie` 加入 `.gitignore`（`site-release/` 是发布镜像，400KB 与主文件重复；`.workbuddy/` 是记忆元数据，本就不该入库）
- **拆法**：四项升级同处单文件，`git add -p` 不可用（非交互）。可行为路径——先 `cp index.html /tmp/borrow-full.html` 留全量 → `git checkout -- index.html` 回旧版 → 按第 2 节锚点行区间逐块从全量副本抽入 → 每块 `node .../verify-borrow.js` 快速自证 → commit。顺序：纪律 → K 线 → 分散度 → 温度计（依赖最少者先）
- **中间态风险**：温度计与「文案清剿」牵连 gauge 结构，若单块无法独立加载，允许与相邻块合并，并在 commit body 注明「为可运行中间态与 X 合并」
- **commit 规范**：`feat(discipline|kline|diversify|thermo): …`，body 写借鉴来源 + 验证断言数
- **CHANGELOG**：新增「未发布 · 借鉴升级（2026-11-23）」一节，四条分述 + 探针/自检数字 + 明确写「四维权重与阈值为经验值，未做历史回测校准」
- **验收**：4 个 commit 各自 `git show --stat` 只含本块改动；HEAD 上 `index.html` sha 与 `852ce5a4…` 一致（拆 commit 不应改变最终内容）

### 第 3 步 · QA 验收（恢复团队，独立判定）
- **做什么**：`TeamCreate gstack-borrow-upgrade` → 调度 `gstack-qa-lead`，独立跑 `verify-borrow` / `verify-bughunt` / `selftest` + 第 1 步回归清单，出 **Go / No-Go**
- **要点**：门神须**独立执行**，不采信主理人给的数字；重点回归面 = 账户存储兼容（`chg` 字段旧数据）、K 线切周期竞态、移动端 375/414 下新增面板
- **产出**：Go/No-Go + 阻塞项清单 + 回滚预案（`git revert <4 commits>` 或 `cp` 旧 `site-release/index.html` 重部署）

### 第 4 步 · 落盘协作报告
- **路径**：`deliverables/gstack/feature-dev-borrow-upgrade-2026-11-24.md`
- **结构**：按 gstack 通用收口（TL;DR / 核心结论卡片 / 成员核心结论 / 综合发现 / 行动清单 / 待完善 / 成员产出索引 / 免责声明）；补「交付清单」段（代码变更 + 测试覆盖 + 发布检查清单 + 回滚预案）
- **注意**：`deliverables/` 在 `.gitignore`，报告不入版本库（与既往一致）

### 第 5 步 · 线上同步部署（链接不变）
- **命令**：`cp index.html site-release/index.html` → 校验两者 sha256 相等 → 对 `site-release/` 同目录重新 deploy
- **验收**：线上页面能 grep 到新标记（如「四维复合评分」「有效持仓」），且 `selftest` 在线上读数为 46/46
- **回退**：保留旧 `site-release/index.html` 副本，异常时覆盖回旧版重部署

### 第 6 步 · 收尾清场
- **记忆落盘**：`.workbuddy/memory/2026-11-24.md`（记录本轮：4 项升级 + 拆 commit 手法 + MA 三色结论 + 新增踩坑）
- **关停**：`TeamDelete`（团队仍在运行时先发 shutdown）
- **交付告知**：对话末尾给出报告路径 + 线上链接

---

## 4. 风险与注意（恢复前必读）

| 级别 | 风险 | 处置 |
|---|---|---|
| 🟠 | **MA 三色 3:1 未复核**：`#C9974B` 为低饱和琥珀，画在深色 canvas 上可能不足 3:1 | 第 1 步用 `contrast.js` 图形件口径跑亮/暗两主题，不足则换色或加 1px 描边 |
| 🟠 | **拆 4 commit 的中间态可能不可运行**（单文件强耦合） | 按第 2 步回退条款：允许合并相邻块，commit body 说明；不强求每个中间 commit 都过全量探针 |
| 🟡 | 恢复时工作区可能已被外部改动 | 执行前先 `git status` + `sha256sum index.html`，与本文第 1 节数字比对，不一致先查清再动手 |
| 🟡 | 老探针口径漂移（历史踩坑：`#selfTestPanel b` 读数、`scroll-behavior:smooth` 需等动画、liveTick 1.2–3.8s 数据漂移、时段断言随时间失效） | FAIL 先按「已知坑」清单排查，别急着改代码 |
| 🟡 | 温度计 selftest 用 `innerText` 断言静态假文案 | 后续再改前端文案须同步该断言，否则 46/46 变 45/46 |
| 🟢 | `deliverables/` 在 `.gitignore` | 报告与探针不进版本库，属既定约定 |

### 已知局限（写入报告，不隐藏）
- 温度计四维权重 30/25/20/25 与阈值（80/60/40/20 分档）为**经验值**，未做历史回测校准
- 纪律面板 `DISCIPLINE_SAMPLE_MIN=5`、追高阈值 40%、集中度 40%/50% 同为经验阈值；集中度已与 X-RAY 共用 `CONC_LIMIT`（DRY）
- 分散度相关矩阵基于近 120 日，导入标的为**合成回放序列**（UI 已标注）
- 温度计为日粒度确定性计算，不进 `liveTick`，盘中不实时跳动（设计取舍，非缺陷）

---

## 5. 环境备忘

- 探针运行方式：`node <probe>.js`，Playwright 取自 `_baseline/node_modules`，**必须 `chromium.launch({ channel: 'msedge' })`**（内置 chromium 缺失）
- 探针目标：`file:///…/index.html`，无需本地 server
- 自检读数：`#selfTestPanel b`，勿用 `body.textContent` 正则（会误抓行情数字）
- 中文环境 Windows + Git Bash；页面为单文件（`<style>` 两段，改样式先确认生效块）

---

> 本计划书由软件工坊主理人落盘，关键决策请由工程负责人复核。
