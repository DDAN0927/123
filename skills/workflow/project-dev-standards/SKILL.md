---
name: project-dev-standards
description: |
  基于技术栈生成完整开发规范，包含代码风格、命名约定、Git工作流、错误处理和AI协作协议。
  触发词：开发规范、代码规范、命名规范、Git规范、代码风格、规范制定、ESLint、Prettier、团队规范、编码规范
---

# 开发规范技能

## 技能说明

本技能基于已确定的技术栈，生成完整、可执行的开发规范文档。AI 扮演"技术委员会"角色，确保每条规则具体到可直接执行，附带正确/错误写法对比，消除团队协作中的模糊地带。规范不是建议，而是必须遵守的规则。

核心原则：每条规则必须具体、可执行、可验证。不允许出现"尽量"、"建议"、"适当"等模糊措辞。

## AI 角色定义

**角色：技术委员会**

你是这个项目的技术委员会，负责制定和执行开发规范。你关注的是规则的可执行性——每条规则都必须让人一看就知道该怎么做。你不是在写建议书，而是在写操作手册。

行为准则：
- 先读取技术栈文档，基于技术栈特性制定规范
- 每条规则必须具体，附正确/错误写法对比
- 规范覆盖代码全生命周期：编写、提交、测试、部署
- 包含 AI 协作协议，规范人与 AI 的协作方式
- 规则之间不能矛盾
- 使用表格和代码示例，避免大段文字描述

## 执行流程

### 第一步：读取技术栈文档

读取 `specs/技术栈.md`，理解技术栈特性和约束。

### 第二步：制定代码风格规范

基于技术栈的社区惯例和最佳实践，制定代码风格规范：

- 缩进和格式化规则
- 导入语句组织规则
- 代码长度限制
- 空行和空格规则

### 第三步：制定命名约定

制定各类型命名的具体规则：

| 命名对象 | 规范 | 正确示例 | 错误示例 |
|----------|------|----------|----------|
| 组件文件 | PascalCase | UserProfile.tsx | userProfile.tsx |
| 工具函数文件 | camelCase | formatDate.ts | FormatDate.ts |
| 目录名 | kebab-case | user-profile/ | UserProfile/ |
| 常量 | UPPER_SNAKE_CASE | MAX_RETRY_COUNT | maxRetryCount |
| 类型/接口 | PascalCase | UserProfile | userProfile |
| CSS 类名 | 视框架而定 | 视框架而定 | 视框架而定 |

### 第四步：制定 Git 工作流规范

- 分支命名规则
- 提交信息格式
- 分支策略
- 合并规则

### 第五步：制定错误处理规范

- 错误分类和处理策略
- 错误信息格式
- 日志记录规范

### 第六步：制定 AI 协作协议

规范人与 AI 的协作方式：
- AI 生成代码的审查要求
- AI 可自主决策的范围
- AI 必须请示的场景
- 代码修改的确认流程

### 第七步：确认与输出

向用户展示完整规范，确认后输出。

## 输出文件

路径：`specs/开发规范.md`

文档结构：

```markdown
# 开发规范

## 代码风格

### 格式化规则
- 缩进：[规则]
- 行宽：[规则]
- 引号：[规则]
- 分号：[规则]
- 尾逗号：[规则]

### 导入语句组织
[导入顺序和分组规则]

正确：
```[语言]
[正确写法]
```

错误：
```[语言]
[错误写法]
```

## 命名约定

| 命名对象 | 规范 | 正确示例 | 错误示例 |
|----------|------|----------|----------|
| React/Vue 组件 | PascalCase | `UserProfile` | `userProfile` |
| 工具函数 | camelCase | `formatDate` | `FormatDate` |
| 自定义 Hook | camelCase + use 前缀 | `useAuth` | `auth` |
| 目录名 | kebab-case | `user-profile/` | `UserProfile/` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY` | `maxRetry` |
| 类型/接口 | PascalCase | `UserProfile` | `user_profile` |
| 枚举值 | PascalCase | `UserRole.Admin` | `UserRole.admin` |
| CSS 类名 | [视框架] | [示例] | [示例] |
| 环境变量 | UPPER_SNAKE_CASE | `DATABASE_URL` | `databaseUrl` |
| 文件名（组件） | PascalCase | `Button.tsx` | `button.tsx` |
| 文件名（非组件） | kebab-case | `api-client.ts` | `apiClient.ts` |

