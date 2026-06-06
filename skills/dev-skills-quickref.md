# 开发 Skills 技能速查表

> **版本**: v2.1 | **完整版**: [dev-skills-complete.md](./dev-skills-complete.md)

---

## 技能总览

| 部门 | 岗位 | 核心技能数 | 关键技能 |
|------|------|-----------|----------|
| **技术研发部** | | | |
| | 前端开发 | 30+ | React, Vue, Next.js, TypeScript, Tailwind CSS, Vite |
| | 后端开发 | 28+ | Node.js/Python/Java/Go, RESTful/GraphQL, PostgreSQL, Redis, Kafka |
| | 移动端开发 | 16+ | Swift/Kotlin/ArkTS, React Native, Flutter, 推送+离线 |
| | 全栈开发 | 12+ | T3 Stack, BaaS(Supabase), Serverless, tRPC |
| | 测试工程师 | 15+ | Jest/Vitest, Playwright/Cypress, TDD, k6性能测试 |
| | 运维工程师 | 22+ | Docker, K8s, GitHub Actions, Terraform, Prometheus+Grafana |
| | 架构师 | 14+ | 高并发/高可用架构, DDD, 微服务, 技术选型方法论 |
| | 数据库工程师 | 18+ | PostgreSQL, MySQL, MongoDB, Redis, ES, 备份恢复优化 |
| **产品&设计部** | | | |
| | 产品经理 | 14+ | PRD撰写, Axure/Figma原型, 用户故事地图, 数据分析 |
| | UI设计师 | 16+ | Figma, 色彩排版, Design System, 品牌VI, 设计交付 |
| | UX交互设计师 | 14+ | 用户研究, 可用性测试, 信息架构, 微交互, 无障碍(a11y) |
| | 平面/品牌设计 | 14+ | LOGO设计, VI系统, 海报/Infographic, AI图像生成 |
| **AI驱动开发工作流** | | | |
| | 项目级(7个Skill) | 7 | 需求澄清→产品概述→技术栈→目录结构→开发规范→路线图→项目初始化 |
| | 功能级(5个Skill) | 5 | 功能需求澄清→技术方案→任务规划→编码实现→功能迭代变更 |
| | 通用(1个Skill) | 1 | BUG修复工作流(复现→定位→修复→测试→验证→报告) |
| **AI智能体角色库** | | | |
| | 17部门 | 215 | 工程35/营销36/专项46/游戏20/设计8/金融8/销售8/测试9/支持7/付费媒体7/产品5/项目6/空间6/学术6/供应链4/HR2/法务2 |

---

## 一、技术研发部速查

### 1.1 前端开发

```
前端开发
├── 核心框架
│   ├── React          → [react.dev](https://react.dev) | Hooks + Redux/Zustand
│   ├── Vue.js         → [vuejs.org](https://vuejs.org)  | Composition API + Pinia
│   ├── Next.js        → [nextjs.org](https://nextjs.org) | SSR/SSG + App Router
│   └── Svelte/SvelteKit → [svelte.dev](https://svelte.dev)
├── 语言基础
│   ├── TypeScript     → 类型体操 / 泛型 / 工具类型
│   └── ES6+           → async/await / Modules / Proxy
├── CSS方案
│   ├── Tailwind CSS   → [tailwindcss.com](https://tailwindcss.com) ⭐推荐
│   ├── SCSS/Sass      → 7-1架构 / Mixin
│   └── 响应式布局      → Flexbox / Grid / Container Queries
├── 工程化
│   ├── Vite           → [vitejs.dev](https://vitejs.dev) ⭐推荐
│   ├── Webpack 5      → Module Federation
│   └── Monorepo       → pnpm workspace + Turborepo
├── 跨平台
│   ├── 微信小程序      → WXML/WXSS + 云开发
│   ├── uni-app        → Vue语法多端
│   └── H5移动端       → Vant + 视口适配
├── 状态管理
│   ├── Redux Toolkit  → RTK Query
│   ├── Zustand/Pinia  → 轻量级
│   └── TanStack Query → 服务端状态
└── 性能优化
    ├── Core Web Vitals → LCP/FID/CLS
    ├── 代码分割        → Dynamic Import
    └── 图片优化        → AVIF/WebP + CDN
```

### 1.2 后端开发

