---
name: testing-devops
description: |
  测试与运维技能。当用户需要测试、部署、监控、CI/CD、Docker时自动激活。
  触发词：测试、部署、上线、Docker、K8s、CI/CD、监控、GitHub Actions、
  自动化测试、E2E、性能测试、安全、运维、服务器、云服务。
---

# 测试与运维技能

## 自动选型规则

| 场景 | 推荐方案 |
|------|---------|
| 单元测试 | Vitest + Testing Library |
| E2E测试 | Playwright (首选) / Cypress |
| API测试 | Vitest + Supertest / Postman |
| CI/CD | GitHub Actions |
| 容器化 | Docker + Docker Compose |
| 小团队部署 | Vercel(前端) + Railway(后端) |
| 国内部署 | 阿里云ECS + RDS + OSS |
| 监控 | Sentry(错误) + Uptime Kuma(可用性) |

## 测试规范

### 单元测试模板 (Vitest)
```typescript
import { describe, it, expect, vi } from 'vitest';
import { userService } from './user.service';

describe('UserService', () => {
  it('should create user with valid data', async () => {
    const data = { phone: '13800138000', nickname: 'Test' };
    const user = await userService.create(data);
    expect(user.phone).toBe(data.phone);
  });

  it('should reject duplicate phone', async () => {
    const data = { phone: '13800138000', nickname: 'Test' };
    await expect(userService.create(data)).rejects.toThrow('已存在');
  });
});
```

### E2E测试模板 (Playwright)
```typescript
import { test, expect } from '@playwright/test';

test('登录流程', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[data-testid="phone"]', '13800138000');
  await page.fill('[data-testid="password"]', '123456');
  await page.click('[data-testid="submit"]');
  await expect(page).toHaveURL('/home');
});
```

## Docker 部署模板

### Dockerfile (Node.js)
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
EXPOSE 3000
CMD ["node", "dist/main.js"]
```

### docker-compose.yml
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://postgres:123456@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_PASSWORD: 123456
    volumes:
      - pgdata:/var/lib/postgresql/data
  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
volumes:
  pgdata:
  redisdata:
```

## GitHub Actions CI/CD

```yaml
name: CI/CD
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm run test
      - run: npm run build

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
```

## 上线检查清单

- [ ] 环境变量已配置 (生产环境)
- [ ] 数据库迁移已执行
- [ ] 域名 + SSL 证书已配置
- [ ] 错误监控已接入 (Sentry)
- [ ] 日志收集已配置
- [ ] 备份策略已设置
- [ ] 限流/防刷已配置
- [ ] CORS 已限制为生产域名
- [ ] 性能基线已记录
- [ ] 回滚方案已准备
