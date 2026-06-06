---
name: frontend-dev
description: |
  前端开发全栈技能。当用户开发网页、小程序、H5、APP界面时自动激活。
  触发词：前端、页面、组件、Vue、React、小程序、uni-app、CSS、Tailwind、TypeScript、
  H5、微信小程序、响应式、动画、表单、列表、登录页、首页、详情页、Dashboard。
---

# 前端开发技能

## 自动选型规则

根据项目特征自动选择技术栈：

| 项目特征 | 推荐技术栈 |
|---------|-----------|
| 纯Web应用 | React + Next.js 或 Vue + Nuxt.js |
| 小程序 | uni-app(Vue3) + uView Plus |
| H5移动端 | Vue3 + Vant + vw适配 |
| 管理后台 | React + Ant Design / Vue + Element Plus |
| 营销活动页 | Vue3/React + Tailwind CSS + GSAP动画 |
| 需要SEO | Next.js(SSR/SSG) 或 Nuxt.js |
| 创意动效/视觉冲击 | React + ReactBits (reactbits.dev) |

## 动效 & 创意组件库

### ReactBits (reactbits.dev)
130+ 高度可定制的动画组件和背景，即插即用，让项目瞬间脱颖而出。

**安装方式**（shadcn CLI）：
```bash
npx shadcn@latest add @react-bits/<ComponentName>-<TS|JS>-<TW|CSS>
# 示例：安装 Aurora 背景（TypeScript + Tailwind 版本）
npx shadcn@latest add @react-bits/Aurora-TS-TW
```

**组件分类**：

| 分类 | 说明 | 典型组件 |
|------|------|---------|
| Backgrounds | 全屏动态背景 | Aurora、Dot Field、Line Waves、Soft Aurora、Radar、Shape Grid、Grainient、Balatro、Ballpit、Beams |
| Text Animations | 文字动效 | Shiny Text、Split Text、Gradient Text、Blur Text、Count Up |
| Animations | 交互动画 | Blob Cursor、Splash Cursor、Magnet Lines、Antigravity、Pixel Trail、Magic Rings、Ribbons、Orbit Images、Metallic Paint |
| Components | UI 组件 | Dock、Card、Morphing Dialog、Tilted Card、Spotlight Card |

**适用场景**：
- 首页 Hero 区动态背景（Aurora / Line Waves / Soft Aurora）
- 鼠标跟随特效（Blob Cursor / Splash Cursor）
- 文字入场动效（Shiny Text / Gradient Text / Blur Text）
- 作品集卡片展示（Tilted Card / Spotlight Card / Orbit Images）
- 导航栏动效（Dock / Magnet Lines）

**技术栈支持**：JS + CSS / TS + CSS / JS + Tailwind / TS + Tailwind（四种组合可选）

> 官网：https://reactbits.dev/
> GitHub：https://github.com/DavidHDev/react-bits (38.9K+ Stars)

## 核心框架选择

### React 项目
- 框架：Next.js 14+ (App Router)
- 状态：Zustand(轻量) 或 Redux Toolkit(大型)
- 数据获取：TanStack Query v5
- 样式：Tailwind CSS + CSS Modules
- 类型：TypeScript 5.x 严格模式
- 表单：react-hook-form + zod 校验

### Vue 项目
- 框架：Vue 3 + Composition API
- 构建：Vite 6
- 状态：Pinia
- 路由：Vue Router 4
- 样式：Tailwind CSS 或 SCSS
- UI库：Element Plus(后台) / Vant(移动) / uView(小程序)

### 小程序项目
- 框架：uni-app (Vue3)
- UI：uView Plus / Uni UI
- 条件编译：#ifdef MP-WEIXIN / #ifdef H5
- 云开发：uniCloud 或 微信云开发
- 支付：uni.requestPayment

## 代码规范

### 文件结构 (Vue3 + Vite)
```
src/
├── api/           # 接口请求
├── assets/        # 静态资源
├── components/    # 公共组件
│   ├── common/    # 通用组件
│   └── business/  # 业务组件
├── composables/   # 组合式函数
├── pages/         # 页面
├── router/        # 路由
├── stores/        # Pinia状态
├── styles/        # 全局样式
├── types/         # TS类型定义
└── utils/         # 工具函数
```

### 文件结构 (React + Next.js)
```
src/
├── app/           # Next.js App Router
│   ├── (auth)/    # 路由组
│   ├── api/       # API Routes
│   └── layout.tsx
├── components/    # 组件
│   ├── ui/        # 基础UI组件
│   └── features/  # 业务组件
├── hooks/         # 自定义Hooks
├── lib/           # 工具库
├── stores/        # 状态管理
├── types/         # TS类型
└── styles/        # 全局样式
```

## 性能优化清单

1. 路由懒加载 (React.lazy / Vue defineAsyncComponent)
2. 图片优化 (next/image 或 <img loading="lazy"> + WebP/AVIF)
3. 代码分割 (Dynamic Import + Vite manualChunks)
4. 缓存策略 (TanStack Query staleTime + Service Worker)
5. 首屏优化 (SSR/SSG + 预加载关键资源)
6. 包体积分析 (rollup-plugin-visualizer)

## 常见问题速查

| 问题 | 解决方案 |
|------|---------|
| 首屏白屏久 | SSR/SSG + 骨架屏 + 预加载 |
| 列表卡顿 | 虚拟滚动 + 分页加载 + 防抖搜索 |
| 样式闪烁 | CSS Modules + Tailwind JIT |
| 跨端样式不一致 | 条件编译 + CSS Reset + normalize |
| 小程序包体积超限 | 分包加载 + 图片CDN + 按需引入 |