```
后端开发
├── 编程语言与框架
│   ├── Node.js        → NestJS(企业级) / Fastify(高性能)
│   ├── Python         → FastAPI(异步) / Django(全栈)
│   ├── Java           → Spring Boot 3 + Spring Cloud
│   ├── Go             → Gin/Echo + gRPC
│   └── Rust           → Actix/Axum (极致性能)
├── API设计
│   ├── RESTful        → OpenAPI/Swagger文档
│   ├── GraphQL        → Apollo Server
│   ├── gRPC           → Protocol Buffers
│   └── WebSocket/SSE  → Socket.io 实时通信
├── 数据库
│   ├── SQL            → PostgreSQL(首选) / MySQL
│   ├── ORM            → Prisma / Drizzle / SQLAlchemy
│   ├── Redis          → 缓存/会话/队列
│   └── MongoDB        → 文档数据库
├── 认证授权
│   ├── JWT/OAuth 2.0  → Token认证标准
│   ├── Session        → Redis分布式Session
│   └── RBAC/ABAC      → Casbin权限引擎
├── 消息队列
│   ├── RabbitMQ       → AMQP可靠消息
│   ├── Kafka          → 高吞吐流处理
│   ├── BullMQ         → Redis任务队列(Node)
│   └── Celery         → Python任务队列
└── 微服务/分布式
    ├── 服务发现       → Consul / Nacos
    ├── API网关        → Kong / APISIX
    ├── 分布式事务     → Seata / Saga模式
    └── 链路追踪       → Jaeger / SkyWalking
```

### 1.3 移动端开发

```
移动端开发
├── 原生开发
│   ├── iOS (Swift)    → SwiftUI + Combine
│   ├── Android(Kotlin)→ Jetpack Compose + MVVM
│   └── 鸿蒙(ArkTS)    → ArkUI + Stage模型
├── 跨平台
│   ├── React Native   → Expo + Reanimated ⭐JS生态
│   ├── Flutter        → Dart + Riverpod
│   ├── Capacitor      → Web技术包装原生
│   └── uni-app App端  → nvue + 原生插件
└── 移动专项
    ├── 推送通知       → FCM/APNs/厂商通道
    ├── 离线同步       → SQLite + CRDT
    ├── 性能监控       → Sentry / Firebase
    └── 商店上架       → App Store / Google Play / 华为
```

### 1.4 全栈开发

```
全栈开发
├── 全栈组合
│   ├── MERN Stack     → Mongo+Express+React+Node
│   ├── T3 Stack       → Next+tRPC+Prisma+Tailwind ⭐推荐
│   ├── BaaS           → Supabase / Firebase / Appwrite
│   └── Serverless     → Vercel Edge / Cloudflare Workers
└── 最佳实践
    ├── 端到端类型安全  → tRPC + Zod
    ├── 项目架构       → 分层架构 / Clean Architecture
    └── 快速原型能力   → Vercel + Supabase + Clerk + Stripe
```

### 1.5 测试工程师

```
测试工程师
├── 自动化测试框架
│   ├── 单元测试       → Jest / Vitest + Testing Library
│   ├── 组件测试       → Cypress CT / Storybook
│   ├── E2E测试        → Playwright ⭐推荐 / Cypress
│   └── API测试        → Postman/Newman / Rest Assured
├── 测试方法论
│   ├── TDD            → Red-Green-Refactor
│   ├── BDD            → Cucumber/Gherkin
│   ├── 性能测试        → k6 / JMeter / Locust
│   └── 安全测试        → OWASP ZAP / Burp Suite
└── 测试基础设施
    ├── CI/CD集成      → GitHub Actions + Allure Report
    ├── 测试数据        → Faker / Test Containers
    └── 缺陷管理        → Jira / Sentry
```

### 1.6 运维工程师

```
运维工程师
├── 容器化编排
│   ├── Docker         → Dockerfile + Compose + 多阶段构建
│   └── Kubernetes     → Pod/Deployment/Service/Ingress/Helm
├── 云服务
│   ├── 阿里云          → ECS/OSS/RDS/SLB/CDN
│   ├── AWS            → EC2/S3/Lambda/CloudFront
│   └── 边缘计算        → Cloudflare Workers / Vercel Edge
├── CI/CD部署
│   ├── GitHub Actions  → Workflows + Matrix + Caching
│   ├── GitOps          → ArgoCD / Flux
│   └── 发布策略         → 蓝绿/金丝雀/灰度
├── 监控可观测性
│   ├── 日志           → ELK / Loki + Grafana
│   ├── 指标           → Prometheus + Grafana
│   ├── 链路追踪        → Jaeger / OTel
│   └── APM            → Sentry / Datadog
└── IaC
    ├── Terraform      → 多云资源管理
    ├── Ansible        → 配置管理
    └── Pulumi         → 编程语言写IaC
```

