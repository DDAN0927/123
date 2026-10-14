# 🧳 旅游智能助手 Travel Copilot

一支会深度思考的 AI 旅行顾问团队：行程规划、景点攻略、美食探店、天气与预算分析，一句话问出完整攻略。

## ✨ 功能

- 🤝 **多 Agent 协作** — 调度中心智能路由，行程规划师 / 景点顾问 / 美食顾问 / 数据分析师 / 旅行咨询师按需接力；聊天页实时展示**协作轨迹**（谁被调度、为什么、是否完成）
- 🧠 **深度思考** — 基于 DeepSeek Reasoner，回答前先推理；思考过程可在聊天页「🧠 思考过程」面板中展开查看
- 📚 **攻略知识库** — RAG 检索（BGE 向量 + FAISS），支持管理员上传自己的攻略文档
- 🌦️ **真实天气** — 接入 open-meteo 实时预报，覆盖 20 个热门城市
- 💬 **会话管理** — 历史会话列表、恢复继续追问、⭐收藏、👍/👎反馈、一键导出 Markdown
- 🗺️ **地图与路线** — 高德地图景点分布（**355 城 / 1500+ 景点**，含 44 城的美食街与夜市，城市下拉框按拼音首字母分组）、驾车/步行/公交路线规划、跨城路线与出行建议，支持自然语言筛选（如「北京三日游，喜欢历史古迹」「想找小吃夜市」）
- ✏️ **景点可自维护** — 地图页右侧列表支持**自己添加 / 删除景点**（本地保存，可一键恢复默认），自定义景点同样参与自然语言筛选与「必去」命中
- 📊 **运营看板** — 会话/消息统计、各专家调用分布、注册用户使用情况（仅管理员）

## 🚀 使用

直接在对话框输入旅行需求，例如：

- 规划北京 3 天行程，预算 3000 元
- 成都 3 天有哪些必吃的美食？
- 十一去西安天气怎么样，预算多少？

默认管理员账号：`admin` / `123456`（在 `.env` 中用 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 覆盖，**上线前请务必改成强密码**）。

> 改密码有个坑：管理员账号只在**首次启动**时创建，之后改 `.env` 不会覆盖已存在的密码。已有环境请用：
>
> ```bash
> python scripts/admin_password.py --local  <新密码>            # 本地 data/users.json
> python scripts/admin_password.py --remote <站点地址> <新密码>  # 已发布站点（走改密接口）
> ```
>
> 线上模式省略旧密码时会自动从 `deploy/.env` 读取，改完还会用新密码复核登录。

## 🛠️ 技术栈

FastAPI · LangGraph · DeepSeek（reasoner + chat）· RAG（BGE-small-zh + FAISS）· 原生 JS 静态前端 · 高德地图 JS API

## 🏃 本地运行

```bash
# 1. 准备依赖
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS / Linux

# 2. 配置环境变量（复制模板后填入自己的 Key）
cp .env.example .env

# 3. 构建知识库索引（首次需要下载 BGE 向量模型）
python scripts/build_kb.py

# 4. 启动（官网静态站挂在 /，API 在 /api）
python -m uvicorn app.main:app --host 127.0.0.1 --port 7860
```

访问 <http://127.0.0.1:7860/>。

> 若本机设置了 HTTP 代理，用 curl 访问本地服务时需加 `--noproxy '*'`。

## ✅ 自测

```bash
# 后端接口冒烟测试（临时数据目录 + mock 模型，离线、零成本）
python scripts/smoke_test.py

# 前端 Markdown 渲染器校验（表格 / 列表 / XSS 转义）
node scripts/md_render_check.js

# 前端 DOM 集成校验（需 jsdom）：导航注入、移动端菜单、聊天页渲染、点赞索引归属
NODE_PATH=<node_modules> node scripts/dom_check.js

# 高德地图模板校验（需 jsdom）：容器高度、安全密钥注入顺序、加载失败兜底、注入转义
NODE_PATH=<node_modules> node scripts/map_check.js

# 城市选择器校验（需 jsdom）：首字母分组、最长匹配、别名落点、交通页、景点增删、geo-data 数据质量
NODE_PATH=<node_modules> node scripts/city_check.js
```

## 🔑 改管理员密码

```bash
# 本地：直接重置 data/users.json 里 admin 的密码哈希
python scripts/admin_password.py --local <新密码>

# 线上：调用 /api/auth/change-password（旧密码省略时从 deploy/.env 读取）
python scripts/admin_password.py --remote https://<你的站点地址> <新密码>
```

## 🔒 权限模型

| 接口 | 权限 |
| --- | --- |
| `/api/chat*`、`/api/agents` | 匿名可用（受匿名限流；会话历史相关需登录） |
| `/api/favorites*` | 需登录，且仅能读写**自己**的收藏 |
| `/api/knowledge*` | 需**管理员**（列表 / 上传 / 删除 / 重建索引） |
| `/api/admin*` | 需**管理员**（含开通账号 `/api/admin/users`） |

## 🛡️ 公网部署加固

真实 LLM 额度一旦公网暴露就容易被刷，因此默认做了限流保护（全部可在 `.env` 中调整）：

| 开关 | 默认 | 作用 |
| --- | --- | --- |
| `ALLOW_REGISTRATION` | `true` | 任何人可自助注册。设为 `false` 则关闭注册，新账号只能由管理员在「运营管理」页开通 |
| `RATE_LIMIT_ANONYMOUS_PER_MINUTE` | `2` | 匿名访客每个 IP 每分钟的对话上限 |
| `RATE_LIMIT_PER_MINUTE` | `6` | 登录用户每个 IP 每分钟的对话上限 |
| `RATE_LIMIT_GLOBAL_PER_MINUTE` | `20` | **全局硬上限**：即使伪造 `X-Forwarded-For` 轮换 IP 也绕不过 |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `10` | 登录 / 注册尝试上限，防暴力破解 |

管理员可用 `GET /api/admin/ratelimit` 查看当前限流配置与各窗口占用情况。

> ⚠️ 开放注册时，**限流就是唯一的额度防线**：任何注册成功的人都能在 6 次/分钟（每 IP）的额度内消耗你的 API Key，
> 全局上限 20 次/分钟是最终兜底。若要彻底收紧，把 `ALLOW_REGISTRATION` 改为 `false` 即可。
>
> 发布包（`deploy/`）的 `ALLOW_REGISTRATION` 跟随本地 `.env`（见 `scripts/build_deploy.py`）。

## 📁 目录结构

```
app/
  agents/       LangGraph 多 Agent 协作图、调度中心与 5 位专家
  api/          对话 / 认证 / 收藏 / 知识库 / 运营管理接口（含鉴权依赖）
  rag/          FAISS 索引构建与检索
  tools/        天气、预算、知识库检索工具
  store.py      会话 / 收藏 / 用户 / 统计的持久化
frontend/static/  官网与功能页静态站点（由 FastAPI 挂载于 /）
  assets/img/     本地配图（9 张渐进式 JPEG，站点无外部图床依赖）
  assets/js/      app.js（交互与地图模板）/ geo-data.js（355 城地理数据）/ main.js
frontend/streamlit_app.py  早期 Streamlit 版前端（**已停用**，当前仅作实现参考，不参与运行与部署）
knowledge_base/   内置攻略文档（北京 / 上海 / 成都 / 杭州 / 西安 / 重庆）
scripts/          索引构建、部署打包与自测脚本
```

## 📝 变更记录

见 [CHANGELOG.md](./CHANGELOG.md)。
