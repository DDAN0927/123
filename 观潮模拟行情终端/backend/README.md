# 观潮·模拟行情终端 —— 后端服务

把原本"单文件纯前端模拟终端"升级为前后端分离架构。前端仍是那个 `index.html`，
后端提供行情数据与（后续）计算服务。

> **数据声明**：本服务输出的是**本地确定性模拟序列**，不是真实行情。
> `/api/health` 里逐项声明 `data_is_simulated: true`。接真实数据是产品决策，
> 必须同步修改前端所有"模拟数据"标注，不能悄悄换源。

---

## 快速开始

```bash
# 1) 安装依赖（版本与实测环境一致，见 backend/requirements.txt）
python -m pip install -r backend/requirements.txt

# 2) 从 index.html 抽取标的资产（首次或前端 UNIVERSE 变更后执行）
node backend/scripts/extract_universe.js

# 3) 启动（项目根目录）
python -m uvicorn backend.app.main:app --reload --port 8000
```

打开：

| 地址 | 内容 |
|---|---|
| http://127.0.0.1:8000/ | 前端页面（同源，自动接入后端） |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/openapi.json | OpenAPI 规格 |

---

## 目录结构

```
backend/
├── app/
│   ├── main.py              FastAPI 入口、CORS、路由挂载、/ 提供前端单文件
│   ├── version.py           版本号（含 git short sha）
│   ├── core/
│   │   ├── envelope.py      数据质量信封 DataQuality（available/total/missing/degraded/note）
│   │   └── store.py         标的注册表 + provider 单例
│   ├── providers/
│   │   └── mock.py          确定性序列生成（逐行复刻前端 genSeries）+ Provider 协议
│   ├── schemas/
│   │   └── market.py        请求/响应 Pydantic 模型（响应也有模型，不只请求）
│   ├── services/
│   │   └── kline.py         区间切片、周/月聚合、均线（对齐前端 drawerBars/movingAvg）
│   └── routers/
│       ├── health.py        /api/health
│       └── market.py        universe / quote / kline / bars
├── data/
│   └── universe.json        标的资产（由 extract_universe.js 从 index.html 生成）
├── scripts/
│   └── extract_universe.js  抽取 UNIVERSE → JSON
└── tests/
    ├── parity_gen.js        前端真实算法产出基准（抽取 index.html 源码运行）
    ├── parity_kline_gen.js  前端聚合口径基准
    ├── test_parity.py       序列一致性校验
    └── test_parity_api.py   K 线接口与前端 drawerBars 逐根比对（30 组用例）
```

---

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务健康、provider、标的注册表、`data_is_simulated` 声明 |
| GET | `/api/market/universe` | 31 只精选标的元数据 |
| GET | `/api/market/quote/{code}` | 单标的最新快照（由日线推导，非逐笔） |
| GET | `/api/market/kline?code&range&period` | K 线；`period=W/M` 时返回 MA5/10/20 |
| GET | `/api/market/bars?code&limit` | 最近 N 根日线（前端增量同步用） |

区间：`1W/1M/3M/6M/1Y/5Y`（对应 5/22/66/126/252/1300 根）。
**`1D` 明确不支持**：前端分时是本地合成（`genIntraday`），后端再生成一份会变成两个真相。

每个返回数值的接口都带 `quality`：

```json
"quality": { "available": 1, "total": 1, "missing": [], "degraded": false, "note": "..." }
```

原则：**缺失即降级，不补 0、不给假值**。1W 区间聚出 1 根周 K 就如实返回 1 根。

---

## 为什么前后端序列必须一致

前端保留了离线回退：后端不可用时退回本地 `genSeries()`。若两边算法有任何差异，
同一标的会在"在线/离线"两种状态下画出不同的 K 线，用户会看到数据跳变，
且 selftest 的确定性断言会变成两套口径。

因此：

1. `providers/mock.py` 的 `mulberry32` / `gauss` / `hash_str` / `gen_series` 是
   **从 JS 逐行翻译**的，包括 `gauss` 里先去零 u 再取 v 的消耗顺序。
2. `services/kline.py` 的聚合口径对齐 `aggBars`（o 取组首、c 取组尾、h/l 取极值、v 求和、t 取组首）。
3. 有测试守着，且基准由**前端真实源码**产出，不是手抄：

```bash
node backend/tests/parity_gen.js index.html backend/tests/parity_js.json
python backend/tests/test_parity.py            # 序列：4 标的 × 1300 根

node backend/tests/parity_kline_gen.js index.html backend/tests/parity_kline_js.json
python backend/tests/test_parity_api.py        # 接口：3 标的 × 10 组区间/周期
```

实测结果：序列最大相对误差 **7.8e-15**，K 线 30/30 组用例通过（最大 **5.3e-15**），
日期 100% 对齐。**表述上应说"一致到 1e-12"**，不要说"逐字节相同"——
`math.*` 与 JS `Math.*` 存在浮点末位差异。