### 1.7 架构师

```
架构师
├── 系统设计方法
│   ├── 高并发         → 负载均衡/缓存/分库分表/流量漏斗
│   ├── 高可用(HA)     → 多活/熔断降级/Chaos Engineering
│   ├── 分布式理论      → CAP/BASE/Raft/Paxos
│   └── DDD            → 限界上下文/聚合根/CQRS
├── 架构模式
│   ├── 微服务         → API Gateway/BFF/Strangler Fig
│   ├── 事件驱动(EDA)   → Event Sourcing/CQRS/Outbox
│   ├── Serverless     → FaaS+BaaS/Scale-to-zero
│   └── 云原生          → 12-Factor/Service Mesh
└── 技术选型
    ├── 选型方法论      → Technology Radar / ADR
    ├── 性能基准        → TechEmpower / AB测试
    └── 安全架构        → Zero Trust/IAM/等保合规
```

### 1.8 数据库工程师

```
数据库工程师
├── 关系型
│   ├── PostgreSQL     → JSONB/全文搜索/扩展 ⭐首选
│   ├── MySQL          → InnoDB/MGR集群
│   └── SQL Server/Oracle → 企业级
├── NoSQL
│   ├── MongoDB        → 文档型/聚合管道/分片
│   ├── Redis          → 内存KV/Module/Cluster
│   ├── Elasticsearch  → 搜索引擎/日志分析
│   └── ClickHouse/Doris → OLAP分析
└── 运维
    ├── 备份恢复        → WAL归档/PITR
    ├── 读写分离/分库分表 → ShardingSphere/Vitess
    ├── 慢查询优化      → EXPLAIN ANALYZE/索引策略
    └── 监控            → PMM/Prometheus Exporter
```

---

## 二、产品&设计部速查

### 2.1 产品经理

```
产品经理
├── 需求分析
│   ├── 需求挖掘        → 用户访谈/竞品分析/用例图
│   ├── PRD撰写        → 结构化需求/验收标准
│   ├── 用户故事地图    → Story Mapping/INVEST原则
│   └── 数据决策        → SQL/埋点/A-B Test
├── 原型工具
│   ├── Axure RP       → 专业原型/动态面板
│   ├── Figma          → 协作原型/组件库
│   └── 墨刀/MasterGo  → 国产协作
└── 产品运营
    ├── 路线图          → Roadmap/OKR/MoSCoW
    ├── 竞品分析        → SWOT/差异化定位
    ├── 增长策略        → AARRR模型/留存曲线
    └── 文案内容        → Landing Page/Onboarding文案
```

### 2.2 UI设计师

```
UI设计师
├── 设计基础
│   ├── 色彩配色        → 60-30-10法则/无障碍色/深色模式
│   ├── 排版字体        → 字体配对/层级系统/Variable Font
│   ├── 图标插画        → SVG/图标系统/品牌插画风格
│   └── 栅格布局        → 8pt栅格/原子设计/间距系统
├── 设计工具
│   ├── Figma          → Components/Variants/Dev Mode ⭐核心
│   ├── Sketch         → Symbols/Libraries(Mac)
│   ├── Adobe PS/AI/AE → 创意套件
│   └── Framer/Principle → 高保真动效原型
└── 设计体系
    ├── Design System   → Atomic Design/Style Guide
    ├── Tailwind DS     → Config/Tokens/代码同步
    ├── VI品牌识别      → Logo/辅助图形/规范手册
    └── 设计交付        → Dev Mode/Zeplin/自动切图
```

### 2.3 UX交互设计师

```
UX交互设计师
├── 用户研究
│   ├── 用户画像        → Persona/JTBD/用户分层
│   ├── 可用性测试      → moderated/unmoderated/热力图
│   ├── A/B测试设计     → 统计显著性/多变量测试
│   └── 卡片分类        → IA验证/树状测试
├── 交互设计
│   ├── 信息架构(IA)    → 站点地图/导航/搜索
│   ├── 交互流程        → User Flow/状态机/异常流程
│   ├── 微交互          → Loading/手势/触觉反馈
│   └── 无障碍(a11y)    → WCAG 2.1/键盘导航/屏幕阅读器
└── 体验度量
    ├── HEART/GSM      → Happiness/Engagement/Retention
    ├── NPS/CSAT/CES   → 满意度测量
    └── 会话录制/热图   → Hotjar/FullStory/行为挖掘
```

