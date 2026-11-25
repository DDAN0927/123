# 部署就绪度对照：QuantFlow Pro vs 观潮

> 提问：「跟 https://fund-assessment.onrender.com/static/index.html 这个项目的前后端部署差不多了吗」
> 时间：2026-11-24
> 取证方式：`/api/health`、`/openapi.json`（5 条路径）、直连 45 个 `_stage3` 探针、本机起停 uvicorn

## 0. 直接回答：不差不多

差得最狠的不是功能，**是"能被别人打开"这条链路，我们此前一次都没走通过**。

- 那个站在公网、有账号、有 148 条接口、有 Bearer 鉴权、有持久化目录、有 MCP 端点。
- 我们后端 5 条接口，只能在本机 `127.0.0.1:8000` 跑；线上页面仍是旧版（发布卡在 `SITES_ACCOUNT_MISMATCH`）。

但"接口少"不是这次的重点。真正的区别是：**它有成套的部署制品，我们一个都没有** ——
没有 `requirements.txt`、没有进程入口、没有鉴权。换句话说，换台机器我们连装什么版本都不知道。

## 1. 硬指标对照

| 维度 | QuantFlow Pro | 观潮 | 差距性质 |
|---|---|---|---|
| 后端路由 | **148** 条 / 19 个 tag | **5** 条 / 2 个 tag | 约 30 倍，短期不追 |
| 请求+响应模型 | 响应几乎全是裸 dict | **响应也有 Pydantic 模型** | 我们更好 |
| 鉴权 | Bearer，失败 401 | Bearer（可选），失败 401 | ✅ 本轮补齐 |
| 依赖声明 | 有 | 有（本轮补） | ✅ |
| 进程入口 | Render | `Procfile` / `render.yaml` / `Dockerfile`（本轮补，三个） | ✅ |
| 健康检查 | `/api/health` 报各数据源可用性 | `/api/health` + `auth` 自描述 | ✅ 略胜 |
| 数据源 | akshare 真实行情 | 本地确定性模拟 | **产品决策差异**，非能力差距 |
| 持久化 | `data/backup`、账本 JSON | 零写入（`localStorage`） | ❌ 明确不做，见 §4 |
| 限流 | 60 次/分钟 | 无 | ❌ 未做 |
| MCP 接入 | `/mcp` JSON-RPC 只读 | 无 | ❌ 未做 |
| 前端规模 | 10,335 行 + 20 个外部 JS | 8,897 行单文件 | 结构差异，非优劣 |
| 线上可达 | 公网 | **线上仍是旧版** | ❌ 卡账号权限 |

## 2. 本轮补了什么（都有实测）

### 2.1 制品三入口

| 文件 | 关键约束 | 踩错的后果 |
|---|---|---|
| `backend/requirements.txt` | 钉 `fastapi==0.165.0` / `uvicorn[standard]==0.54.0` / `pydantic==2.14.4` | 装到别的版本，前后端浮点一致性没有保证 |
| `Procfile` | `--host 0.0.0.0 --port $PORT` | 绑 127.0.0.1 或写死 8000 → 云端 502，日志无提示 |
| `render.yaml` | `healthCheckPath: /api/health`（必须真实存在） | 写错路径 → 平台判定不健康 → 反复重启 |
| `backend/Dockerfile` | 构建上下文是**仓库根**（要 `COPY index.html`） | 只拷 `backend/` → 首页 404 |

`requirements.txt` 的版本不是抄来的：探针 A20 会读运行时 `fastapi.__version__` 等三项，与文件里钉的逐项比对，不一致就红。

### 2.2 可选鉴权

| `ACCESS_TOKEN` | 行为 |
|---|---|
| 未设 | 开发模式放行；`/api/health` 返回 `auth.mode="off"` + `note:"未设置…禁止直接暴露公网"` |
| 已设 | 除 `/api/health` 外 `/api/*` 全部要求 `Authorization: Bearer` 或 `X-API-Token` |

细节取舍（都写进 `core/auth.py` 模块文档）：