时区坑：前端 `t` 是 `new Date(2026,10,17)` 本地午夜，接口返回 `YYYY-MM-DD` 本地口径，
前端解析时必须用 `YYYY/MM/DD`（`new Date('2026-11-17')` 会按 UTC 解释并倒退一天）。

---

## 前端接入方式

`index.html` 末尾新增一段「后端数据桥」，**只换数据来源，不改任何渲染函数**：

| 打开方式 | 行为 |
|---|---|
| `http(s)://…/`（同源） | 自动探测 `/api/health`，成功则同步 31 只标的序列，`<html data-data-source="server">` |
| `?api=off` | 强制本地生成，行为与升级前完全一致（selftest 46/46 不受影响） |
| `file://` 直接打开 | 默认本地（不发起跨域请求） |
| `?api=on`（file:// 下） | 强制尝试连 `127.0.0.1:8000` |

同步完成的标的会带 `stock._src = 'api'` 标记，用于区分"来自后端"与"本地生成"
—— 因为两者数值本就一致，只比数值无法证明数据真的走了后端。

回滚：`?api=off` 即可整体关闭，无需改代码、无需回滚制品。

---

## 部署

三种入口，任选其一。**三者都必须满足两条**：绑 `0.0.0.0`、读平台注入的 `$PORT`。
绑 `127.0.0.1` 或写死 `8000` 在云端是 502，且日志里看不出来原因。

| 方式 | 制品 | 命令 |
|---|---|---|
| Render Blueprint | `render.yaml` | 连仓库后按 `render.yaml` 建服务 |
| 通用 PaaS / Heroku | `Procfile` | `web: uvicorn … --port $PORT` |
| 容器 | `backend/Dockerfile` | `docker build -f backend/Dockerfile -t guanchao . && docker run -p 8000:8000 guanchao` |

### 鉴权（可选，默认关）

| `ACCESS_TOKEN` | 行为 |
|---|---|
| 不设 / 空 | 开发模式：所有 `/api/*` 放行；`/api/health` 里 `auth.mode="off"`，**明说无鉴权** |
| 设了值 | 除 `/api/health` 外全部要求 `Authorization: Bearer <token>`（或 `X-API-Token`），否则 401 |

白名单只有 `/api/health`：它是探活端点，前端靠它判断「后端在不在」。
`/`、`/docs`、`/openapi.json` 也不拦 —— 拦了页面白屏，用户连「没有权限」这句话都看不到。

前端接入带 token 的写法（无需改代码）：

```
https://<host>/?token=<token>        # 首次带进来，之后记在 localStorage
https://<host>/?api=off              # 无论有没有 token，强制离线本地生成
```

`?api=off` 的优先级高于一切，鉴权态下同样有效 —— 回滚开关不能被新功能吃掉。

### 四种失败态必须能分得开

`<html data-data-source>` 取值，探针按它断言：

| 值 | 含义 | 用户该做什么 |
|---|---|---|
| `server` | 已连后端 | — |
| `local` | 后端没起来 / `?api=off` | 页面照常用，数据来自本地同算法 |
| `degraded` | 后端在，但过半请求失败 | 查上游/限流 |
| `denied` | 后端在，但没给有效 token | 加 `?token=` |

`denied` 是这轮补的：`/api/health` 在白名单里必然返回 200，**光看探活结果永远发现不了没权限**——
以前全部行情 401 会被笼统归到 `degraded`，排查方向直接错。

### ⚠️ 数据持久化仍未做

持仓/交易/账本仍在浏览器 `localStorage`，后端**不写任何用户数据**。
这意味着换设备、换浏览器看不到自己的持仓。这是刻意的（避免无账号体系时把私人数据收上云端），
但也意味着「多端同步」这件事还没解决，不要对外宣称「云端持仓」。

---

## 已验证 / 待办

完成：
- 标的清单、快照、K 线（日/周/月聚合 + MA5/10/20）
- 数据质量信封（`available/total/missing/degraded/note`）
- 前后端数值一致性测试（序列 + 聚合，共 34 组用例）
- 前端三场景接入验收（同源 / `?api=off` / `file://`，18 条断言）
- **可部署**：`requirements.txt` 钉版本、`Procfile` / `render.yaml` / `Dockerfile` 三入口、可选 Bearer 鉴权、`/api/health` 自描述鉴权态
- 部署链路验收 51 条（制品静检 20 + 开发态 5 + 鉴权态 16 + 前端真实接入 10），见 `_stage3/verify-deploy.js`

待办：
- 大盘温度计：四维每维带 `available`/`note`，不可用维置中性分并计入 `missing`
  （参考 QuantFlow Pro 的 `data_quality` 做法）
- 持仓、交易、纪律复盘、分散度迁到后端 ——**前提是先想清账号体系**，否则只是把本地数据搬到别人的服务器
- 真实行情 provider（akshare 等）——需要先决定产品定位与合规口径
- 数据持久化（当前零写入，见上文「数据持久化仍未做」）
- 限流：现在只有鉴权没有频率限制，token 泄露后可以无限刷