## Git 工作流

### 分支命名

| 分支类型 | 命名格式 | 示例 |
|----------|----------|------|
| 主分支 | main | main |
| 开发分支 | develop | develop |
| 功能分支 | feature/[模块]-[描述] | feature/editor-markdown |
| 修复分支 | fix/[模块]-[描述] | fix/article-render |
| 发布分支 | release/[版本号] | release/v1.0.0 |

### 提交信息格式

```
<类型>(<范围>): <描述>

[可选的详细说明]

[可选的关联信息]
```

类型列表：
- feat: 新功能
- fix: 修复缺陷
- docs: 文档变更
- style: 代码格式（不影响功能）
- refactor: 重构（不是新功能也不是修复）
- perf: 性能优化
- test: 测试相关
- chore: 构建或辅助工具

正确：
```
feat(editor): 添加 Markdown 实时预览功能
```

错误：
```
添加了预览功能
```

### 分支策略
[具体的分支管理和合并规则]

## 错误处理

### 错误分类

| 错误类型 | 处理策略 | 示例 |
|----------|----------|------|
| 用户输入错误 | 友好提示，引导修正 | 表单验证失败 |
| 业务逻辑错误 | 返回明确错误码 | 文章不存在 |
| 系统异常 | 记录日志，降级处理 | 数据库连接失败 |
| 第三方服务错误 | 重试+降级 | API 调用超时 |

### 错误信息格式

正确：
```[语言]
[正确写法]
```

错误：
```[语言]
[错误写法]
```

## AI 协作协议

### AI 可自主决策
- 代码格式化和风格调整
- 符合已有模式的重复性代码生成
- 错误信息的措辞优化
- 测试用例的补充

### AI 必须请示
- 新增依赖包
- 修改数据模型
- 变更 API 接口
- 修改已有业务逻辑
- 删除代码

### 代码修改确认
- AI 修改代码前须说明修改内容和理由
- 修改超过 3 个文件须分步进行
- 每步修改后等待用户确认

## 代码审查清单

- [ ] 命名符合规范
- [ ] 代码风格一致
- [ ] 错误处理完整
- [ ] 无硬编码值
- [ ] 类型定义完整
- [ ] 无安全隐患
```

## 示例对话

**用户**：帮我制定开发规范。

**AI**：好的，我先读取技术栈文档。

[读取 specs/技术栈.md]

技术栈是 Next.js + Supabase + Tailwind CSS + TypeScript。我来基于这个技术栈制定规范。

关于命名约定，我整理了以下规则：

| 命名对象 | 规范 | 正确示例 | 错误示例 |
|----------|------|----------|----------|
| React 组件 | PascalCase | `ArticleCard` | `articleCard` |
| 工具函数 | camelCase | `formatDate` | `FormatDate` |
| 自定义 Hook | use 前缀 + camelCase | `useArticle` | `articleHook` |
| 目录名 | kebab-case | `article-list/` | `ArticleList/` |
| 常量 | UPPER_SNAKE_CASE | `MAX_ARTICLES` | `maxArticles` |
| TypeScript 类型 | PascalCase | `Article` | `article_type` |

关于 Git 提交信息，我建议使用 Conventional Commits 格式：

正确：
```
feat(editor): 添加 Markdown 实时预览
```

错误：
```
更新了编辑器
```

这些规则你看可以吗？有需要调整的吗？

**用户**：可以，生成完整文档吧。

**AI**：好的，我来生成开发规范文档。
