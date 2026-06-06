---
name: fullstack-dev
description: |
  全栈开发技能。当用户需要从零搭建完整项目、快速MVP验证、或同时涉及前后端时自动激活。
  触发词：全栈、从零开始、MVP、快速原型、完整项目、Supabase、
  Serverless、BaaS、部署、上线、Vercel、Cloudflare。
---

# 全栈开发技能

## 自动选型规则

| 项目特征 | 推荐方案 |
|---------|---------|
| 快速MVP验证 | Next.js + Supabase + Vercel + Clerk |
| SaaS产品 | Next.js + Stripe + Auth0 + PostgreSQL + Resend |
| 国内全栈 | Vue3/Nuxt + NestJS + MySQL + 阿里云 |
| 小程序+后端 | uni-app + NestJS + MySQL + Redis + 腾讯云 |
| 个人项目 | Next.js + Supabase + Vercel (全免费) |
| 企业级 | Next.js/Nuxt + Spring Boot + MySQL + Redis + 阿里云 |

## 快速启动模板

### T3 Stack (推荐 - TypeScript全栈)
```
Next.js 14 (App Router + SSR/SSG)
TypeScript (端到端类型安全)
tRPC (类型安全API)
Prisma (ORM)
Tailwind CSS (样式)
NextAuth/Auth.js (认证)
```

### BaaS 快速方案 (最快出活)
```
Supabase (数据库 + Auth + Storage + Realtime)
Vercel (前端部署 + Serverless)
Clerk/Auth0 (认证，或用Supabase Auth)
Stripe/LemonSqueezy (支付)
Resend (邮件)
```

### 国内全栈方案
```
前端：Vue3 + Vite + Pinia + Vant/Element Plus
后端：NestJS + Prisma + MySQL + Redis
认证：JWT + 微信登录
部署：阿里云 ECS + OSS + CDN
支付：微信支付 + 支付宝
短信：阿里云SMS / 腾讯云SMS
```

## 项目初始化清单

### 1. 项目脚手架
```bash
# Next.js 全栈
npx create-next-app@latest --typescript --tailwind --app

# Vue3 + Vite
npm create vite@latest my-app -- --template vue-ts

# NestJS 后端
npx @nestjs/cli new api

# 全栈 Monorepo
npx create-turbo@latest my-app
```

### 2. 必装依赖
```bash
# 前端
npm i @tanstack/react-query zustand zod axios

# 后端
npm i @prisma/client zod bcrypt jsonwebtoken
npm i -D prisma @types/bcrypt @types/jsonwebtoken
```

### 3. 环境变量模板 (.env)
```
# 数据库
DATABASE_URL="postgresql://user:pass@localhost:5432/db"

# 认证
JWT_SECRET="your-secret-key"
JWT_EXPIRES_IN="7d"

# 第三方
SUPABASE_URL="https://xxx.supabase.co"
SUPABASE_ANON_KEY="xxx"

# 微信
WX_APPID="xxx"
WX_SECRET="xxx"

# 部署
VERCEL_TOKEN="xxx"
```

## 部署方案

| 场景 | 前端 | 后端 | 数据库 | 费用 |
|------|------|------|--------|------|
| 个人项目 | Vercel | Vercel Serverless | Supabase | 免费 |
| 国内项目 | 阿里云OSS+CDN | 阿里云ECS | RDS MySQL | ~100元/月 |
| 海外SaaS | Vercel | Railway/Render | Supabase/Neon | ~$20/月 |
| 高并发 | Cloudflare | K8s集群 | RDS+Redis | 按量计费 |