### 2.4 平面/品牌设计

```
平面/品牌设计
├── 品牌设计
│   ├── LOGO设计        → 字标/图形/缩放测试
│   ├── VI系统          → 基础+应用系统/手册编制
│   ├── 品牌延展        → 包装/周边/空间导视
│   └── 品牌策略        → 品牌金字塔/Tone of Voice
├── 平面设计
│   ├── 海报/Banner     → 主视觉KV/社交媒体图
│   ├── Infographic     → 数据可视化图表
│   ├── Landing Page    → 转化优化LP设计
│   └── PPT演示         → Keynote/模板/动效演示
└── 创意/AI辅助
    ├── AI图像生成      → Midjourney/SD/ComfyUI
    ├── 漫画插画风      → 扁平/3D/像素风
    ├── 算法艺术        → Processing/p5.js/TD
    └── 印刷输出        → CMYK/出血/特殊工艺
```

---

## 快速检索：按场景查找技能

### 🚀 启动新项目时必查

| 场景 | 推荐技能组合 |
|------|-------------|
| **Web前端新项目** | Next.js + TypeScript + Tailwind CSS + Prisma + tRPC (T3 Stack) |
| **小程序项目** | uni-app(Vue3) + uView + 云开发 或 Taro(React) + NutUI |
| **移动App** | React Native + Expo 或 Flutter + Riverpod |
| **后端API服务** | NestJS(TypeScript) 或 FastAPI(Python) + PostgreSQL + Redis |
| **快速MVP验证** | Supabase(BaaS) + Vercel(部署) + Next.js + Clerk(认证) |
| **SaaS全栈** | Next.js + Stripe + Auth0 + Postgres + Resend(邮件) |

### 🔧 解决具体问题时

| 问题 | 相关技能 |
|------|---------|
| **首屏加载慢** | Core Web Vitals → 代码分割 → 图片优化 → CDN → SSR/ISR |
| **接口响应慢** | EXPLAIN分析 → 索引优化 → Redis缓存 → 查询优化 → 读写分离 |
| **并发量暴涨** | 负载均衡 → 水平扩展 → 消息队列削峰 → 缓存预热 → 限流降级 |
| **跨端兼容问题** | 条件编译 → Polyfill → Babel配置 → 渐进增强策略 |
| **用户体验差** | 可用性测试 → 热力图分析 → 微交互优化 → A/B Test验证 |

---

## 三、免费 API 速查

### 3.1 Mock / 测试模拟

```
Mock / 测试模拟类 API
├── JSONPlaceholder  → https://jsonplaceholder.typicode.com/  | 完全免费无限制 | CRUD/列表/表单测试
├── ReqRes           → https://reqres.in/                     | 完全免费无限制 | 登录认证/分页/CRUD模拟
├── MockAPI.io       → https://mockapi.io/                    | 免费3项目无限请求 | 自定义业务接口Mock
├── httpbin          → https://httpbin.org/                   | 完全免费无限制 | HTTP请求全场景测试
└── Mockoon          → https://mockoon.com/                   | 开源免费本地部署 | 离线Mock/GraphQL模拟
```

### 3.2 全栈基础工具

```
基础工具类 API
├── TimeAPI          → https://www.timeapi.io/                 | 完全免费 | 时间校准/时区/节假日
├── IPAPI.co         → https://ipapi.co/                      | 免费无限制+CORS | IP定位/归属地/风控
├── TenAPI           → https://tenapi.cn/                     | 国内免费 | 二维码/短信/天气/快递/短链
├── UUID Generator   → https://www.uuidtools.com/api          | 完全免费 | UUID v1/v3/v4/v5批量生成
└── 企业信用API       → https://www.gsxt.gov.cn/api-mgr.html  | 官方免费 | 企业认证/资质核验
```

### 3.3 AI 大模型 / 多模态 ⭐

```
免费 AI API (2026年稳定可用)
├── Google Gemini    → https://ai.google.dev/                 | 永久免费层 60次/分 1500次/天 | 多模态/Agent/代码生成
├── Mistral          → https://console.mistral.ai/            | 永久免费 200万Token/月 | 代码生成/推理/Codestral
├── DeepSeek         → https://platform.deepseek.com/         | 注册送500万Token 国内直连 | 代码审查/生成/技术问答
├── 通义千问          → https://tongyi.aliyun.com/            | 免费100万Token/月 | 中文AI/代码/多模态
├── Tavily Search    → https://tavily.com/                    | 免费1000次/月 | AI Agent搜索/RAG/知识库
├── 火山方舟(豆包)    → https://www.volcengine.com/ark         | 每日200万Token 国内直连 | 中文AI/自动化/多模态
└── HuggingFace      → https://huggingface.co/docs/api-inference | 免费无限(限速) | 10万+开源模型/LLM/CV/NLP
```

