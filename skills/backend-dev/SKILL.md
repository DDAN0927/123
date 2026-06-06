---
name: backend-dev
description: |
  后端开发技能。当用户开发服务器、接口、数据库、业务逻辑时自动激活。
  触发词：后端、接口、API、数据库、服务器、登录、认证、权限、CRUD、
  Node.js、Python、Java、Go、RESTful、GraphQL、Redis、消息队列、微服务。
---

# 后端开发技能

## 自动选型规则

| 项目特征 | 推荐技术栈 |
|---------|-----------|
| 快速API开发 | Node.js + NestJS + Prisma + PostgreSQL |
| AI/数据相关 | Python + FastAPI + SQLAlchemy + PostgreSQL |
| 企业级系统 | Java + Spring Boot 3 + MyBatis-Plus + MySQL |
| 高性能服务 | Go + Gin + GORM + PostgreSQL |
| 已有Vue/React前端 | Node.js + NestJS (统一TS技术栈) |
| 国内小程序后端 | Node.js + Express/Koa + MySQL + Redis |

## API 设计规范

### RESTful 接口标准
```
GET    /api/v1/users          # 列表(支持分页/筛选/排序)
GET    /api/v1/users/:id      # 详情
POST   /api/v1/users          # 创建
PUT    /api/v1/users/:id      # 全量更新
PATCH  /api/v1/users/:id      # 部分更新
DELETE /api/v1/users/:id      # 删除
```

### 统一响应格式
```typescript
interface ApiResponse<T> {
  code: number;      // 0=成功, 非0=错误码
  message: string;   // 提示信息
  data: T;           // 业务数据
  timestamp: number; // 时间戳
}

interface PageResponse<T> {
  list: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}
```

### 错误码规范
```
1xxxx - 通用错误 (10001参数错误, 10002权限不足)
2xxxx - 用户模块 (20001用户不存在, 20002密码错误)
3xxxx - 业务模块 (30001库存不足, 30002订单异常)
5xxxx - 系统错误 (50001数据库异常, 50002第三方服务异常)
```

## 认证授权方案

### JWT Token (推荐)
```typescript
// 登录返回
{ accessToken: 'xxx', refreshToken: 'xxx', expiresIn: 7200 }

// 请求头
Authorization: Bearer <accessToken>

// Token刷新
POST /api/v1/auth/refresh { refreshToken } → 新的accessToken
```

### 微信小程序登录
```
1. 前端 wx.login() 获取 code
2. 后端 code + appId + appSecret 换取 openid/session_key
3. 后端生成自定义 Token 返回前端
```

## 数据库操作规范

### Prisma (Node.js 推荐)
```prisma
model User {
  id        String   @id @default(cuid())
  phone     String   @unique
  nickname  String?
  avatar    String?
  status    Int      @default(1)  // 1正常 2禁用
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}
```

### 查询优化
1. 必须加索引：WHERE条件字段、JOIN关联字段、ORDER BY排序字段
2. 避免 SELECT *，只查需要的字段
3. 大列表必须分页，默认 pageSize=20
4. N+1问题：用 include/prefetch 预加载关联
5. 热数据走 Redis 缓存，设置合理 TTL

## 文件结构 (NestJS)
```
src/
├── modules/
│   ├── auth/           # 认证模块
│   │   ├── auth.controller.ts
│   │   ├── auth.service.ts
│   │   ├── auth.module.ts
│   │   └── dto/
│   ├── user/           # 用户模块
│   └── common/         # 公共模块
│       ├── filters/    # 异常过滤器
│       ├── guards/     # 守卫
│       ├── interceptors/ # 拦截器
│       └── decorators/ # 自定义装饰器
├── config/             # 配置
├── prisma/             # 数据库
└── main.ts
```

## 安全清单

- [ ] 所有输入用 Zod/class-validator 校验
- [ ] SQL 参数化查询，禁止拼接
- [ ] 密码 bcrypt 加密存储
- [ ] JWT Token 设置合理过期时间
- [ ] 接口限流 (rate-limit)
- [ ] CORS 白名单配置
- [ ] 敏感数据脱敏返回
- [ ] HTTPS 强制