- **白名单只放 `/api/health`**：探活端点。`/`、`/docs`、`/openapi.json` 也不拦 —— 拦了页面白屏，用户连"没有权限"这句话都看不到。
- **`OPTIONS` 放行**：CORS 预检不带 `Authorization`，拦了会让跨域直接失败成"后端不可用"，是最难查的假故障。
- **中间件注册顺序**：Starlette 里后 add 的在更外层，所以鉴权先注册、CORS 后注册。反了的话 401 响应不带 CORS 头，浏览器报成 CORS 错误。
- **`hmac.compare_digest`**：避免逐字节时间侧信道。零成本的习惯。
- **错误分「没带」与「带错」**：只报状态码，调试只能靠猜；但不能回显期望 token 的任何片段（探针 C9 专门断言这点）。

### 2.3 前端接入

```
/?token=<token>     # 首次带进来，之后记 localStorage['gc.api.token']
/?api=off           # 优先级最高，鉴权态下同样生效（回滚开关不能被新功能吃掉）
```

## 3. 两个当场抓到的缺陷

### 3.1 `denied` 状态从来不可能出现

原设计：health 返回 401 → 标 `denied`。但 `/api/health` 在鉴权白名单里，**永远 200**。
于是没 token 时：health 成功 → 探测通过 → 31 个行情请求全 401 → `fail > ok` → 判成 `degraded`（数据降级）。

后果不只是标签错了：**"没权限"和"上游坏了"变成同一件事**，排查会从错误方向开始。
修法：`syncAll` 里单独统计 401 次数，`denied === fail` 时才标 `denied`。

> 探针 D1 是在这次修改之前就写好的（期望 `denied`），它一跑就红 —— 说明预期写对了，实现没跟上。

### 3.2 断言整文件搜关键词会误判

`A17 Dockerfile 不带 --reload` 第一版是全文 `includes('--reload')`，结果被我自己**解释为什么不用 `--reload`** 的注释判红。写清楚理由反而让测试失败，这会逼人删注释。

修法：只检查 `CMD` 那一行。已写进 `CONVENTIONS.md` §9.3。

## 4. 刻意不做：数据持久化

持仓/交易仍在 `localStorage`，后端零写入。理由：

没有账号体系就收私人持仓上云，等于凭空造一个"你的数据在我这、但你可能看不到"的承诺。代价是换设备看不到持仓。

因此对外表述的边界是：**不说"云端持仓"、不说"多端同步"**。这条写进了 `backend/README.md`。

## 5. 验证记录

| 项 | 结果 |
|---|---|
| `verify-deploy.js` | **51/51**（制品静检 20 / 开发态 5 / 鉴权态 16 / 前端真实接入 10） |
| `verify-api-bridge.js` | 18/18（回归，改动未破坏同源/离线两态） |
| `probe-selftest.js` | 自检 **55/55** |
| `verify-orphan-holding.js` | 52/52 |
| `verify-pf-parity.js` | 14/14 |
| `verify-diag-source.js` | 48/48 |
| 前后端数值一致性 | 序列 4 标的 × 1300 根 最大相对误差 **7.80e-15**；K 线 30/30 组 **5.25e-15** |

关键实测：带 token 打开 `/?token=…` → `data-data-source="server"`、`QF_API.synced=31`、`failed=0`、`CURATED[0]._src==='api'`（证明真走了后端，不是数值巧合）。

## 6. 仍未解决（不隐瞒）

1. **线上仍是旧版**：`SITES_ACCOUNT_MISMATCH`，应用属另一账号。代码侧无需改动，切回原账号后同一目录重新发布即可，链接不变。
2. **无限流**：token 泄露后可以无限刷。QuantFlow 是 60 次/分钟。
3. **无 MCP 端点**：那是另一个量级的工程，且要先有稳定的只读接口面。
4. **数据仍是模拟**：这不是"没做完"，是产品定位。接真实行情要同步改掉前端所有标注，不能悄悄换源。