### 3.4 业务数据

```
业务数据 API
├── 高德地图          → https://lbs.amap.com/                 | 30万次/天免费 | 国内LBS首选
├── 百度地图          → https://lbsyun.baidu.com/             | 永久免费额度 | 百度生态/室内定位
├── OpenWeather      → https://openweathermap.org/api         | 60次/分 100万次/月 | 全球天气
├── 和风天气          → https://dev.qweather.com/             | 3000次/天免费 | 国内天气中文优化
├── TMDB             → https://www.themoviedb.org/documentation/api | 5万次/天免费 | 全球影视全量数据
├── TuShare          → https://tushare.pro/                   | 永久免费 | A股/港股/美股行情
├── NewsAPI          → https://newsapi.org/                   | 100次/天免费 | 全球新闻聚合
└── 聚合数据          → https://www.juhe.cn/                  | 790+API免费测试 | 快递/手机/违章一站式
```

### 3.5 多媒体处理

```
多媒体 API
├── Cloudinary       → https://cloudinary.com/                | 25GB存储+带宽/月 | 图片压缩/裁剪/水印/CDN
├── 百度OCR          → https://cloud.baidu.com/product/ocr    | 1000次/月免费 | 文字/证件/票据识别
├── Edge-TTS         → https://github.com/rany2/edge-tts      | 完全开源免费 | 多语种语音合成
├── Imgur            → https://apidocs.imgur.com/             | 免费无严格限制 | 图床/图片分享
└── Remove.bg        → https://www.remove.bg/api              | 50次/月免费 | 自动抠图/背景移除
```

### 3.6 第三方登录 / OAuth

```
OAuth / 第三方登录 API
├── GitHub OAuth     → 完全免费无限制 | 技术网站/开源工具首选
├── 微信开放平台       → 基础功能免费 | 国内APP/小程序必备
├── QQ互联           → 完全免费 | 年轻用户群体适配
├── Google OAuth 2.0 → 完全免费无限制 | 海外项目/跨境必备
└── 抖音开放平台       → 免费基础额度 | 短视频/内容/电商
```

### 3.7 运维 / 安全工具

```
运维 / 安全 API
├── GitHub API       → 5000次/小时免费 | DevOps/代码管理
├── SSL Labs         → 完全免费 | SSL证书检测/安全评级
├── VirusTotal       → 500次/天免费 | 文件/URL安全检测
├── Ping.pe          → 免费可用 | 全球节点ping/端口检测
└── Cloudflare DNS   → 免费完全可用 | DNS管理/DDOS防护
```

### 3.8 免费云服务 / 部署平台

```
免费云平台
├── Cloudflare       → 永久免费 | CDN+DNS+Workers+KV+R2
├── Vercel           → 永久免费 | 前端部署+Serverless+CDN
├── 阿里云           → 新用户免费 | ECS+RDS+OSS+函数计算
├── 腾讯云           → 新用户免费 | 云服务器+CDN+COS+AI
└── AWS Free Tier    → 12个月免费 | EC2+S3+Lambda+RDS
```

### 3.9 API 聚合大全

```
一站式免费 API 平台
├── Public APIs          → https://publicapis.org/                          | 全球最大免费API合集
├── RapidAPI 免费专区     → https://rapidapi.com/collection/free-apis       | 按分类浏览
├── Any-API              → https://any-api.com/                            | 带示例代码 新手友好
└── awesome-free-apis    → https://github.com/codiebyheaart/awesome-free-apis | GitHub社区维护
```

---

## 快速检索：按开发场景查找 API

### 🎯 开发场景 → API 推荐

