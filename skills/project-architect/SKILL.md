---
name: project-architect
description: |
  项目架构与选型技能。当用户开始新项目、需要技术选型、系统设计、或遇到架构问题时自动激活。
  触发词：新项目、技术选型、架构设计、系统设计、高并发、高可用、
  微服务、数据库设计、项目结构、技术方案、重构、性能瓶颈、
  架构评审、系统重构、高可用设计、容量规划、系统架构、架构咨询、性能瓶颈分析。
---

# 项目架构与选型技能

## 技术选型决策树

```
新项目
├── 纯前端展示？
│   ├── 需要SEO？ → Next.js(SSR) / Nuxt.js(SSR)
│   ├── 管理后台？ → React+Ant Design / Vue+Element Plus
│   └── 营销H5？ → Vue3+Vant+GSAP
│
├── 需要后端？
│   ├── 快速MVP？ → Supabase + Vercel (零后端代码)
│   ├── 中等复杂度？ → NestJS + Prisma + PostgreSQL
│   ├── 企业级？ → Spring Boot + MyBatis-Plus + MySQL
│   └── 高性能？ → Go + Gin + PostgreSQL
│
├── 需要移动端？
│   ├── 小程序为主？ → uni-app (一套代码多端)
│   ├── APP为主？ → React Native / Flutter
│   └── 鸿蒙原生？ → ArkTS + ArkUI
│
└── 需要AI能力？
    ├── 国内直连？ → DeepSeek / 通义千问 / 火山方舟
    ├── 海外？ → Gemini / Mistral / OpenAI
    └── 开源模型？ → HuggingFace Inference API
```

## 数据库选型

| 场景 | 推荐数据库 | 理由 |
|------|-----------|------|
| 通用业务 | PostgreSQL | 功能最强，JSONB/全文搜索/扩展 |
| 国内传统项目 | MySQL 8.0 | 生态成熟，运维资源多 |
| 缓存/会话/队列 | Redis 7 | 内存KV，性能极高 |
| 文档/日志 | MongoDB | 灵活Schema，聚合管道 |
| 搜索引擎 | Elasticsearch | 全文检索/日志分析 |
| 时序数据 | ClickHouse | OLAP分析，列式存储 |

## 架构模式选择

### 单体架构 (项目初期推荐)
```
适用：用户<10万，团队<5人，快速验证
优点：开发快、部署简单、调试方便
缺点：后期扩展受限
技术：Next.js全栈 / NestJS单体
```

### 微服务架构 (中后期演进)
```
适用：用户>50万，团队>10人，业务复杂
优点：独立部署、技术异构、故障隔离
缺点：运维复杂、分布式事务
技术：Spring Cloud / NestJS Microservices + gRPC
```

### Serverless架构 (低频/事件驱动)
```
适用：流量波动大、事件驱动、成本敏感
优点：按量付费、零运维、自动扩缩
缺点：冷启动、调试困难、供应商锁定
技术：Vercel Edge / Cloudflare Workers / AWS Lambda
```

## 高并发方案

```
用户请求 → CDN(静态资源)
         → 负载均衡(Nginx/SLB)
         → API网关(限流/鉴权/路由)
         → 服务集群(水平扩展)
         → Redis缓存(热点数据)
         → 消息队列(削峰填谷)
         → 数据库(读写分离+分库分表)
```

## 项目启动流程

1. **需求分析** → 确定核心功能(MVP)
2. **技术选型** → 用上面的决策树
3. **数据库设计** → ER图 + 表结构
4. **API设计** → OpenAPI文档 + Mock服务
5. **前端开发** → 组件库 + 页面开发
6. **后端开发** → 接口实现 + 单元测试
7. **联调测试** → E2E测试 + 性能测试
8. **部署上线** → Docker + CI/CD + 监控
9. **迭代优化** → 数据驱动 + A/B测试

## ADR 架构决策记录模板

```markdown
# ADR-001: 选择 NestJS 作为后端框架

## 状态：已采纳

## 背景
项目需要同时支持Web端和小程序端，团队熟悉TypeScript

## 决策
采用 NestJS + Prisma + PostgreSQL

## 理由
1. 前后端统一TypeScript，降低沟通成本
2. NestJS模块化架构，适合中大型项目
3. Prisma类型安全ORM，开发效率高
4. PostgreSQL功能全面，JSONB支持灵活数据

## 后果
- 优点：开发效率高，类型安全，生态好
- 缺点：NestJS学习曲线较陡，运行时性能不如Go
```
