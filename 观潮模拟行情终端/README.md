# 观潮 · 模拟行情终端

一个「单文件前端 + FastAPI 后端」的行情终端演示项目：前端 `index.html` 里是完整的
行情看板（自选、K 线、板块、持仓、诊断），后端提供与其**数值逐位一致**的行情/K 线 API。

> **数据声明**：所有价格都是**本地确定性模拟序列**（同一个标的永远得到同一组数据），
> 不是真实行情。`/api/health` 里逐项声明 `data_is_simulated: true`，前端也标注了「模拟」。
> 接真实数据是产品决策，必须同步修改全部标注，不允许悄悄换源。

---

## 快速开始

### 只看前端（零依赖）

直接用浏览器打开 `index.html`。没有后端时自动走本地 `genSeries()` 离线回退，
功能完整，数据同样是模拟的。

### 带上后端

```bash
# 1) 依赖（版本钉死，换版本要重跑一致性测试）
python -m pip install -r backend/requirements.txt

# 2) 从 index.html 抽取标的资产（首次或前端 UNIVERSE 变更后执行）
node backend/scripts/extract_universe.js

# 3) 启动（在项目根目录）
python -m uvicorn backend.app.main:app --reload --port 8000
```

| 地址 | 内容 |
|---|---|
| http://127.0.0.1:8000/ | 前端页面（同源，自动接入后端） |
| http://127.0.0.1:8000/docs | Swagger UI |

可选鉴权：设环境变量 `ACCESS_TOKEN` 后，除 `/api/health` 外全部要求
`Authorization: Bearer <token>`；不设则是开发模式，`/api/health` 会明说 `auth.mode="off"`。
前端接入带 token 用 `?token=xxx` 或 `localStorage['gc.api.token']`。

---

## 目录结构

```
观潮模拟行情终端/
├── index.html            单文件前端（样式、数据、看板全在里面）
├── backend/              FastAPI 服务：行情 / K 线 / health
│   ├── app/providers/    确定性序列生成（从 JS 逐行翻译）
│   ├── app/services/     区间切片、周月聚合、均线
│   └── tests/            与前端真实源码产出的一致性测试
├── deliverables/gstack/  评估报告与回归探针（verify-*.js / probe-*.js）
├── CHANGELOG.md          每一轮做了什么、抓到哪些缺陷
├── CONVENTIONS.md        口径约定：每条都对应一个真实发生过的缺陷
├── Procfile / render.yaml / backend/Dockerfile    三种部署入口
└── backend/.env.example  环境变量清单（无真实值，可直接照抄）
```

---

## 测试

```bash
node backend/tests/parity_gen.js index.html backend/tests/parity_js.json
python backend/tests/test_parity.py          # 序列：4 标的 × 1300 根

node backend/tests/parity_kline_gen.js index.html backend/tests/parity_kline_js.json
python backend/tests/test_parity_api.py      # 接口：3 标的 × 10 组区间/周期
```

前后端一致性实测最大相对误差 7.8e-15（K 线 30/30 组通过），表述上应说「一致到 1e-12」，
不要说「逐字节相同」。

---

## 怎么读这个项目

先读 `CONVENTIONS.md`——它不是设计原则清单，而是把踩过的坑写成可执行断言：
一条数据一个来源、缺失就说缺失不补 0、平盘不算涨、聚合权重必须写明……
再读 `CHANGELOG.md` 看这些约定各自对应哪次缺陷。
`deliverables/gstack/` 下是当时的评估报告与回归探针，换台机器也能自证。