| 开发场景 | 推荐 API |
|---------|---------|
| **前端联调/接口测试** | JSONPlaceholder(基础CRUD) + ReqRes(认证分页) + Mockoon(离线Mock) |
| **IP定位/地域限制** | IPAPI.co(前端直调+CORS) + 高德地图(精确定位) |
| **AI代码生成** | DeepSeek(国内直连) + Gemini(多模态) + Mistral(Codestral) |
| **AI Agent/RAG** | Tavily Search(实时搜索) + HuggingFace(开源模型) + 火山方舟(国内) |
| **地图/LBS应用** | 高德地图(国内首选) + 百度地图(备选) |
| **天气类应用** | 和风天气(国内) + OpenWeather(全球) |
| **影视/内容平台** | TMDB(影视数据) + NewsAPI(新闻资讯) |
| **金融/量化** | TuShare(A股/港股/美股) |
| **图片处理/图床** | Cloudinary(全功能) + Imgur(简单图床) + Remove.bg(抠图) |
| **OCR/文字识别** | 百度智能云OCR(1000次/月免费) |
| **语音合成** | Edge-TTS(完全免费开源) |
| **第三方登录** | GitHub(技术站) + 微信(国内) + Google(海外) |
| **SSL/安全检测** | SSL Labs(证书评级) + VirusTotal(文件/URL安全) |
| **项目部署** | Vercel(前端) + Cloudflare(边缘) + 阿里云(国内全栈) |
| **找API** | Public APIs(全球合集) + RapidAPI(分类浏览) |

---

## 四、免费数据库速查

### 4.1 关系型数据库（MySQL / PostgreSQL）

```
免费关系型数据库
├── PlanetScale      → https://planetscale.com              | 永久免费 1库无限存储查询 | MySQL协议 分支回滚 ⭐后端首选
├── Neon             → https://neon.tech                    | 永久免费 3GB存储        | PostgreSQL 连接池 休眠不扣费
└── Supabase         → https://supabase.com                 | 免费版永久够用          | PG+自带API+登录+权限+实时订阅 ⭐快速开发
```

### 4.2 NoSQL / 文档数据库

```
免费 NoSQL 数据库
├── MongoDB Atlas    → https://www.mongodb.com/atlas/database | 免费永久 512MB | 标准MongoDB 外网直连 全语言适配
└── Upstash          → https://upstash.com                     | 免费 Redis+Kafka | 低延迟 缓存/会话/限流
```

### 4.3 轻量免运维（自带 API，不用写 SQL）

```
免运维数据库
├── Vercel KV/Postgres → https://vercel.com                  | 免费额度够用 | Vercel无缝衔接 Serverless开发
├── Cloudflare D1    → https://www.cloudflare.com/zh-cn/products/d1/ | 免费SQLite | Worker直连 零成本极简 ⭐首选
└── PocketBase       → https://pocketbase.io                  | 开源免费无限制 | 单文件启动 自带后台+API+登录
```

### 4.4 国内稳定免费库

```
国内免费数据库
├── 阿里云免费数据库   → https://free.aliyun.com              | 新用户免费MySQL/PG | 国内极快 ⭐国内首选
└── 腾讯云CloudBase   → https://cloud.tencent.com/product/tcb | 免费DB+云函数+存储 | 小程序/网站开箱即用
```

---

## 快速检索：按开发场景查找数据库

### 🎯 开发场景 → 数据库推荐

| 开发场景 | 推荐数据库 |
|---------|-----------|
| **后端项目(海外)** | PlanetScale(MySQL) 或 Neon(PostgreSQL) |
| **快速MVP/小程序** | Supabase(PG+API+登录) 或 腾讯云CloudBase |
| **JSON/日志/配置存储** | MongoDB Atlas(512MB免费) |
| **缓存/会话/限流** | Upstash(Redis免费) |
| **Serverless全栈** | Vercel KV/Postgres + Cloudflare D1 |
| **极简后端(零配置)** | Cloudflare D1 + Worker 或 PocketBase(自托管) |
| **国内项目(低延迟)** | 阿里云免费MySQL/PG 或 腾讯云CloudBase |
| **微信小程序** | 腾讯云CloudBase(免费DB+云函数+存储) |

---

## 五、Public APIs 全量目录速查

