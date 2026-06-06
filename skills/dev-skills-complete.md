# 开发 Skills 技能体系 - 完整版

> **版本**: v2.1 | **更新日期**: 2026-05-17
> **用途**: 项目开发技能参考、团队技能评估、学习路径规划、免费API速查、免费数据库速查、Public APIs全量目录(23场景)、AI智能体角色库(215角色17部门)、AI驱动开发工作流(13个Skill)

---

## 目录

- [一、技术研发部](#一技术研发部)
  - [1. 前端开发](#1-前端开发)
  - [2. 后端开发](#2-后端开发)
  - [3. 移动端开发](#3-移动端开发)
  - [4. 全栈开发](#4-全栈开发)
  - [5. 测试工程师](#5-测试工程师)
  - [6. 运维工程师](#6-运维工程师)
  - [7. 架构师](#7-架构师)
  - [8. 数据库工程师](#8-数据库工程师)
- [二、产品&设计部](#二产品设计部)
  - [9. 产品经理](#9-产品经理)
  - [10. UI设计师](#10-ui设计师)
  - [11. UX交互设计师](#11-ux交互设计师)
  - [12. 平面/品牌设计](#12-平面品牌设计)
- [三、免费 API 资源库](#三免费-api-资源库)
  - [1. Mock / 测试模拟类 API](#1-mock--测试模拟类-api)
  - [2. 全栈高频刚需 - 基础工具类 API](#2-全栈高频刚需---基础工具类-api)
  - [3. AI 开发核心 - 免费大模型/多模态 API](#3-ai-开发核心---免费大模型多模态-api)
  - [4. 业务数据支撑 - 免费业务数据 API](#4-业务数据支撑---免费业务数据-api)
  - [5. 多媒体处理 - 免费音视频/图片 API](#5-多媒体处理---免费音视频图片-api)
  - [6. 用户体系开发 - 第三方登录/OAuth API](#6-用户体系开发---第三方登录oauth-api)
  - [7. 运维/网络开发 - 系统工具类 API](#7-运维网络开发---系统工具类-api)
  - [8. Serverless/部署 - 云服务免费平台](#8-serverless部署---云服务免费平台)
  - [9. API 聚合大全 - 一站式免费 API 平台](#9-api-聚合大全---一站式免费-api-平台)
- [四、免费数据库资源库](#四免费数据库资源库)
  - [1. 关系型数据库（MySQL / PostgreSQL）](#1-关系型数据库mysql--postgresql)
  - [2. NoSQL / 文档数据库（MongoDB 类）](#2-nosql--文档数据库mongodb-类)
  - [3. 轻量免运维（自带 API，不用写 SQL）](#3-轻量免运维自带-api不用写-sql)
  - [4. 国内稳定免费库（国内访问快）](#4-国内稳定免费库国内访问快)
- [附录](#附录)
  - [熟练度等级说明](#熟练度等级说明)
  - [技能标签索引](#技能标签索引)
  - [API 分类标签索引](#api-分类标签索引)
- [六、AI驱动开发工作流](#六ai驱动开发工作流)
  - [1. 工作流全景](#1-工作流全景)
  - [2. 核心机制](#2-核心机制)
  - [3. 项目级工作流（7个Skill）](#3-项目级工作流7个skill)
  - [4. 功能级工作流（5个Skill）](#4-功能级工作流5个skill)
  - [5. 通用工作流（1个Skill）](#5-通用工作流1个skill)
  - [6. 实战技巧](#6-实战技巧)
- [七、AI 智能体角色库](#七ai-智能体角色库)
  - [1. 角色库概览](#1-角色库概览)
  - [2. 按部门速查](#2-按部门速查)
  - [3. 项目场景→角色组合推荐](#3-项目场景角色组合推荐)

---

## 一、技术研发部

### 1. 前端开发

**岗位职责**: 网页、小程序、APP界面、H5 开发

#### 1.1 核心框架

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **React** | Facebook 出品的 UI 库，组件化开发范式 | React, JSX, Hooks, Redux/Zustand | 入门: 组件与JSX → 熟练: Hooks+状态管理 → 精通: 源码原理+性能优化 | [react.dev](https://react.dev), [vercel-react-best-practices](https://github.com/vercel/react) |
| **Vue.js** | 渐进式框架，上手快生态好 | Vue 3, Composition API, Pinia, Vue Router | 入门: 模板语法 → 熟练: 组合式API → 精通: 响应式原理+源码 | [vuejs.org](https://vuejs.org), [frontend-design](https://github.com) |
| **Next.js** | React 全栈框架，SSR/SSG 首选 | Next.js, App Router, Server Components | 入门: 页面路由 → 熟练: SSR/SSG/ISR → 精通: 边缘部署+性能调优 | [nextjs.org](https://nextjs.org), [next-best-practices](https://github.com) |
| **Nuxt.js** | Vue 全栈框架，类似 Next.js 定位 | Nuxt 3, Auto-imports, Nitro | 入门: 目录约定 → 熟练: SSR/混合渲染 → 精通: 模块系统+部署 | [nuxt.com](https://nuxt.com) |
| **Angular** | 企业级框架，TypeScript 强绑定 | Angular, RxJS, NgRx, Zone.js | 入门: 模块与组件 → 熟练: 依赖注入+路由 → 精通: 变更检测优化 | [angular.io](https://angular.io) |
| **Svelte/SvelteKit** | 编译时框架，无虚拟DOM | Svelte, SvelteKit, Svelte Stores | 入门: 响应式语法 → 熟练: SvelteKit全栈 → 精通: 编译器原理 | [svelte.dev](https://svelte.dev) |

#### 1.2 TypeScript 与 JavaScript 进阶

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **TypeScript** | JavaScript 超集，类型安全 | TS 5.x, 泛型, 类型体操, tsconfig | 入门: 基础类型 → 熟练: 泛型+工具类型 → 精通: 类型编程+声明文件 | [typescriptlang.org](https://typescriptlang.org) |
| **ES6+/现代JS** | 异步编程、模块化、解构等 | async/await, Promise, Modules, Proxy | 入门: 箭头函数/解构 → 熟练: 异步模式 → 精通: 事件循环+V8引擎 | [developer.mozilla.org](https://developer.mozilla.org) |
| **Node.js 基础** | 服务端 JS 运行时 | Node.js, npm/yarn/pnpm, nvm | 入门: 包管理 → 熟练: 流/缓冲区 → 精通: C++插件+性能分析 | [nodejs.org](https://nodejs.org) |

#### 1.3 CSS 与样式方案

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **Tailwind CSS** | 原子化 CSS 框架，效率极高 | Tailwind CSS, JIT, 自定义配置 | 入门: 工具类使用 → 熟练: 自定义主题 → 精通: 设计系统构建 + 插件开发 | [tailwindcss.com](https://tailwindcss.com), [tailwind-design-system](https://github.com) |
| **SCSS/Sass** | CSS 预处理器，嵌套/变量/混入 | Sass, Dart Sass, 7-1架构 | 入门: 嵌套变量 → 熟练: Mixin/Function → 精通: 架构设计+BEM结合 | [sass-lang.com](https://sass-lang.com) |
| **CSS Modules / CSS-in-JS** | 作用域样式方案 | CSS Modules, Styled Components, Emotion | 入门: 基础用法 → 熟练: 动态样式 → 精通: 性能对比+场景选择 | - |
| **响应式布局** | 移动适配、断点设计 | Flexbox, Grid, Media Queries, Container Queries | 入门: Flex/Grid基础 → 熟练: 断点策略 → 精通: 容器查询+自适应图片 | [web-design-guidelines](https://github.com) |

#### 1.4 前端工程化

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **Vite** | 新一代构建工具，极速 HMR | Vite, Rollup, 插件生态 | 入门: 项目创建 → 熟练: 插件开发 → 精通: 构建优化+SSR | [vitejs.dev](https://vitejs.dev) |
| **Webpack** | 传统打包工具，生态成熟 | Webpack 5, Loader, Plugin, Module Federation | 入门: 基础配置 → 熟练: Loader/Plugin → 精通: MF微前端+性能剖析 | [webpack.js.org](https://webpack.js.org) |
| **Monorepo 管理** | 多包项目管理 | pnpm workspace, Turborepo, Nx, Lerna | 入门: workspace 配置 → 熟练: Turborepo 缓存 → 精通: Nx 图谱+CI集成 | [turborepo.org](https://turborepo.org) |
| **代码规范** | ESLint/Prettier/Husky | ESLint 9+, Prettier, Husky, lint-staged, commitlint | 入门: 规则配置 → 熟练: 自定义规则 → 精通: 团队规范体系 | - |

#### 1.5 小程序 & 跨平台

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **微信小程序** | 微信生态原生开发 | WXML, WXSS, 小程序 API, 云开发 | 入门: 页面结构 → 熟练: API调用+云函数 → 精通: 性能优化+分包加载 | [developers.weixin.qq.com](https://developers.weixin.qq.com) |
| **uni-app** | 一套代码多端运行（Vue语法） | uni-app, Vue 3, uView/UIPlus, 条件编译 | 入门: 页面开发 → 熟练: 跨端兼容 → 精通: 原生插件+性能调优 | [uniapp.dcloud.net.cn](https://uniapp.dcloud.net.cn) |
| **Taro** | React 语法多端框架 | Taro 3, React, NutUI | 入门: 基础页面 → 熟练: 跨端差异处理 → 精通: 编译原理自定义 | [taro.zone](https://taro.zone) |
| **H5 移动端** | 移动浏览器适配 | Viewport, Touch事件, FastClick, Vant | 入门: 视口设置 → 熟练: 手势交互 → 精通: 混合开发桥接 | - |

#### 1.6 状态管理与数据流

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **Redux Toolkit (RTK)** | React 状态管理标准方案 | RTK, RTK Query, Immer | 入门: Slice+Store → 熟练: RTK Query → 精通: 中间件+性能优化 | [redux-toolkit.js.org](https://redux-toolkit.js.org) |
| **Zustand / Pinia** | 轻量级状态管理 | Zustand, Pinia, DevTools | 入门: Store 定义 → 熟练: 持久化 → 精通: 中间件扩展 | [zustand.docs.pmnd.rs](https://zustand.docs.pmnd.rs) |
| **React Query / SWR** | 服务端状态管理 | TanStack Query, SWR, Axios | 入门: useQuery/useMutation → 熟练: 缓存策略 → 精通: 乐观更新+离线支持 | [tanstack.com/query](https://tanstack.com/query) |
| **GraphQL 客户端** | GraphQL 前端集成 | Apollo Client, URQL, GraphQL Codegen | 入门: Query/Mutation → 熟练: 缓存规范化 → 精通: Schema驱动开发 | [apollographql.com](https://apollographql.com) |

#### 1.7 性能优化

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **Core Web Vitals** | Google 核心性能指标 | LCP, FID/INP, CLS, Chrome DevTools | 入门: 指标理解 → 熟练: 优化实践 → 精通: 监控告警+A/B验证 | [web.dev/vitals](https://web.dev/vitals) |
| **前端性能诊断** | 性能分析与优化 | Chrome Performance, Lighthouse, WebPageTest | 入门: Lighthouse 使用 → 熟练: Performance面板 → 精通: 长任务分析+内存泄漏排查 | - |
| **代码分割与懒加载** | 减少首屏体积 | Dynamic Import, React.lazy, @loadable/component | 入门: 路由懒加载 → 熟练: 组件级分割 → 精通: 预加载策略预测 | - |
| **图片与资源优化** | 资源体积压缩 | AVIF/WebP, Image Optimization, CDN, 雪碧图替代 | 入门: 格式选择 → 熟练: 响应式图片 → 精通: 自适应质量+CDN策略 | - |

---

### 2. 后端开发

**岗位职责**: 服务器、接口、数据库、业务逻辑

#### 2.1 编程语言与框架

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **Node.js (后端)** | JavaScript 服务端开发 | Express/Koa/Fastify/NestJS, TypeScript | 入门: Express 路由 → 熟练: NestJS 模块化 → 精通: 微服务拆分+集群 | [nestjs.com](https://nestjs.com), [supabase-postgres-best-practices](https://github.com) |
| **Python (后端)** | AI/数据/Web 后端首选 | Django/FastAPI/Flask, Pydantic, SQLAlchemy | 入门: Flask/FastAPI CRUD → 熟练: Django Admin+ORM → 精通: 异步高并发+Celery | [fastapi.tiangolo.com](https://fastapi.tiangolo.com) |
| **Java (Spring)** | 企业级后端主流 | Spring Boot 3, Spring Cloud, MyBatis/JPA | 入门: Spring Boot REST → 熟练: Spring Security → 精通: 分布式事务+微服务治理 | [spring.io/projects/spring-boot](https://spring.io/projects/spring-boot) |
| **Go (Gin/Echo)** | 高性能后端/云原生 | Go, Gin/Echo, GORM, gRPC | 入门: Gin CRUD → 熟练: 并发模型 → 精通: gRPC+分布式追踪 | [go.dev](https://go.dev) |
| **Rust (Actix/Axum)** | 安全高性能后端 | Rust, Actix-web/Axum, SQLx, Tokio | 入门: Axum 路由 → 熟练: 异步运行时 → 精通: 无安全并发+零成本抽象 | [rust-lang.org](https://rust-lang.org) |
| **PHP (Laravel)** | 快速 Web 开发 | Laravel, Eloquent, Blade, Octane | 入门: 路由+Blade → 熟练: Eloquent ORM → 精通: Octane+Swoole高并发 | [laravel.com](https://laravel.com) |

#### 2.2 API 设计与开发

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **RESTful API 设计** | 标准 HTTP 接口设计 | HTTP Methods, Status Codes, HATEOAS, OpenAPI/Swagger | 入门: CRUD 规范 → 熟练: 版本控制+分页 → 精通: Hypermedia+API网关 | [swagger.io](https://swagger.io) |
| **GraphQL** | 查询语言，灵活获取数据 | Apollo Server, GraphQL, Schema-first/Code-first | 入门: Schema定义 → 熟练: Resolver+N+1解决 → 精通: Federation+订阅 | [graphql.org](https://graphql.org) |
| **gRPC** | 高性能 RPC 框架 | Protocol Buffers, gRPC, Connect-RPC | 入门: Proto 定义 → 熟练: Streaming → 精通: 网关转换+负载均衡 | [grpc.io](https://grpc.io) |
| **WebSocket / SSE** | 实时双向通信 | Socket.io, WS, Server-Sent Events | 入门: 聊天室Demo → 熟练: 心跳重连 → 精通: 房间管理+消息可靠性 | [socket.io](https://socket.io) |
| **API 文档与Mock** | 接口文档自动化 | Swagger/OpenAPI, Postman, Apifox, Prism | 入门: Swagger 注解 → 熟练: Mock服务 → 精通: 文档即测试 | [apifox.com](https://apifox.com) |

#### 2.3 数据库操作

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **SQL 基础与进阶** | 关系型数据库查询语言 | PostgreSQL/MySQL, 复杂JOIN, 窗口函数, CTE | 入门: CRUD → 熟练: 索引优化+EXPLAIN → 精通: 执行计划分析+锁机制 | [supabase-postgres-best-practices](https://github.com) |
| **ORM 框架** | 对象关系映射 | Prisma/Drizzle(TypeScript), SQLAlchemy(Python), MyBatis(Java) | 入门: Model定义 → 熟练: 关联查询 → 精通: N+1问题+迁移管理 | [prisma.io](https://prisma.io) |
| **Redis** | 缓存/会话/队列 | Redis, Redis Stack, ioredis, Redisson | 入门: String/Hash → 熟练: 发布订阅+Lua脚本 → 精通: 集群+持久化策略 | [redis.io](https://redis.io) |
| **MongoDB** | NoSQL 文档数据库 | MongoDB, Mongoose, Aggregation Pipeline | 入门: CRUD 操作 → 熟练: 聚合管道 → 精通: 分片+副本集 | [mongodb.com](https://mongodb.com) |

#### 2.4 认证与授权

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **JWT / OAuth 2.0** | Token 认证标准 | JWT, OAuth 2.0, OIDC, Passport.js | 入门: JWT签发验证 → 熟练: OAuth流程 → 精通: RefreshToken轮换+多因素认证 | [better-auth-best-practices](https://github.com) |
| **Session 管理** | 传统会话方案 | Express-session, Cookie, Redis Session | 入门: Cookie-Session → 熟练: Redis存储 → 精通: 分布式Session+安全加固 | - |
| **权限控制 (RBAC/ABAC)** | 权限模型设计 | Casbin, ACL, Policy-as-Code | 入门: RBAC基础 → 熟练: ABAC属性 → 精通: 细粒度策略引擎 | [casbin.org](https://casbin.org) |

#### 2.5 消息队列与异步

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **RabbitMQ** | AMQP 消息中间件 | RabbitMQ, amqplib, 管理后台 | 入门: 生产消费模型 → 熟练: Exchange+死信 → 精通: 集群+镜像队列 | [rabbitmq.com](https://rabbitmq.com) |
| **Kafka** | 高吞吐流处理平台 | Apache Kafka, kafkajs, Kafka Streams | 入门: Topic/Partition → 熟练: Consumer Group → 精通:Exactly Once+Schema Registry | [kafka.apache.org](https://kafka.apache.org) |
| **Bull/BullMQ** | Redis 任务队列 | BullMQ, 重复任务, 延迟任务, 优先级 | 入门: 基本队列 → 熟悉: 重试+延迟 → 精通: 速率限制+可观测性 | [docs.bullmq.io](https://docs.bullmq.io) |
| **Celery** | Python 分布式任务队列 | Celery, Beat, Flower, Redis/RabbitMQ | 入门: Task定义 → 熟练: 定时任务+链式 → 精通: Worker池+监控 | [celeryproject.org](https://celeryproject.org) |

#### 2.6 微服务与分布式

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **微服务架构** | 服务拆分与治理 | Spring Cloud/Dubbo/gRPC, Service Mesh | 入门: 单体拆分 → 熟练: 服务发现 → 精通: 熔断降级+链路追踪 | - |
| **服务网格 (Service Mesh)** | 基础设施层网络 | Istio, Envoy, Linkerd | 入门: Sidecar概念 → 熟练: 流量管理 → 精通: 可观测性+安全策略 | [istio.io](https://istio.io) |
| **分布式事务** | 跨服务一致性 | Seata, Saga模式, TCC, 本地消息表 | 入门: 最终一致性 → 熟练: Saga编排 → 精通: 补偿模式+幂等设计 | - |
| **API 网关** | 统一入口 | Kong/APISIX/Nginx, 限流/鉴权/路由 | 入门: 反向代理 → 熟练: 插件开发 → 精通: 多租户+灰度发布 | [konghq.com](https://konghq.com) |

---

### 3. 移动端开发

**岗位职责**: iOS/Android、鸿蒙 APP

#### 3.1 原生开发

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **iOS (Swift)** | Apple 生态原生开发 | Swift 5, SwiftUI, UIKit, Combine, Xcode | 入门: SwiftUI 声明式UI → 熟练: Combine响应式 → 精通: App架构(MVVM-C)+性能 | [developer.apple.com/swiftui](https://developer.apple.com/swiftui), [vercel-react-native-skills](https://github.com) |
| **Android (Kotlin)** | Google 生态原生开发 | Kotlin, Jetpack Compose, MVVM, Android Studio | 入门: Compose UI → 熟练: ViewModel+Navigation → 精通: 自定义View+性能 profiling | [developer.android.com/jetpack/compose](https://developer.android.com/jetpack/compose) |
| **鸿蒙 (ArkTS)** | 华为鸿蒙原生开发 | ArkTS, ArkUI, Stage模型, DevEco Studio | 入门: ArkUI组件 → 熟练: Ability生命周期 → 精通: 分布式能力+元服务 | [developer.huawei.com](https://developer.huawei.com) |

#### 3.2 跨平台开发

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **React Native** | JavaScript 跨平台移动应用 | RN 0.74+, Expo, React Navigation, Reanimated | 入门: 组件+导航 → 熟练: 原生模块桥接 → 精通: 架构设计+性能优化 | [reactnative.dev](https://reactnative.dev), [vercel-react-native-skills](https://github.com) |
| **Flutter** | Google 跨平台 UI 框架 | Flutter 3, Dart, Riverpod, GoRouter | 入门: Widget树 → 熟练: 状态管理 → 精通: Platform Channel+渲染原理 | [flutter.dev](https://flutter.dev) |
| **Capacitor/Cordova** | Web技术包装原生应用 | Capacitor, Ionic, PWA | 入门: 基础插件 → 熟练: 自定义插件 → 精通: 混合架构+离线策略 | [capacitorjs.com](https://capacitorjs.com) |
| **uni-app (App端)** | Vue 语法跨平台App | uni-app, nvue, 原生插件, 离线打包 | 入门: 页面开发 → 熟练: nvue原生渲染 → 精通: 原生模块扩展 | [uniapp.dcloud.net.cn](https://uniapp.dcloud.net.cn) |

#### 3.3 移动端专项

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **推送通知** | 消息推送集成 | FCM, APNs, 华为/小米/OPPO厂商通道, 个推/极光 | 入门: 基础推送 → 熟练: 厂商通道 → 精通: 到达率优化+富媒体 | - |
| **离线与同步** | 无网络可用策略 | SQLite/WCDB, 数据同步, 冲突解决 | 入门: 本地缓存 → 熟练: 增量同步 → 精通: CRDT+冲突自动合并 | - |
| **性能监控** | APM 集成 | Firebase Performance, Sentry, 自定义埋点 | 入门: SDK接入 → 熟练: 自定义指标 → 精通: 卡顿/崩溃分析 | - |
| **应用商店上架** | iOS/Android/鸿蒙发布流程 | App Store Connect, Google Play Console, AppGallery Connect | 入门: 基础提审 → 熟练: ASO优化 → 精通: 合规审核+灰度发布 | - |

---

### 4. 全栈开发

**岗位职责**: 前后端都会，初创必备

#### 4.1 全栈技术栈组合

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **MERN Stack** | MongoDB + Express + React + Node | MERN, TypeScript 全栈 | 入门: CRUD全栈 → 熟练: Auth+部署 → 精通: 微型SaaS架构 | - |
| **T3 Stack** | TypeScript 全栈最佳实践 | Next.js, tRPC, Prisma, Tailwind, NextAuth | 入门: 项目脚手架 → 熟练: tRPC端到端类型安全 → 精通: Monorepo+部署 | [create.t3.gg](https://create.t3.gg) |
| **BaaS (Backend as a Service)** | 后端即服务，快速出原型 | Supabase, Firebase, Appwrite, Nhost | 入门: Supabase CRUD → 熟练: Auth+Realtime → 精通: Edge Functions+Row Level Security | [supabase.com](https://supabase.com) |
| **Serverless / FaaS** | 无服务器架构 | AWS Lambda/Vercel Edge/Cloudflare Workers | 入门: 基础函数 → 熟练: 冷启动优化 → 精通: 事件驱动架构 | [vercel.com/functions](https://vercel.com/functions) |

#### 4.2 全栈最佳实践

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **端到端类型安全** | 前后端类型共享 | tRPC, Zod, OpenAPI Codegen, RPC | 入门: Zod校验 → 熟练: tRPC全栈 → 精通: Schema驱动开发 | [trpc.io](https://trpc.io) |
| **全栈项目架构** | 初创项目架构设计 | 分层架构, DDD精简版, Clean Architecture | 入门: MVC分层 → 熟练: Repository模式 → 精通: 六边形架构+CQRS | - |
| **快速原型能力** | 从0到1快速验证 | Vercel/Netlify, Supabase, Clerk/Auth0, Stripe | 入门: 模板项目 → 熟练: 1天MVP → 精通: 用户反馈迭代闭环 | - |

---

### 5. 测试工程师

**岗位职责**: 功能测试、接口测试、自动化测试

#### 5.1 自动化测试框架

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **单元测试** | 函数/组件级别测试 | Jest/Vitest, Testing Library, @testing-library/react | 入门: 基础断言 → 熟练: Mock/Stub → 精通: TDD红绿重构 | [jestjs.io](https://jestjs.io), [test-driven-development](https://github.com) |
| **组件测试** | UI 组件隔离测试 | Cypress Component Testing, Storybook Test Runner | 入门: 渲染测试 → 熟练: 交互测试 → 精通: Visual Regression | [cypress.io](https://cypress.io) |
| **E2E 测试** | 端到端用户流程测试 | Playwright, Cypress, Puppeteer | 入门: 录制回放 → 熟练: Page Object Model → 精通: CI并行+失败视频录制 | [playwright.dev](https://playwright.dev), [webapp-testing](https://github.com) |
| **API 测试** | 接口自动化测试 | Postman/Newman, Rest Assured, Supertest, httptest | 入门: 接口请求 → 熟练: 断言+环境变量 → 精通: 数据驱动+契约测试 | [postman.com](https://postman.com) |

#### 5.2 测试方法论

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **TDD (测试驱动开发)** | 先写测试再写实现 | Red-Green-Refactor 循环 | 入门: 基本循环 → 熟练: Mock隔离 → 精通: 测试覆盖率策略 | [test-driven-development](https://github.com) |
| **BDD (行为驱动开发)** | 自然语言描述测试 | Cucumber/Gherkin, Playwright BDD | 入门: Feature文件 → 熟练: Step Definition → 精通: Living Documentation | [cucumber.io](https://cucumber.io) |
| **性能测试** | 压力/负载/基准测试 | k6, JMeter, Locust, Artillery | 入门: 基准测试 → 熟练: 负载模拟 → 精通: 瓶颈定位+容量规划 | [k6.io](https://k6.io) |
| **安全测试** | 漏洞扫描与渗透 | OWASP ZAP, Burp Suite, SAST/DAST | 入门: OWASP Top 10 → 熟练: 自动扫描集成 → 精通: 渗透测试报告 | [owasp.org](https://owasp.org) |

#### 5.3 测试基础设施

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **CI/CD 测试集成** | 流水线中嵌入测试 | GitHub Actions, GitLab CI, Jenkins, Allure Report | 入门: 基础流水线 → 熟练: 并行执行 → 精通: 测试门禁+质量卡点 | - |
| **测试数据管理** | 测试数据生成与管理 | Faker, Factory Bot, Test Containers, Flyway | 入门: 随机数据 → 熟练: Factory模式 → 精通: TestContainers真实环境 | [testcontainers.org](https://testcontainers.org) |
| **缺陷管理** | Bug 追踪与分析 | Jira, ZenHub, Sentry, Bugsnag | 入门: Bug录入 → 熟练: 回归分析 → 精通: 缺陷趋势+根因分析 | - |

---

### 6. 运维工程师

**岗位职责**: 服务器部署、云服务、上线维护、监控

#### 6.1 容器化与编排

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **Docker** | 容器化标准 | Dockerfile, Docker Compose, Multi-stage Build | 入门: 镜像构建 → 熟练: Compose编排 → 精通: 镜像优化+安全扫描 | [docs.docker.com](https://docs.docker.com) |
| **Kubernetes (K8s)** | 容器编排平台 | K8s, Helm, Kustomize, kubectl | 入门: Pod/Deployment → 熟练: Service/Ingress → 精通: Operator开发+故障排查 | [kubernetes.io](https://kubernetes.io) |
| **容器镜像仓库** | 镜像存储与分发 | Harbor, ECR, ACR, GHCR | 入门: 推送拉取 → 熟练: 镜像签名 → 精通: 镜像同步+漏洞扫描 | - |

#### 6.2 云服务平台

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **阿里云 (国内主流)** | 国内最大云服务商 | ECS, OSS, RDS, SLB, CDN, 函数计算 | 入门: ECS+域名解析 → 熟练: RDS+OSS → 精通: 混合云+成本优化 | [aliyun.com](https://aliyun.com) |
| **AWS (国际主流)** | 全球最大云平台 | EC2, S3, RDS, Lambda, CloudFront, VPC | 入门: EC2实例 → 熟练: S3+Lambda无服务器 → 精通: Well-Architected | [aws.amazon.com](https://aws.amazon.com) |
| **腾讯云 / 华为云** | 国内备选云平台 | CVM, COS, TBDS, CCE | 入门: 基础产品 → 熟练: 专属产品 → 精通: 多云容灾 | - |
| **边缘计算 / CDN** | 全球加速与边缘部署 | Cloudflare Workers, Vercel Edge, 阿里DCDN | 入门: CDN配置 → 熟练: 边缘函数 → 精通: 多节点调度 | [workers.cloudflare.com](https://workers.cloudflare.com) |

#### 6.3 CI/CD 与自动化部署

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **GitHub Actions** | GitHub 原生 CI/CD | YAML Workflows, Self-hosted Runners, Matrix | 入门: 基础工作流 → 熟练: 缓存+矩阵 → 精通: Composite Action+复用 | [github.com/features/actions](https://github.com/features/actions) |
| **GitLab CI / Jenkins** | 企业级 CI/CD | .gitlab-ci.yml, Jenkinsfile, Pipeline | 入门: 基础Pipeline → 熟练: 多阶段 → 精通: 共享库+模板 | [about.gitlab.com/stages-devops-lifecycle/continuous-integration](https://about.gitlab.com/stages-devops-lifecycle/continuous-integration) |
| **ArgoCD (GitOps)** | Kubernetes 声明式部署 | ArgoCD, Flux, GitOps Workflow | 入门: Application同步 → 熟练: Sync Policy → 精通: ApplicationSet+多集群 | [argoproj.github.io/cd](https://argoproj.github.io/cd) |
| **蓝绿/金丝雀发布** | 零停机部署策略 | Istio, Nginx Canary, Flagger | 入门: 蓝绿切换 → 熟练: 金丝雀流量切分 → 精通: 自动回滚+渐进交付 | - |

#### 6.4 监控与可观测性

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **日志聚合** | 集中式日志管理 | ELK Stack(Elasticsearch+Logstash+Kibana), Loki, PLG | 入门: 日志收集 → 熟练: 查询分析 → 精通: 日志告警+合规留存 | [elastic.co](https://elastic.co) |
| **指标监控** | 系统与应用指标 | Prometheus + Grafana, Datadog, New Relic | 入门: Grafana看板 → 熟练: PromQL → 精通: 告警规则+SLO管理 | [prometheus.io](https://prometheus.io) |
| **链路追踪** | 分布式请求追踪 | Jaeger, Zipkin, OpenTelemetry, SkyWalking | 入门: Span概念 → 熟练: OTel集成 → 精通: Trace关联+瓶颈定位 | [opentelemetry.io](https://opentelemetry.io) |
| **APM (应用性能监控)** | 应用层面监控 | Sentry, Datadog APM, 阿里ARMS | 入门: 错误捕获 → 熟练: 性能基线 → 精通: 告警降噪+根因分析 | [sentry.io](https://sentry.io) |

#### 6.5 基础设施即代码 (IaC)

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **Terraform** | 多云 IaC 工具 | Terraform, Provider, State Management | 入门: 资源定义 → 熟练: Module复用 → 精通: Workspace+Policy | [terraform.io](https://terraform.io) |
| **Ansible** | 配置管理自动化 | Ansible Playbook, Inventory, Role | 入门: Ad-hoc命令 → 熟练: Playbook编写 → 精通: Galaxy+动态Inventory | [ansible.com](https://ansible.com) |
| **Pulumi** | 编程语言写 IaC | Pulumi(TS/Python/Go), 跨云抽象 | 入门: 基础资源 → 熟练: 组件抽象 → 精通: 多语言+测试驱动 | [pulumi.com](https://pulumi.com) |

---

### 7. 架构师

**岗位职责**: 系统设计、技术选型、框架搭建（中大型公司必备）

#### 7.1 系统设计方法

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **高并发架构** | 大流量系统设计 | 负载均衡, 缓存层, 消息队列, 数据库分库分表 | 入门: 垂直水平扩展 → 熟练: 缓存穿透/击穿/雪崩 → 精通: 流量漏斗+容量预估 | System Design Interview |
| **高可用架构 (HA)** | 故障容忍设计 | 多活/双活, 故障转移, 熔断降级, 幂等设计 | 入门: 主备切换 → 熟练: Chaos Engineering → 精通: RTO/RPO目标设计 | - |
| **分布式系统理论** | CAP/BASE/一致性算法 | CAP定理, Paxos/Raft, 向量钟, CRDT | 入门: CAP取舍 → 熟练: Raft协议 → 精通: 最终一致性方案设计 | - |
| **领域驱动设计 (DDD)** | 复杂业务建模 | 限界上下文, 聚合根, 领域事件, CQRS | 入门: 基础概念 → 熟练: 战略设计 → 精通: 事件风暴+上下文映射 | [dddcommunity.org](https://dddcommunity.org) |

#### 7.2 架构模式

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **微服务架构** | 服务拆分模式 | API Gateway, BFF, Strangler Fig, Backend for Frontend | 入门: 按业务拆分 → 熟练: 通信模式选择 → 精通: 演进式架构 | - |
| **事件驱动架构 (EDA)** | 异步解耦架构 | Event Sourcing, CQRS, Outbox Pattern, Event Mesh | 入门: Pub/Sub → 熟练: Event Sourcing → 精通: Saga编排+事件版本ing | - |
| **Serverless 架构** | 无服务器架构设计 | FaaS+BaaS, Event-driven, Scale-to-zero | 入门: 函数拆分 → 熟练: 冷启动优化 → 精通: 成本模型+供应商锁定规避 | - |
| **云原生架构** | 云优先架构设计 | 12-Factor App, Cloud Native, Service Mesh | 入门: 12要素遵循 → 熟练: 声明式API → 精通: 多云策略 | [12factor.net](https://12factor.net) |

#### 7.3 技术选型与评估

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **技术选型方法论** | 技术决策框架 | Technology Radar, ADR (Architecture Decision Records) | 入门: 对比表格 → 熟练: PoC验证 → 精通: 决策记录+回溯 | [adr.github.io](https://adr.github.io) |
| **性能基准测试** | 技术方案对比 | TechEmpower, 自建Benchmark, AB测试 | 入门: 基础压测 → 熟练: 对比分析 → 精通: 场景化选型决策 | [techempower.com](https://techempower.com) |
| **安全架构** | 安全体系设计 | Zero Trust, IAM, 加密传输, 数据脱敏 | 入门: HTTPS+基础认证 → 熟练: OAuth/OIDC → 精通: 零信任架构+合规(GDPR/等保) | - |

---

### 8. 数据库工程师

**岗位职责**: 数据库设计、优化、备份

#### 8.1 关系型数据库

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **PostgreSQL** | 功能最强大的开源关系数据库 | PG 16+, JSONB, 全文搜索, 扩展生态 | 入门: 基础DDL/DML → 熟练: 索引+EXPLAIN → 精通: 源码级调优+扩展开发 | [postgresql.org](https://postgresql.org), [supabase-postgres-best-practices](https://github.com) |
| **MySQL** | 最流行的开源关系数据库 | MySQL 8.0+, InnoDB, Group Replication | 入门: 基础操作 → 熟练: InnoDB引擎 → 精通: MGR集群+主从延迟优化 | [dev.mysql.com](https://dev.mysql.com) |
| **SQL Server / Oracle** | 商业级企业数据库 | SQL Server 2022, Oracle 21c, AlwaysOn, RAC | 入门: 基础管理 → 熟练: 高可用方案 → 精通: 集群运维+迁移 | - |

#### 8.2 NoSQL 数据库

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **MongoDB** | 文档型NoSQL | MongoDB 7.0+, Change Streams, Time Series | 入门: 文档模型 → 熟练: 聚合管道 → 精通: 分片策略+事务一致性 | [mongodb.com](https://mongodb.com) |
| **Redis** | 内存键值数据库 | Redis 7+, Redis Stack, Modules | 入门: 五大数据类型 → 熟练: Lua+Module → 精通: Cluster+持久化+大Key治理 | [redis.io](https://redis.io) |
| **Elasticsearch** | 搜索/分析引擎 | ES 8.x, Kibana, Logstash, Beats | 入门: 全文检索 → 熟练: 聚合分析 → 精通: 索引设计+Reindex策略 | [elastic.co](https://elastic.co) |
| **ClickHouse / Doris** | OLAP 分析型数据库 | ClickHouse, Apache Doris, StarRocks | 入门: 列式存储 → 熟练: 即席查询 → 精通: 实时数仓+物化视图 | [clickhouse.com](https://clickhouse.com) |

#### 8.3 数据库运维

| 技能 | 描述 | 技术栈/工具 | 熟练度路径 | 资源链接 |
|------|------|-------------|------------|----------|
| **备份与恢复** | 数据安全保障 | pg_dump/mysqlpump, WAL归档, Point-in-Time Recovery | 入门: 逻辑备份 → 熟练: 连续归档恢复 → 精通: 跨区域灾备+演练 | - |
| **读写分离与分库分表** | 扩展方案 | ShardingSphere, Vitess, ProxySQL, MyCat | 入门: 主从复制 → 熟练: 分片策略 → 精通: 弹性扩缩容+迁移 | - |
| **慢查询优化** | SQL性能调优 | EXPLAIN ANALYZE, Slow Query Log, pt-query-digest | 入门: 慢日志查看 → 熟练: 执行计划分析 → 精通: SQL改写+索引策略 | - |
| **数据库监控** | DB健康度监控 | PMM, Prometheus Exporter, Cloud DB Monitoring | 入门: 基础指标 → 熟练: 告警规则 → 精通: 容量规划+自动扩容 | - |

---

## 二、产品&设计部

### 9. 产品经理

**岗位职责**: 需求梳理、原型设计、功能规划、对接客户

#### 9.1 需求分析与方法论

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **需求挖掘与梳理** | 用户需求收集与分析 | 用户访谈, 问卷调研, 竞品分析, 用例图 | 入门: 需求收集 → 熟练: 需求优先级排序 → 精通: 隐性需求洞察+需求变更管理 | - |
| **PRD文档撰写** | 产品需求规格说明书 | PRD模板, 用户故事, 验收标准 | 入门: 基础PRD → 熟练: 结构化PRD → 精通: 可执行PRD+版本追溯 | [executing-plans](https://github.com) |
| **用户故事地图** | 敏捷需求组织 | User Story Mapping, Story Splitting, INVEST原则 | 入门: Story编写 → 熟练: Map构建 → 精通: Release Planning | - |
| **数据分析与决策** | 数据驱动产品决策 | SQL基础, Excel/BI工具, A/B Test, 埋点设计 | 入门: 数据查看 → 熟练: 漏斗分析 → 精通: 因果推断+实验设计 | - |

#### 9.2 原型设计与工具

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **Axure RP** | 专业原型设计工具 | Axure RP, 动态面板, 中继器, 变量 | 入门: 静态原型 → 熟练: 交互原型 → 精通: 组件库+团队协作 | [axure.com](https://axure.com) |
| **Figma** | 协作式设计+原型 | Figma, Prototype, Auto Layout, Components | 入门: 基础绘图 → 熟练: 交互原型 → 精通: Design System + Dev Mode | [figma.com](https://figma.com) |
| **墨刀 / MasterGo** | 国产协作原型工具 | 墨刀, MasterGo, 协作评审 | 入门: 页面制作 → 熟练: 交互动效 → 精通: 设计规范输出 | [modao.cc](https://modao.cc) |
| **即时原型 (Low-fi)** | 快速验证想法 | 纸面原型, Balsamiq, Excalidraw | 入门: 手绘草图 → 熟练: 数字草图 → 精通: 快速迭代验证闭环 | - |

#### 9.3 产品规划与运营

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **产品路线图** | 版本规划与节奏把控 | Roadmap, OKR对齐, MoSCoW法 | 入门: 时间线规划 → 熟练: 优先级矩阵 → 精通: 战略路线图+利益相关者管理 | - |
| **竞品分析** | 市场竞争研究 | 竞品矩阵, SWOT, 功能对比, 差异化定位 | 入门: 表格对比 → 熟练: 深度分析报告 → 精通: 趋势预判+护城河构建 | - |
| **用户增长策略** | 用户获取与留存 | AARRR海盗模型, 留存曲线, 激励体系 | 入门: 基础漏斗 → 熟练: 留存策略 → 精通: 增长飞轮+LTV/CAC优化 | [marketing-ideas](https://github.com), [content-strategy](https://github.com) |
| **文案与内容策略** | 产品文案与内容运营 | Landing Page文案, Onboarding引导, Help Center | 入门: 基础描述 → 熟练: 说服性文案 → 精通: 内容矩阵+SEO友好 | [copywriting](https://github.com) |

---

### 10. UI设计师

**岗位职责**: 界面设计、图标、配色、视觉稿

#### 10.1 设计基础

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **色彩理论与配色** | 色彩心理学与应用 | 色相环, 60-30-10法则, 无障碍色彩, 深色模式 | 入门: 基础配色 → 熟练: 品牌色板 → 精通: 语义化色彩系统 | [web-design-guidelines](https://github.com) |
| **排版与字体** | 字体选择与排版层级 | 字体配对, 行高字距, 响应式字体, 中文排版 | 入门: 字体选择 → 熟练: 层级系统 → 精通: Variable Font + 国际化字体方案 | - |
| **图标与插画** | 图形元素设计 | Icon Design, SVG, 插画风格, 图标库管理 | 入门: 图标绘制 → 熟练: 图标系统 → 精通: 品牌插画风格指南 | [canvas-design](https://github.com) |
| **栅格与布局** | 界面空间规划 | 8pt栅格, Bootstrap Grid, CSS Grid, 响应式断点 | 入门: 基础栅格 → 熟练: 自适应布局 → 精通: 原子设计+间距系统 | - |

#### 10.2 设计工具

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **Figma (核心)** | 主流协作设计工具 | Figma, Components, Variants, Auto Layout, Dev Mode | 入门: 基础绘图 → 熟练: 组件系统 → 精通: Design Tokens + 插件生态 | [figma.com](https://figma.com) |
| **Sketch (Mac)** | macOS 原生设计工具 | Sketch, Symbols, Libraries, Sketch2React | 入门: 界面设计 → 熟练: Symbol库 → 精通: 与开发者协作流 | [sketch.com](https://sketch.com) |
| **Adobe Creative Suite** | 专业创意工具套件 | Photoshop, Illustrator, After Effects | 入门: PS基础操作 → 熟练: AI矢量设计 → 精通: AE动效+PS合成 | [adobe.com](https://adobe.com) |
| **Framer / Principle** | 高保真交互原型 | Framer, Principle, ProtoPie | 入门: 基础动效 → 熟练: 复杂交互 → 精通: 微交互设计系统 | [framer.com](https://framer.com) |

#### 10.3 设计系统

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **Design System 构建** | 组件化设计体系 | Atomic Design, Style Guide, Pattern Library | 入门: 基础组件 → 熟练: 完整系统 → 精通: 跨平台Design Token | [ui-ux-pro-max](https://github.com) |
| **Tailwind 设计系统** | 原子化CSS设计系统 | Tailwind Config, Design Tokens, Figma-Tailwind同步 | 入门: Tailwind使用 → 熟练: 自定义设计 → 精通: DS→代码自动化 | [tailwind-design-system](https://github.com) |
| **品牌视觉识别 (VI)** | 品牌视觉规范 | Logo, VI手册, 品牌色, 辅助图形 | 入门: Logo设计 → 熟练: VI基础 → 精通: 品牌延展+数字资产 | - |
| **设计交付与标注** | 开发者友好交付 | Figma Dev Mode, Zeplin, Spec, 切图导出 | 入门: 标注导出 → 熟练: 自动化交付 → 精通: Design→Code流水线 | - |

---

### 11. UX交互设计师

**岗位职责**: 用户流程、操作逻辑、体验优化

#### 11.1 用户研究

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **用户画像** | 目标用户建模 | Persona, 用户分层, JTBD (Jobs to be Done) | 入门: 基础画像 → 熟练: 数据驱动画像 → 精通: 动态画像+细分策略 | [ui-ux-pro-max](https://github.com) |
| **可用性测试** | 产品易用性验证 | moderated/unmoderated testing, 思维 aloud, 热力图 | 入门: 基础测试 → 熟练: 远程测试 → 精通: 定量+定性混合研究 | - |
| **A/B 测试设计** | 方案对比实验 | A/B Test, 多变量测试, 统计显著性 | 入门: 基础A/B → 熟练: 实验设计 → 精通: 贝叶斯实验+序列测试 | - |
| **卡片分类** | 信息架构研究 | 开放/封闭卡片分类, 树状测试, IA验证 | 入门: 基础分类 → 熟练: 远程卡片分类 → 精通: AI辅助IA | - |

#### 11.2 交互设计

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **信息架构 (IA)** | 信息组织与导航 | 站点地图, 导航模式, 搜索设计, 面包屑 | 入门: 基础IA → 熟练: 复杂IA → 精通: 个性化IA+AI推荐 | - |
| **交互流程设计** | 用户操作路径 | User Flow, 流程图, 状态机, 异常流程 | 入门: 正常流程 → 熟练: 异常处理 → 精通: 全路径覆盖+Edge Case | - |
| **微交互设计** | 细节体验打磨 | Loading动画, 手势操作, 触觉反馈, 音效 | 入门: 基础动效 → 熟练: 情感化设计 → 精通: 动效原则+性能平衡 | - |
| **无障碍设计 (a11y)** | 包容性设计 | WCAG 2.1, 键盘导航, 屏幕阅读器, 色彩对比 | 入门: 基础合规 → 熟练: 全面a11y → 精通: a11y自动化检测 | [w3.org/WAI/WCAG21](https://w3.org/WAI/WCAG21) |

#### 11.3 体验度量

| 抃能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **HEART / GSM** | Google UX度量框架 | Happiness, Engagement, Adoption, Retention, Task Success | 入门: 指标选取 → 熟练: 度量体系搭建 → 精通: 数据驱动UX改进 | - |
| **NPS / CSAT / CES** | 用户满意度测量 | Net Promoter Score, Customer Satisfaction, Customer Effort Score | 入门: 问卷设计 → 熟练: 数据分析 → 精通: 行业对标+改进闭环 | - |
| **会话录制与热图** | 用户行为分析 | Hotjar, FullStory, Mouseflow, Clarity | 入门: 热图查看 → 熟练: 会话分析 → 精通: 行为模式挖掘+转化漏斗 | - |

---

### 12. 平面/品牌设计

**岗位职责**: LOGO、宣传海报、官网页面、物料设计

#### 12.1 品牌设计

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **LOGO设计** | 品牌标识设计 | 字标/图形/组合LOGO, 矢量绘制, 缩放测试 | 入门: 基础LOGO → 熟练: 品牌LOGO → 精通: 超级符号+IP化 | - |
| **VI 视觉识别系统** | 品牌视觉规范 | 基础系统, 应用系统, VI手册编制 | 入门: 基础VI → 熟练: 完整VI → 精通: 数字化VI+动态品牌 | - |
| **品牌延展设计** | 品牌物料多样化 | 包装, 服饰周边, 空间导视, 车体广告 | 入门: 基础延展 → 熟练: 多媒介延展 → 精通: IP联名+跨界合作 | - |
| **品牌故事与策略** | 品牌定位与叙事 | 品牌金字塔, 品牌屋, Tone of Voice | 入门: 基础定位 → 熟练: 品牌策略 → 精通: 品牌资产管理 | - |

#### 12.2 平面设计

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **海报/Banner设计** | 营销视觉设计 | 主视觉KV, 活动海报, 广告Banner, 社交媒体图 | 入门: 基础排版 → 熟练: 创意海报 → 精通: 爆款视觉+数据验证 | [baoyu-cover-1image](https://github.com) |
| **信息图表设计** | 数据可视化表达 | Infographic, 数据可视化, 图表美化 | 入门: 基础图表 → 熟练: 复杂Infographic → 精通: 动态数据可视化 | [baoyu-infographic](https://github.com) |
| **官网/Landing Page** | 营销落地页设计 | LP设计, 转化优化, A/B测试设计 | 入门: 基础LP → 熟练: 高转化LP → 精通: 个性化LP+动态创意 | - |
| **PPT/演示文稿** | 商务演示设计 | Keynote/PowerPoint, 模板设计, 动效演示 | 入门: 基础PPT → 熟练: 商务PPT → 精通: 演示叙事+沉浸式体验 | [pptx skill](https://github.com) |

#### 12.3 创意与AI辅助

| 技能 | 描述 | 工具/方法 | 熟练度路径 | 资源链接 |
|------|------|-----------|------------|----------|
| **AI图像生成** | AI辅助视觉创作 | Midjourney, Stable Diffusion, DALL-E, ComfyUI | 入门: Prompt基础 → 熟练: 风格控制 → 精通: 工作流+商业级产出 | [ai-image-generation](https://github.com) |
| **漫画/插画风** | 特定风格创作 | 漫画风, 扁平插画风, 3D风格, 像素风 | 入门: 风格模仿 → 熟练: 风格融合 → 精通: 个人标志性风格 | [baoyu-comic](https://github.com) |
| **算法艺术** | 生成艺术与创意编程 | Processing, p5.js, TouchDesigner, Generative Art | 入门: 基础图形 → 熟练: 交互艺术 → 精通: 装置艺术+NFT | [algorithmic-art](https://github.com) |
| **印刷与输出规范** | 印刷品制作规范 | CMYK,出血,叠印,纸张工艺,印厂对接 | 入门: 基础输出 → 熟练: 特殊工艺 → 精通: 成本控制+供应链管理 | - |

---

## 三、免费 API 资源库

> 开发项目时可直接使用的免费 API 清单，按场景分类，开箱即用。

### 1. Mock / 测试模拟类 API

> 前端后端联调、接口测试、原型开发刚需，开箱即用，无需复杂配置

| API 名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|----------|---------|-------------|-------------|
| **JSONPlaceholder** | [jsonplaceholder.typicode.com](https://jsonplaceholder.typicode.com/) | 完全免费、无鉴权、无调用次数限制，提供标准 RESTful 接口 | 前端 CRUD、列表、表单功能开发测试，模拟用户/帖子/评论等真实业务接口 |
| **ReqRes** | [reqres.in](https://reqres.in/) | 完全免费无限制，支持用户注册、登录、分页、增删改查全流程模拟 | 前端登录认证、权限管理、分页列表开发，模拟真实后端接口响应 |
| **MockAPI.io** | [mockapi.io](https://mockapi.io/) | 免费版支持 3 个项目、无限请求、自定义接口规则与数据结构 | 自定义业务接口 Mock，适配个性化数据结构，前后端并行开发 |
| **httpbin** | [httpbin.org](https://httpbin.org/) | 完全免费无限制，支持 HTTP 请求全场景测试 | 接口调试、请求头/参数/响应测试、爬虫开发、HTTP 客户端功能验证 |
| **Mockoon** | [mockoon.com](https://mockoon.com/) | 开源免费，本地部署无限制，支持 RESTful/GraphQL 接口模拟 | 本地离线 Mock 服务，无网络依赖，适配复杂接口场景测试 |

### 2. 全栈高频刚需 - 基础工具类 API

> 日常开发通用能力，零门槛接入，覆盖 90% 开发基础需求

| API 名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|----------|---------|-------------|-------------|
| **TimeAPI** | [timeapi.io](https://www.timeapi.io/) | 完全免费、无鉴权、无调用次数限制，支持 JSON/XML 返回 | 时间校准、时区转换、节假日查询、时间戳转换、日出日落时间获取 |
| **IPAPI.co** | [ipapi.co](https://ipapi.co/) | 免费版无调用量限制，支持 CORS 跨域，返回 IP 归属地/运营商/经纬度 | 前端 IP 定位、地域限制、访问统计、风控校验，无需后端代理 |
| **TenAPI** | [tenapi.cn](https://tenapi.cn/) | 国内完全免费工具 API 集合，大部分接口无调用限制，无需复杂认证 | 二维码生成/解析、短信验证码、IP 查询、天气、快递、短链接、拼音转换等高频开发需求 |
| **UUID Generator API** | [uuidtools.com/api](https://www.uuidtools.com/api) | 完全免费无鉴权，支持批量生成 UUID v1/v3/v4/v5 | 数据库主键生成、唯一 ID 生成、分布式系统唯一标识开发 |
| **国家企业信用信息公示 API** | [gsxt.gov.cn/api-mgr.html](https://www.gsxt.gov.cn/api-mgr.html) | 官方免费企业工商信息查询接口，合规稳定 | 企业认证、资质核验、工商信息查询类业务开发 |

### 3. AI 开发核心 - 免费大模型/多模态 API

> 2026 年稳定可用，适配代码生成、AI Agent、多模态应用开发，兼容 OpenAI SDK

| API 名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|----------|---------|-------------|-------------|
| **Google Gemini API** | [ai.google.dev](https://ai.google.dev/) | 永久免费层，Gemini 2.5 Flash 每分钟 60 次请求、每天 1500 次调用，无月度上限 | 多模态开发、代码生成、长文本处理、AI Agent 开发，兼容 OpenAI 格式 |
| **Mistral API** | [console.mistral.ai](https://console.mistral.ai/) | 永久免费套餐，每月 200 万免费 Token，无过期时间，支持代码专用 Codestral 模型 | 代码生成、推理任务、轻量级 AI 应用，海外网络适配，低延迟 |
| **DeepSeek API** | [platform.deepseek.com](https://platform.deepseek.com/) | 注册即送 500 万免费 Token，V4 模型代码能力拉满，国内网络直连 | 代码审查、代码生成、技术问答、后端 AI 服务开发 |
| **通义千问 API** | [tongyi.aliyun.com](https://tongyi.aliyun.com/) | 免费层每月 100 万 Token，Qwen-Turbo/代码模型永久免费，国内合规稳定 | 中文场景 AI 应用、代码生成、多模态开发，阿里云生态适配 |
| **Tavily Search API** | [tavily.com](https://tavily.com/) | 每月 1000 次免费调用，专为 AI Agent 优化的实时搜索 API，支持深度网页抓取 | RAG 检索、AI 智能体开发、实时信息问答、知识库应用 |
| **火山方舟 API（豆包大模型）** | [volcengine.com/ark](https://www.volcengine.com/ark) | 每日自动发放 200 万免费 Token，当天有效，支持 Doubao 全系列模型 | 中文 AI 应用、日常自动化脚本、多模态开发，国内网络直连 |
| **Hugging Face Inference API** | [huggingface.co/docs/api-inference](https://huggingface.co/docs/api-inference) | 免费版无限调用（速率限制），支持 10 万+开源模型，覆盖 LLM/CV/NLP 全场景 | 开源模型测试、自定义 AI 应用、多模态功能原型开发 |

### 4. 业务数据支撑 - 免费业务数据 API

> 项目开发核心业务数据，覆盖 LBS、天气、金融、资讯、影视等主流场景

| API 名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|----------|---------|-------------|-------------|
| **高德地图开放平台** | [lbs.amap.com](https://lbs.amap.com/) | 实名认证后，基础地图、地理编码/逆编码、路径规划、POI 查询每日 30 万次免费调用 | 国内 LBS 应用、外卖/出行/导航类项目、位置服务开发，国内网络最优 |
| **百度地图开放平台** | [lbsyun.baidu.com](https://lbsyun.baidu.com/) | 实名认证后，基础地图服务、定位、路径规划永久免费额度 | 百度生态适配、国内地图类应用、室内定位、交通路况类开发 |
| **OpenWeather API** | [openweathermap.org/api](https://openweathermap.org/api) | 免费版每分钟 60 次请求、每月 100 万次调用，全球天气/空气质量/预报数据 | 全球天气类应用、跨境项目、气象数据可视化开发 |
| **和风天气 API** | [dev.qweather.com](https://dev.qweather.com/) | 免费版每日 3000 次调用，国内天气/空气质量/灾害预警数据，中文优化 | 国内天气类小程序/APP、生活服务类应用开发 |
| **TMDB API** | [themoviedb.org/documentation/api](https://www.themoviedb.org/documentation/api) | 非商用场景完全免费，速率限制 40 次/10 秒、50000 次/天，全球影视全量数据 | 影视类 APP/网站、影评平台、视频内容管理系统开发 |
| **TuShare API** | [tushare.pro](https://tushare.pro/) | A股/港股/美股基础行情、日线、基本面数据永久免费调用，Python 原生支持 | 金融量化、财经类应用、股票数据分析工具开发 |
| **NewsAPI** | [newsapi.org](https://newsapi.org/) | 免费版每日 100 次请求，全球新闻资讯聚合、关键词检索、来源筛选 | 资讯类应用、舆情监控、新闻聚合平台开发 |
| **聚合数据** | [juhe.cn](https://www.juhe.cn/) | 790+API 覆盖生活服务、金融、出行等场景，大部分接口提供免费测试额度 | 一站式业务数据接入，快递查询、手机号归属、违章查询等高频需求 |

### 5. 多媒体处理 - 免费音视频/图片 API

> 内容处理开发必备，覆盖图片存储、音视频处理、OCR、文档转换等场景

| API 名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|----------|---------|-------------|-------------|
| **Cloudinary API** | [cloudinary.com](https://cloudinary.com/) | 免费版每月 25GB 存储、25GB 带宽、每月 25 次视频处理，支持图片/视频云端处理+CDN | 前端图片压缩/裁剪/水印、音视频转码、图床服务，前端开发零门槛接入 |
| **百度智能云 OCR API** | [cloud.baidu.com/product/ocr](https://cloud.baidu.com/product/ocr) | 通用文字识别每月 1000 次免费调用，身份证/银行卡/票据识别均有免费额度 | 文字识别、证件核验、票据录入、文档扫描类应用开发 |
| **Edge-TTS** | [github.com/rany2/edge-tts](https://github.com/rany2/edge-tts) | 完全开源免费，无调用/字符上限，无需 API 密钥，支持多语种多音色语音合成 | 语音播报、有声书、AI 语音助手开发，前后端均可快速接入 |
| **Imgur API** | [apidocs.imgur.com](https://apidocs.imgur.com/) | 免费版无严格调用限制，支持图片上传/存储/处理/分享，全球 CDN 加速 | 海外项目图床、图片分享功能、社区类应用开发 |
| **Remove.bg API** | [remove.bg/api](https://www.remove.bg/api) | 免费版每月 50 次调用，全自动图片抠图、背景移除，API 一键接入 | 图片处理工具、电商商品图制作、海报生成类应用开发 |

### 6. 用户体系开发 - 第三方登录/OAuth API

> 网站/APP 用户体系开发，免开发账号系统，提升用户注册转化率

| API 名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|----------|---------|-------------|-------------|
| **GitHub OAuth API** | [docs.github.com/zh/apps/oauth-apps](https://docs.github.com/zh/apps/oauth-apps) | 完全免费无限制，支持用户信息获取、授权登录，开发者首选 | 技术类网站、开源工具、开发者平台第三方登录 |
| **微信开放平台 API** | [open.weixin.qq.com](https://open.weixin.qq.com/) | 个人/企业开发者可接入，微信登录/分享/支付基础功能免费 | 国内 APP/小程序/网站用户体系，微信生态适配 |
| **QQ 互联开放平台** | [connect.qq.com](https://connect.qq.com/) | 完全免费，支持 QQ 第三方登录、用户信息获取、分享功能 | 国内网站/APP 用户体系，年轻用户群体适配 |
| **Google OAuth 2.0 API** | [developers.google.com/identity/protocols/oauth2](https://developers.google.com/identity/protocols/oauth2) | 完全免费无限制，支持 Google 账号登录、跨平台授权 | 海外项目、跨境网站/APP 用户体系开发 |
| **抖音开放平台 API** | [developer.open-douyin.com](https://developer.open-douyin.com/) | 免费基础额度，支持抖音登录、内容发布、数据获取、短视频能力接入 | 短视频相关应用、内容平台、电商类项目开发 |

### 7. 运维/网络开发 - 系统工具类 API

> 后端、运维、安全开发专用，覆盖域名、DNS、SSL、监控、安全检测场景

| API 名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|----------|---------|-------------|-------------|
| **GitHub API** | [docs.github.com/zh/rest](https://docs.github.com/zh/rest) | 免费版每小时 5000 次请求，支持仓库/用户/Issue/Workflow 全量数据操作 | 开源工具、DevOps 平台、代码管理系统开发 |
| **SSL Labs API** | [ssllabs.com/projects/ssllabs-apis/](https://www.ssllabs.com/projects/ssllabs-apis/) | 完全免费，支持 SSL 证书检测、安全评级、漏洞扫描 | HTTPS 站点监控、证书管理工具、安全检测平台开发 |
| **VirusTotal API** | [developers.virustotal.com/reference](https://developers.virustotal.com/reference) | 免费版每日 500 次请求，支持文件/URL/IP 安全检测、病毒查杀、恶意代码识别 | 安全工具、文件上传校验、URL 风控检测开发 |
| **Ping.pe API** | [ping.pe/api](https://ping.pe/api) | 免费版可用，支持全球节点 ping/traceroute/端口检测、服务器可用性监控 | 网络监控工具、服务器状态检测、多节点可用性验证开发 |
| **Cloudflare DNS API** | [developers.cloudflare.com/api](https://developers.cloudflare.com/api) | 免费版完全可用，支持 DNS 解析管理、域名管理、DDOS 防护配置 | 域名管理工具、DNS 自动化配置、站点运维平台开发 |

### 8. Serverless/部署 - 云服务免费平台

> 开发部署全流程免费资源，覆盖服务器、数据库、CDN、Serverless 函数

| 平台名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|----------|---------|-------------|-------------|
| **Cloudflare 免费套餐** | [cloudflare.com/zh-cn/plans/free/](https://www.cloudflare.com/zh-cn/plans/free/) | 永久免费，提供 CDN、DNS、Worker Serverless 函数、KV 存储、R2 对象存储 | 前端部署、Serverless 接口开发、全球 CDN 加速、静态站点托管 |
| **Vercel 免费套餐** | [vercel.com/pricing](https://vercel.com/pricing) | 永久免费，支持 React/Vue/Next.js 等前端框架一键部署、Serverless 函数、全球 CDN | 前端项目部署、全栈应用开发、静态/SSR 站点托管 |
| **阿里云免费套餐** | [free.aliyun.com](https://free.aliyun.com/) | 新用户长期免费额度，覆盖云服务器、云数据库 RDS、对象存储 OSS、API 网关、函数计算 | 国内全栈项目部署、后端服务开发、企业级应用测试 |
| **腾讯云免费专区** | [cloud.tencent.com/free](https://cloud.tencent.com/free) | 新用户长期免费额度，云服务器、CDN、云数据库、对象存储 COS、AI 能力全品类覆盖 | 国内小程序/APP/网站开发部署、腾讯生态适配 |
| **AWS Free Tier** | [aws.amazon.com/free/](https://aws.amazon.com/free/) | 12 个月免费额度，覆盖 EC2 云服务器、S3 对象存储、Lambda 函数、RDS 数据库 | 海外项目部署、跨境应用开发、全球分布式服务搭建 |

### 9. API 聚合大全 - 一站式免费 API 平台

> 海量 API 一站式查找，覆盖全场景，新手友好，快速找到适配开发需求的接口

| 平台名称 | 官方链接 | 说明 |
|----------|---------|------|
| **Public APIs** | [publicapis.org](https://publicapis.org/) | 全球最大免费 API 合集，分类齐全 |
| **RapidAPI 免费专区** | [rapidapi.com/collection/free-apis](https://rapidapi.com/collection/free-apis) | RapidAPI 免费 API 专区，按分类浏览 |
| **Any-API** | [any-api.com](https://any-api.com/) | 带示例代码的 API 大全，新手友好 |
| **GitHub awesome-free-apis** | [github.com/codiebyheaart/awesome-free-apis](https://github.com/codiebyheaart/awesome-free-apis) | GitHub 社区维护的免费 API 合集 |

---

## 四、免费数据库资源库

> 项目开发免自建数据库，开箱即用，按场景分类推荐。

### 1. 关系型数据库（MySQL / PostgreSQL）

> 适合后端项目、网站业务数据、结构化数据存储

| 数据库名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|-----------|---------|-------------|-------------|
| **PlanetScale** | [planetscale.com](https://planetscale.com) | 永久免费，1 个数据库、无限存储、无限查询 | 兼容 MySQL 协议，不用自己搭服务器；支持分支、回滚、直接连代码；后端项目、网站业务数据首选，稳定不跑路 |
| **Neon** | [neon.tech](https://neon.tech) | 永久免费，3GB 存储、免费计算额度 | 标准 PostgreSQL，支持连接池、定时休眠不扣费；适合 Java/Node/Python 后端，存结构化业务数据 |
| **Supabase** | [supabase.com](https://supabase.com) | 免费版永久够用，内置 PostgreSQL + 自带 API | 不用写后端也能 CRUD，自带用户登录、权限、实时订阅；适合快速开发、小程序、管理后台 |

### 2. NoSQL / 文档数据库（MongoDB 类）

> 适合 JSON 结构数据、日志、用户配置、缓存、会话存储

| 数据库名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|-----------|---------|-------------|-------------|
| **MongoDB Atlas** | [mongodb.com/atlas/database](https://www.mongodb.com/atlas/database) | 免费永久集群，512MB 存储 | 标准 MongoDB，支持外网直连，所有后端语言都适配；存 JSON 结构数据、日志、用户配置、商品数据超合适 |
| **Upstash** | [upstash.com](https://upstash.com) | 免费 Redis + Kafka + 文档库 | Redis 免费够用，低延迟，适合做缓存、会话存储、限流 |

### 3. 轻量免运维（自带 API，不用写 SQL）

> 零成本、免服务器、免配置，极简开发首选

| 数据库名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|-----------|---------|-------------|-------------|
| **Vercel KV / Vercel Postgres** | [vercel.com](https://vercel.com) | 免费额度够用，和 Vercel 部署无缝衔接 | 适合前端 + 后端一体项目，Serverless 开发 |
| **Cloudflare D1** | [cloudflare.com/zh-cn/products/d1/](https://www.cloudflare.com/zh-cn/products/d1/) | 免费内置 SQLite 数据库 | 搭配 Cloudflare Worker 直接写后端接口；零成本、免服务器、免配置，极简开发首选 |
| **PocketBase** | [pocketbase.io](https://pocketbase.io) | 开源自托管，单文件启动，完全免费无额度限制 | 内置数据库 + 后台管理 + 注册登录 + 完整 API；自己随便部署在哪 |

### 4. 国内稳定免费库（国内访问快）

> 国内项目首选，延迟低、合规稳定

| 数据库名称 | 官方链接 | 核心免费权益 | 开发适配场景 |
|-----------|---------|-------------|-------------|
| **阿里云免费数据库** | [free.aliyun.com](https://free.aliyun.com) | 新用户免费 MySQL/PostgreSQL 试用 | 国内访问极快，适合国内项目 |
| **腾讯云 CloudBase** | [cloud.tencent.com/product/tcb](https://cloud.tencent.com/product/tcb) | 免费云数据库 + 云函数 + 存储 | 适合微信小程序、个人网站，开箱即用 |

---

## 附录

### 熟练度等级说明

| 等级 | 代号 | 描述 | 典型表现 |
|------|------|------|----------|
| 🟢 入门 | Beginner | 了解概念，能在指导下完成基本任务 | 能写出能跑的代码/设计，需要查阅文档 |
| 🔵 熟练 | Intermediate | 独立完成工作，理解原理和最佳实践 | 能独立负责模块，知道何时用什么方案 |
| 🟣 精通 | Advanced | 深入原理，能解决复杂问题，指导他人 | 能做技术选型、架构决策、性能极限优化 |

### 技能标签索引

| 标签 | 涵盖技能域 |
|------|-----------|
| `#frontend` | React, Vue, CSS, TypeScript, 工程化, 性能优化 |
| `#backend` | API设计, 数据库, 认证授权, 消息队列, 微服务 |
| `#mobile` | iOS, Android, 鸿蒙, React Native, Flutter |
| `#fullstack` | 全栈框架, BaaS, Serverless, 类型安全 |
| `#testing` | 自动化测试, TDD/BDD, 性能测试, 安全测试 |
| `#devops` | Docker, K8s, CI/CD, 云服务, 监控, IaC |
| `#architecture` | 系统设计, DDD, 架构模式, 技术选型 |
| `#database` | SQL, NoSQL, 缓存, 搜索引擎, 数据库运维 |
| `#product` | 需求分析, PRD, 原型设计, 数据驱动, 增长策略 |
| `#ui-design` | 色彩, 排版, 图标, Figma, 设计系统 |
| `#ux-design` | 用户研究, 交互设计, 信息架构, 无障碍 |
| `#brand-design` | LOGO, VI, 海报, AI创作, 印刷规范 |
| `#agent` | 215智能体角色, 17部门, 工程师, 设计师, 营销, 销售, 财务, 法务, 游戏开发, XR, MCP, 提示词工程 |

### API 分类标签索引

| 标签 | 涵盖 API |
|------|---------|
| `#mock-api` | JSONPlaceholder, ReqRes, MockAPI.io, httpbin, Mockoon |
| `#tool-api` | TimeAPI, IPAPI.co, TenAPI, UUID Generator, 企业信用API |
| `#ai-api` | Gemini, Mistral, DeepSeek, 通义千问, Tavily, 火山方舟, HuggingFace |
| `#data-api` | 高德地图, 百度地图, OpenWeather, 和风天气, TMDB, TuShare, NewsAPI, 聚合数据 |
| `#media-api` | Cloudinary, 百度OCR, Edge-TTS, Imgur, Remove.bg |
| `#auth-api` | GitHub OAuth, 微信开放平台, QQ互联, Google OAuth, 抖音开放平台 |
| `#ops-api` | GitHub API, SSL Labs, VirusTotal, Ping.pe, Cloudflare DNS |
| `#cloud-free` | Cloudflare, Vercel, 阿里云, 腾讯云, AWS Free Tier |
| `#api-directory` | Public APIs, RapidAPI, Any-API, awesome-free-apis |
| `#public-apis` | 1400+ API全量目录，15场景分组，详见 public-apis/SKILL.md |
| `#free-db-sql` | PlanetScale(MySQL), Neon(PostgreSQL), Supabase(PG+API) |
| `#free-db-nosql` | MongoDB Atlas, Upstash(Redis+Kafka) |
| `#free-db-serverless` | Vercel KV/Postgres, Cloudflare D1(SQLite), PocketBase(自托管) |
| `#free-db-cn` | 阿里云免费数据库, 腾讯云CloudBase |

---

## 五、Public APIs 全量目录

> 来源: [github.com/public-apis/public-apis](https://github.com/public-apis/public-apis) + [n0shake/Public-APIs](https://github.com/n0shake/Public-APIs) | 1400+ API | 70 分类
> 完整结构化数据: [public-apis-catalog.json](./public-apis/public-apis-catalog.json) | 自动触发技能: [public-apis/SKILL.md](./public-apis/SKILL.md)

### 23 大开发场景速查

| 场景 | 免费API推荐 | 典型项目 |
|------|-----------|---------|
| 🧪 Web开发/Mock | JSONPlaceholder, ReqRes, httpbin, Mockoon | 前端联调/接口测试 |
| 🤖 AI/机器学习 | Gemini, DeepSeek, Mistral, HuggingFace, Tavily | AI应用/Agent |
| 🗺️ 地图/LBS | 高德, 百度, OpenStreetMap, IPAPI.co | 地图应用/定位 |
| 🌤️ 天气/环境 | OpenWeather, 和风天气, Weatherstack | 天气应用 |
| 💰 金融/加密 | TuShare, Alpha Vantage, CoinGecko, ExchangeRate | 金融工具/量化 |
| 📰 新闻/内容 | TMDB, NewsAPI, HackerNews, Reddit | 内容平台 |
| 🔐 社交/登录 | GitHub OAuth, Google OAuth, 微信, Discord | 用户登录 |
| 🖼️ 图片/视频 | Unsplash, Cloudinary, Imgur, Remove.bg, Edge-TTS | 图片处理/图床 |
| 🏢 商业数据 | 聚合数据, Clearbit, Hunter.io | 企业信息查询 |
| 🛠️ 开发工具 | GitHub API, npm Registry, Docker Hub | DevOps/工具 |
| 🔒 安全/运维 | VirusTotal, Shodan, HaveIBeenPwned, SSL Labs | 安全检测 |
| 🍔 生活/健康 | Open Food Facts, Spoonacular, USDA | 健康应用 |
| 📚 教育/科学 | Wikipedia, arXiv, NASA, Open Library | 教育平台 |
| ⚽ 体育/娱乐 | TheSportsDB, PokeAPI, Trivia, Jokes | 娱乐应用 |
| 🏛️ 政府/开放数据 | Data.gov, World Bank, US Census | 数据分析 |
| 💳 支付/电商 | Stripe, Braintree, PayPal, Commerce Layer | 电商/支付 |
| 📊 数据分析 | Google Analytics, Matomo, PostHog, MixPanel | 数据分析/埋点 |
| 🔑 认证/验证 | Auth0, Firebase Auth, Clerk, reCAPTCHA | 用户认证 |
| 📱 通信/推送 | Twilio, SendGrid, Resend, OneSignal | 短信/邮件/推送 |
| 📷 二维码/条码 | QR Code API, QuickChart, Google Barcode | 二维码/扫码 |
| 🧠 NLP/翻译 | Google NLP, DeepL, LibreTranslate, 百度NLP | 文本分析/翻译 |
| 📸 截图/抓取 | Screenshot API, ScrapingBee, Apify | 网页截图/爬虫 |
| 📢 广告/SEO | SerpAPI, Google Ads, Facebook Marketing | 营销/SEO |

### 项目场景 → API 组合推荐

| 项目类型 | 推荐 API 组合 |
|---------|-------------|
| 电商网站 | Unsplash(商品图) + ExchangeRate-API(汇率) + Cloudinary(图片处理) |
| 社交APP | GitHub/Google OAuth(登录) + Imgur(图床) + Push通知 |
| 天气应用 | OpenWeather(全球) + 和风天气(国内) + AirVisual(空气质量) |
| 金融工具 | TuShare(A股) + Alpha Vantage(全球) + CoinGecko(加密) |
| AI应用 | Gemini(多模态) + DeepSeek(国内) + HuggingFace(开源) |
| 地图应用 | 高德(国内) + OpenStreetMap(全球) + IPAPI(IP定位) |
| 教育平台 | Wikipedia(百科) + arXiv(论文) + Open Library(图书) |
| 安全工具 | VirusTotal(检测) + Shodan(设备) + HaveIBeenPwned(泄露) |

---

## 六、AI驱动开发工作流

> 从模糊想法到可运行代码的完整开发工作流，13个Skill分三层协作
> 详细文档: [workflow/SKILL.md](./workflow/SKILL.md) | 核心机制: [GUARDRAILS.md](./workflow/GUARDRAILS.md) + [PROJECT-CONTEXT.md](./workflow/PROJECT-CONTEXT.md) | 实战技巧: [workflow-tips.md](./workflow/workflow-tips.md)

### 1. 工作流全景

这套工作流一共 13 个 Skill，分成三层：

**第一层：项目级（启动时用一次）**

从一个模糊的想法到一个可以开始写代码的项目骨架，走完这 7 步：

需求澄清 → 产品概述 → 技术栈选型 → 目录结构 → 开发规范 → 路线图规划 → 项目初始化

每一步的输出都是下一步的输入，像流水线一样环环相扣。走完之后，`specs/` 目录下会有一整套项目文档，项目目录也搭好了。

**第二层：功能级（反复使用）**

项目骨架搭好之后，就按照路线图一个功能一个功能地做。每个功能走这 4 步：

功能需求澄清 → 技术方案设计 → 任务规划 → 编码实现

路线图里有 10 个功能？那就跑 10 遍。如果已完成的功能需要改动，还有一个专门的迭代 Skill：

功能迭代变更 → 编码实现

**第三层：通用（随时使用）**

遇到 BUG 了？直接调 BUG 修复 Skill，不管你在哪个阶段都能用。

**一句话总结**：项目级走一遍打地基，功能级循环跑盖楼，通用级随叫随到修补丁。

### 2. 核心机制

| 机制 | 说明 | 文件 |
|------|------|------|
| 边界守卫（GUARDRAILS） | 每个Skill只做自己阶段的事，AI越界时自动拦截 | [GUARDRAILS.md](./workflow/GUARDRAILS.md) |
| 项目上下文协议（PROJECT-CONTEXT） | 每个Skill执行前必须读取specs/目录下所有文档，建立完整项目认知 | [PROJECT-CONTEXT.md](./workflow/PROJECT-CONTEXT.md) |

### 3. 项目级工作流（7个Skill）

| # | Skill名称 | 调用命令 | AI角色 | 输出文件 |
|---|----------|---------|--------|---------|
| 1 | 项目需求澄清 | `/project-requirements-clarification` | 好奇的合伙人 | `specs/项目描述.md` |
| 2 | 产品概述 | `/project-product-overview` | 首席产品官 | `specs/产品概述.md` |
| 3 | 技术栈选型 | `/project-tech-stack` | CTO | `specs/技术栈.md` |
| 4 | 目录结构 | `/project-structure` | 系统架构师 | `specs/项目结构.md` |
| 5 | 开发规范 | `/project-dev-standards` | 技术委员会 | `specs/开发规范.md` |
| 6 | 路线图规划 | `/project-roadmap-planning` | 技术产品经理 | `specs/开发路线图.md` |
| 7 | 项目初始化 | `/project-initialization` | DevOps工程师 | 项目骨架 + `docs/开发记录/初始化记录.md` |

### 4. 功能级工作流（5个Skill）

| # | Skill名称 | 调用命令 | AI角色 | 输出文件 |
|---|----------|---------|--------|---------|
| 8 | 功能需求澄清 | `/feature-requirements-clarification` | 产品经理 | `specs/features/{功能名}.md` |
| 9 | 技术方案设计 | `/feature-tech-design` | 系统架构师 | `specs/features/{功能名}_技术方案.md` |
| 10 | 任务规划 | `/feature-task-planning` | 技术主管 | `specs/features/{功能名}_任务规划.md` |
| 11 | 编码实现 | `/feature-implementation` | 高级开发工程师 | 代码 + `docs/开发记录/{功能名}_阶段报告.md` |
| 12 | 功能迭代变更 | `/feature-evolution` | 产品架构师 | 增量更新 `specs/features/` 文档 |

功能迭代变更的三种类型：
- **微调（Tweak）**：小改动，不涉及新需求
- **扩展（Extension）**：加新东西，需要新增验收标准
- **重构（Refactor）**：动了核心结构

### 5. 通用工作流（1个Skill）

| # | Skill名称 | 调用命令 | AI角色 | 硬规则 | 输出文件 |
|---|----------|---------|--------|--------|---------|
| 13 | BUG修复 | `/bugfix-workflow` | 高级调试工程师 | 没复现出来，不准改代码 | 修复代码 + 单元测试 + `docs/BUG修复文档/{BUG名}.md` |

修复流程：复现 → 定位 → 修复 → 单元测试 → 验证 → 报告

### 6. 实战技巧

> 完整技巧详见 [workflow-tips.md](./workflow/workflow-tips.md)

| # | 技巧 | 核心要点 |
|---|------|---------|
| 1 | 功能级规划和编码分开窗口 | 前三步同窗口，编码每任务新窗口 |
| 2 | 项目级规划一个窗口完成 | 7个Skill关联性强，同窗口上下文最清楚 |
| 3 | 提示词先润色再复用 | 建立提示词库，越用越强 |
| 4 | evolution vs 重新走 | ≤30%用evolution，≥70%重新走 |
| 5 | 阶段做完发现不对 | 用evolution提变更→更新文档→再执行 |
| 6 | 不懂就问 | AI干活时你学，正向循环 |
| 7 | 文档不同步立刻补 | 改了代码就要同步文档 |
| 8 | 文档花两分钟过一遍 | 越早发现问题，改起来越便宜 |
| 9 | 沟通黄金法则 | 主动调用Skill + 一次只做一件事 |
| 10 | AI搞不定按顺序试 | 换模型→优化提示词→拆任务→找参考→分析原因 |

---

## 七、AI 智能体角色库

> 来源: [agency-agents-zh](https://github.com/jnMetaCode/agency-agents-zh) | 215 角色 | 17 部门 | 50 中国市场原创
> 完整结构化数据: [agency-agents-catalog.json](./agency-agents/agency-agents-catalog.json) | 自动触发技能: [agency-agents/SKILL.md](./agency-agents/SKILL.md)

### 1. 角色库概览

| 部门 | 角色数 | 核心能力方向 | 中国原创 |
|------|--------|-------------|---------|
| 🛠️ 工程部 (Engineering) | 35 | 全栈/前端/后端/移动/DevOps/架构/数据/ML/安全/平台/SRE/嵌入式/固件/IoT/上位机/机械 | 4 |
| 🎨 设计部 (Design) | 8 | UI/UX研究/UX架构/品牌守护/图像提示词/视觉叙事/趣味注入/包容性视觉 | 0 |
| 📱 营销部 (Marketing) | 36 | 小红书/抖音/微信/B站/快手/电商/百度SEO/私域/直播/跨境/出海/增长/SEO/AI搜索 | 21 |
| 💰 付费媒体部 (Paid Media) | 7 | 广告审计/创意策略/PPC/程序化购买/搜索词分析/追踪归因 | 0 |
| 💼 销售部 (Sales) | 8 | 客户策略/销售教练/交易策略/需求挖掘/售前/外联/管线分析/提案 | 0 |
| 🏦 金融部 (Finance) | 8 | 记账/财务分析/财务预测/FP&A/欺诈检测/投资研究/发票/税务 | 0 |
| 👥 人力资源部 (HR) | 2 | 招聘/绩效评审 | 0 |
| ⚖️ 法务部 (Legal) | 2 | 合同审核/政策撰写 | 0 |
| 🚚 供应链部 (Supply Chain) | 4 | 库存预测/供应商评估/路线优化/供应链策略 | 0 |
| 📦 产品部 (Product) | 5 | 产品经理/Sprint排序/趋势研究/反馈分析/行为助推 | 0 |
| 📋 项目管理部 (Project Management) | 6 | 高级PM/项目守护/实验追踪/工作室制作/运营/Jira工作流 | 0 |
| 🧪 测试部 (Testing) | 9 | 证据采集/现实检验/API测试/性能基准/无障碍审计/结果分析/工具评估/工作流优化/嵌入式QA | 1 |
| 🎧 支持部 (Support) | 7 | 支持响应/分析报告/法律合规/执行摘要/财务追踪/基础设施维护/招聘 | 1 |
| ⚡ 专项部 (Specialized) | 46 | 智能体编排/提示词/MCP/文档生成/工作流/自动化治理/区块链/政务/AI政策/定价/风控/翻译/幕僚长 | 15 |
| 🥽 空间计算部 (Spatial Computing) | 6 | visionOS/Metal/XR交互/XR沉浸/座舱交互/终端集成 | 6 |
| 🎮 游戏开发部 (Game Development) | 20 | 游戏设计/关卡/叙事/技术美术/音频/Unity/Unreal/Godot/Roblox/Blender | 2 |
| 🎓 学术部 (Academic) | 6 | 人类学/地理/历史/叙事学/心理学/学习规划 | 0 |

### 2. 按部门速查

#### 🛠️ 工程部 — 35 角色

| 角色 | 核心能力 |
|------|---------|
| 全栈开发 | React/Next.js + Node.js + PostgreSQL 全链路 |
| 前端开发 | React/Vue/TypeScript/Tailwind CSS |
| 后端开发 | Node.js/Python/Java + API + 数据库 |
| 移动开发 | React Native/Flutter/SwiftUI/Kotlin |
| DevOps 工程师 | Docker/K8s/CI-CD/Terraform |
| QA 工程师 | 自动化测试/性能测试/安全测试 |
| 系统架构师 | 高可用/微服务/DDD/技术选型 |
| 数据工程师 | ETL/数据仓库/Spark/Flink |
| ML 工程师 | 模型训练/MLOps/特征工程 |
| 安全工程师 | 渗透测试/安全审计/合规 |
| 平台工程师 | 内部开发者平台/基础设施 |
| SRE | 可靠性/SLO/监控/故障响应 |
| 嵌入式工程师 | RTOS/驱动/固件/硬件调试 |
| 固件工程师 | MCU/OTA/Bootloader/低功耗 |
| IoT 工程师 | MQTT/边缘计算/设备管理 |
| 上位机工程师 | Qt/QML/Modbus/CAN/工业协议 |
| 机械设计工程师 | 传动/结构/DFMA/GB-ISO |
| 云基础架构师 | AWS/Azure/GCP/多云策略 |
| 数据库架构师 | 数据模型/分库分表/查询优化 |
| API集成专家 | REST/GraphQL/OAuth/接口治理 |
| 性能工程师 | Profiling/负载测试/缓存/优化 |
| 无障碍工程师 | WCAG/ARIA/辅助技术 |
| 可观测性工程师 | Prometheus/Grafana/OTel/链路追踪 |
| 混沌工程师 | 故障注入/韧性验证/GameDay |
| 发布工程师 | 版本管理/灰度发布/Feature Flags |
| 构建工程师 | Bazel/CMake/编译优化 |
| IaC工程师 | Terraform/Pulumi/Ansible/GitOps |
| 容器编排专家 | K8s/Docker/Helm/Service Mesh |
| CI/CD架构师 | Jenkins/GitHub Actions/流水线设计 |
| 成本优化工程师 | 云资源分析/FinOps/Right-sizing |
| 灾备专家 | RPO/RTO/容灾方案/演练 |
| 迁移专家 | 云迁移/数据迁移/Strangler Fig |
| 技术债管理师 | 代码质量/重构优先级/SonarQube |
| 技术负责人 | 技术决策/Code Review/团队方向 |

#### 🎨 设计部 — 8 角色

| 角色 | 核心能力 |
|------|---------|
| UI 设计师 | 视觉设计系统/组件库/无障碍 |
| UX 研究员 | 用户行为分析/可用性测试 |
| UX 架构师 | CSS体系/布局框架/实现指引 |
| 品牌守护者 | 品牌策略/一致性维护 |
| 图像提示词工程师 | AI图像生成/摄影美学/提示词 |
| 视觉叙事师 | 信息可视化/品牌叙事 |
| 趣味注入师 | 品牌个性/惊喜/趣味元素 |
| 包容性视觉专家 | 消除AI偏见/文化多样性 |

#### 📱 营销部 — 36 角色

**国内平台 (21):**

| 角色 | 核心能力 |
|------|---------|
| 小红书运营专家 | 种草笔记/达人合作/爆款公式 |
| 抖音策略师 | 算法推荐/爆款视频/直播带货 |
| 微信公众号运营 | 内容策略/社群/裂变/私域 |
| B站内容策略师 | UP主运营/弹幕文化/社区 |
| 快手策略师 | 下沉市场/老铁社区 |
| 中国电商运营专家 | 淘宝/天猫/拼多多/京东 |
| 百度SEO专家 | 百度算法/生态产品矩阵 |
| 私域流量运营师 | 企微SCRM/社群精细化 |
| 直播电商主播教练 | 主播培训/直播间运营 |
| 跨境电商运营专家 | Amazon/Shopee/Lazada |
| 微博运营策略师 | 热搜/超话/舆情管理 |
| 播客内容策略师 | 小宇宙/喜马拉雅 |
| 微信视频号运营 | 视频号生态/增长 |
| 知识付费产品策划 | 知识付费生态/商业化 |

**出海营销 (6):**

| 角色 | 核心能力 |
|------|---------|
| TikTok策略师 | 病毒式内容/算法优化 |
| Twitter互动官 | 实时互动/思想领袖 |
| Instagram策展师 | 视觉叙事/社区运营 |
| Reddit社区运营 | Reddit社区文化 |
| 应用商店优化师 | ASO/转化率 |
| 视频优化专家 | YouTube算法/留存/封面 |

**通用 (9):**

| 角色 | 核心能力 |
|------|---------|
| 增长黑客 | 低成本获客/增长实验 |
| 内容创作者 | 多平台内容策划 |
| SEO专家 | 技术SEO/内容优化/外链 |
| AI引文策略师 | AEO/GEO/ChatGPT可见性 |
| 智能搜索优化师 | AI代理任务完成率 |

#### 💰 付费媒体部 — 7 角色

| 角色 | 核心能力 |
|------|---------|
| 付费媒体审计师 | Google/Meta广告账户审计 |
| 广告创意策略师 | 文案/RSA优化/素材组 |
| PPC竞价策略师 | Google Ads/Amazon Ads |
| 追踪与归因专家 | GTM/GA4/归因模型 |

#### 💼 销售部 — 8 角色

| 角色 | 核心能力 |
|------|---------|
| 赢单策略师 | MEDDPICC/竞争定位/B2B |
| 售前工程师 | 技术Discovery/Demo/POC |
| Outbound策略师 | 信号驱动/多渠道触达/ICP |
| 投标策略师 | RFP/赢标叙事 |

#### 🏦 金融部 — 8 角色

| 角色 | 核心能力 |
|------|---------|
| 财务分析师 | 财务建模/估值/报表分析 |
| 财务预测分析师 | 收入预测/现金流/烧钱率 |
| 金融风控分析师 | 欺诈检测/风控策略 |
| 发票管理专家 | 增值税/金税系统 |
| 税务策略师 | 税务筹划/跨境税务 |

#### 👥 人力资源部 — 2 角色

| 角色 | 核心能力 |
|------|---------|
| 招聘专家 | Boss直聘/猎聘/拉勾 |
| 绩效管理专家 | OKR/KPI/360度反馈 |

#### ⚖️ 法务部 — 2 角色

| 角色 | 核心能力 |
|------|---------|
| 合同审查专家 | 民法典/合同风险/条款审查 |
| 制度文件撰写专家 | 个人信息保护法/数据合规 |

#### 🚚 供应链部 — 4 角色

| 角色 | 核心能力 |
|------|---------|
| 库存预测专家 | 需求预测/安全库存 |
| 供应商评估专家 | 供应商筛选/验厂审核 |
| 物流路线优化师 | 配送路线/成本优化 |

#### 📦 产品部 — 5 角色

| 角色 | 核心能力 |
|------|---------|
| 产品经理 | 全生命周期/战略规划/路线图 |
| Sprint排序师 | 需求优先级/Sprint规划 |
| 趋势研究员 | 行业趋势/技术前瞻 |
| 反馈分析师 | 用户反馈/洞察提炼 |
| 行为助推引擎 | 行为心理学/交互优化 |

#### 📋 项目管理部 — 6 角色

| 角色 | 核心能力 |
|------|---------|
| 高级项目经理 | 任务拆解/经验教训 |
| 工作室制片人 | 多项目组合/资源分配 |
| Jira工作流管家 | Git工作流/PR规范 |

#### 🧪 测试部 — 9 角色

| 角色 | 核心能力 |
|------|---------|
| API测试员 | API验证/性能测试 |
| 性能基准师 | 性能测试/容量规划 |
| 无障碍审核员 | WCAG/辅助技术实测 |
| 嵌入式QA工程师 | 硬件在环/固件自动化/OTA |

#### 🎧 支持部 — 7 角色

| 角色 | 核心能力 |
|------|---------|
| 支持响应师 | 工单处理/SLA合规 |
| 分析报告师 | 数据可视化/报告生成 |
| 法律合规检查师 | 合规审查/风险提示 |

#### ⚡ 专项部 — 46 角色

| 角色 | 核心能力 |
|------|---------|
| 智能体编排者 | 多Agent工作流编排 |
| 提示词工程师 | 系统提示词/思维链设计 |
| MCP构建器 | MCP服务器开发 |
| 文档生成器 | PDF/PPTX/DOCX/XLSX |
| 工作流架构师 | 工作流设计/智能体交互 |
| 自动化治理架构师 | n8n/业务自动化 |
| 区块链安全审计师 | 智能合约/形式化验证 |
| 政务数字化售前顾问 | 中国政务市场 |
| AI治理政策专家 | AI合规/治理 |
| 动态定价策略师 | 电商定价/促销策略 |
| 企业风险评估师 | 全面风险管理 |
| 技术翻译专家 | 中英双向/技术术语 |
| 幕僚长 | 战略运营/OKR/高管沟通 |
| 开发者布道师 | 开发者社区/技术内容 |

#### 🥽 空间计算部 — 6 角色

| 角色 | 核心能力 |
|------|---------|
| visionOS空间工程师 | SwiftUI体积式/Liquid Glass |
| XR界面架构师 | 空间交互/沉浸式AR-VR |
| XR沉浸式开发者 | WebXR/浏览器端AR-VR |

#### 🎮 游戏开发部 — 20 角色

| 角色 | 核心能力 |
|------|---------|
| 游戏设计师 | GDD/玩家心理/经济平衡 |
| 关卡设计师 | 布局/节奏/遭遇战 |
| 叙事设计师 | 分支对话/世界观 |
| 技术美术 | Shader/VFX/LOD |
| Unity架构师 | ScriptableObject/模块化 |
| Unreal系统工程师 | C++/Blueprint/Nanite/Lumen |
| Godot脚本开发者 | GDScript 2.0/C#/信号 |
| Roblox脚本工程师 | Luau/客户端-服务端 |
| Blender插件工程师 | Python插件/管线自动化 |

#### 🎓 学术部 — 6 角色

| 角色 | 核心能力 |
|------|---------|
| 人类学家 | 文化体系/民族志 |
| 历史学家 | 历史分析/物质文化 |
| 叙事学家 | 叙事理论/故事结构 |
| 学习规划师 | 考研/考公/司法考试 |

### 3. 项目场景→角色组合推荐

| 项目类型 | 推荐角色组合 |
|---------|-------------|
| **Web全栈项目** | 全栈开发 + UX架构师 + QA工程师 + DevOps |
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

*本文档基于 2026 年主流技术栈整理，持续更新中。*