> 来源: [github.com/public-apis/public-apis](https://github.com/public-apis/public-apis) + [n0shake/Public-APIs](https://github.com/n0shake/Public-APIs) | 1400+ API | 23 场景分组

```
Public APIs 场景分组
├── 🧪 Web开发/Mock    → JSONPlaceholder, ReqRes, httpbin, Mockoon
├── 🤖 AI/机器学习      → Gemini, DeepSeek, Mistral, HuggingFace, Tavily
├── 🗺️ 地图/LBS        → 高德, 百度, OpenStreetMap, IPAPI.co
├── 🌤️ 天气/环境       → OpenWeather, 和风天气, Weatherstack
├── 💰 金融/加密        → TuShare, Alpha Vantage, CoinGecko, ExchangeRate
├── 📰 新闻/内容        → TMDB, NewsAPI, HackerNews, Reddit
├── 🔐 社交/登录        → GitHub/Google OAuth, 微信, Discord, Notion
├── 🖼️ 图片/视频        → Unsplash, Cloudinary, Imgur, Remove.bg, Edge-TTS
├── 🏢 商业数据         → 聚合数据, Clearbit, Hunter.io
├── 🛠️ 开发工具         → GitHub API, npm Registry, Docker Hub
├── 🔒 安全/运维        → VirusTotal, Shodan, HaveIBeenPwned, SSL Labs
├── 🍔 生活/健康        → Open Food Facts, Spoonacular, USDA
├── 📚 教育/科学        → Wikipedia, arXiv, NASA, Open Library
├── ⚽ 体育/娱乐        → TheSportsDB, PokeAPI, Trivia, Jokes
├── 🏛️ 政府/开放数据    → Data.gov, World Bank, US Census
├── 💳 支付/电商        → Stripe, Braintree, PayPal, Commerce Layer
├── 📊 数据分析         → Google Analytics, Matomo, PostHog, MixPanel
├── 🔑 认证/验证        → Auth0, Firebase Auth, Clerk, reCAPTCHA
├── 📱 通信/推送         → Twilio, SendGrid, Resend, OneSignal
├── 📷 二维码/条码      → QR Code API, QuickChart, Google Barcode
├── 🧠 NLP/翻译         → Google NLP, DeepL, LibreTranslate, 百度NLP
├── 📸 截图/抓取         → Screenshot API, ScrapingBee, Apify
└── 📢 广告/SEO         → SerpAPI, Google Ads, Facebook Marketing
```

完整目录: [public-apis/SKILL.md](./public-apis/SKILL.md) | 结构化数据: [public-apis-catalog.json](./public-apis/public-apis-catalog.json)

---

## 六、AI驱动开发工作流速查

> 从模糊想法到可运行代码的完整开发工作流，13个Skill分三层协作
> 详细文档: [workflow/SKILL.md](./workflow/SKILL.md) | 核心机制: [GUARDRAILS.md](./workflow/GUARDRAILS.md) + [PROJECT-CONTEXT.md](./workflow/PROJECT-CONTEXT.md) | 实战技巧: [workflow-tips.md](./workflow/workflow-tips.md)

### 6.1 项目级工作流（启动时用一次）

```
项目级工作流
├── Skill 1: 需求澄清        → /project-requirements-clarification  | AI角色: 好奇的合伙人    | 输出: specs/项目描述.md
├── Skill 2: 产品概述        → /project-product-overview            | AI角色: 首席产品官      | 输出: specs/产品概述.md
├── Skill 3: 技术栈选型      → /project-tech-stack                  | AI角色: CTO             | 输出: specs/技术栈.md
├── Skill 4: 目录结构        → /project-structure                   | AI角色: 系统架构师      | 输出: specs/项目结构.md
├── Skill 5: 开发规范        → /project-dev-standards               | AI角色: 技术委员会      | 输出: specs/开发规范.md
├── Skill 6: 路线图规划      → /project-roadmap-planning            | AI角色: 技术产品经理    | 输出: specs/开发路线图.md
└── Skill 7: 项目初始化      → /project-initialization              | AI角色: DevOps工程师    | 输出: 项目骨架 + 初始化记录
```

### 6.2 功能级工作流（反复使用）

```
功能级工作流
├── Skill 8:  功能需求澄清   → /feature-requirements-clarification  | AI角色: 产品经理        | 输出: specs/features/{功能名}.md
├── Skill 9:  技术方案设计   → /feature-tech-design                 | AI角色: 系统架构师      | 输出: specs/features/{功能名}_技术方案.md
├── Skill 10: 任务规划       → /feature-task-planning               | AI角色: 技术主管        | 输出: specs/features/{功能名}_任务规划.md
├── Skill 11: 编码实现       → /feature-implementation              | AI角色: 高级开发工程师  | 输出: 代码 + 阶段报告
└── Skill 12: 功能迭代变更   → /feature-evolution                   | AI角色: 产品架构师      | 输出: 增量更新文档 + 新任务
    变更类型: 微调(Tweak) / 扩展(Extension) / 重构(Refactor)
```

### 6.3 通用工作流（随时使用）

```
通用工作流
└── Skill 13: BUG修复        → /bugfix-workflow                     | AI角色: 高级调试工程师  | 输出: 修复 + 测试 + 报告
    硬规则: 没复现出来，不准改代码
    流程: 复现 → 定位 → 修复 → 单元测试 → 验证 → 报告
```

### 6.4 核心机制

| 机制 | 说明 |
|------|------|
| 边界守卫（GUARDRAILS） | 每个Skill只做自己阶段的事，AI越界时自动拦截 |
| 项目上下文协议（PROJECT-CONTEXT） | 每个Skill执行前必须读取specs/目录下所有文档 |

---

## 七、AI 智能体角色库速查

> 来源: [agency-agents-zh](https://github.com/jnMetaCode/agency-agents-zh) | 215 角色 | 17 部门 | 50 中国市场原创
> 完整文档: [agency-agents/SKILL.md](./agency-agents/SKILL.md) | 结构化数据: [agency-agents-catalog.json](./agency-agents/agency-agents-catalog.json)

### 7.1 部门速查

```
AI 智能体角色库 (215)
├── 🛠️ 工程部         → 35 角色 | 全栈/前端/后端/移动/DevOps/架构/数据/ML/安全/嵌入式/IoT
├── 🎨 设计部         → 8 角色  | UI/UX研究/UX架构/品牌守护/图像提示词/视觉叙事
├── 📱 营销部         → 36 角色 | 小红书/抖音/微信/B站/电商/SEO/私域/出海/增长
├── 💰 付费媒体部     → 7 角色  | 广告审计/创意策略/PPC/追踪归因
├── 💼 销售部         → 8 角色  | 客户策略/售前/外联/投标
├── 🏦 金融部         → 8 角色  | 财务分析/预测/风控/发票/税务
├── 👥 人力资源部     → 2 角色  | 招聘/绩效
├── ⚖️ 法务部         → 2 角色  | 合同审查/制度撰写
├── 🚚 供应链部       → 4 角色  | 库存预测/供应商评估/路线优化
├── 📦 产品部         → 5 角色  | 产品经理/Sprint排序/趋势/反馈/行为助推
├── 📋 项目管理部     → 6 角色  | 高级PM/项目守护/实验追踪/Jira工作流
├── 🧪 测试部         → 9 角色  | API测试/性能基准/无障碍/嵌入式QA
├── 🎧 支持部         → 7 角色  | 支持响应/分析报告/法律合规
├── ⚡ 专项部         → 46 角色 | 智能体编排/提示词/MCP/文档/工作流/区块链/政务/定价
├── 🥽 空间计算部     → 6 角色  | visionOS/XR交互/XR沉浸/座舱
├── 🎮 游戏开发部     → 20 角色 | 游戏设计/Unity/Unreal/Godot/Roblox/Blender
└── 🎓 学术部         → 6 角色  | 人类学/历史/叙事学/心理学/学习规划
```

### 7.2 项目场景 → 角色组合

| 项目类型 | 推荐角色组合 |
|---------|-------------|
| **Web全栈** | 全栈开发 + UX架构师 + QA工程师 + DevOps |
| **移动APP** | 移动开发 + UI设计师 + 后端开发 + 增长黑客 |
| **SaaS产品** | 产品经理 + 全栈开发 + 售前工程师 + 赢单策略师 |
| **电商网站** | 全栈开发 + UI设计师 + 电商运营专家 + 动态定价策略师 |
| **游戏开发** | 游戏设计师 + Unity/Unreal架构师 + 技术美术 + 叙事设计师 |
| **AI应用** | ML工程师 + 提示词工程师 + MCP构建器 + 智能体编排者 |
| **国内营销** | 小红书运营 + 抖音策略师 + 私域运营 + 百度SEO |
| **出海产品** | TikTok策略师 + Instagram策展师 + 跨境电商 + 文化智能策略师 |
| **企业系统** | 系统架构师 + 后端开发 + 合同审查专家 + 金融风控分析师 |
| **硬件/IoT** | 嵌入式工程师 + 固件工程师 + IoT工程师 + 上位机工程师 |
| **XR/空间计算** | visionOS工程师 + XR界面架构师 + XR沉浸式开发者 |
| **政务项目** | 政务数字化售前 + 合同审查专家 + 制度文件撰写专家 |

---

*💡 提示: 详细描述、学习路径和资源链接请查看 [dev-skills-complete.md](./dev-skills-complete.md)*
