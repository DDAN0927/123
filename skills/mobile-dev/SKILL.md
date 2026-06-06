---
name: mobile-dev
description: |
  移动端开发技能。当用户开发APP、移动应用、鸿蒙应用时自动激活。
  触发词：APP、移动端、iOS、Android、鸿蒙、React Native、Flutter、
  uni-app App端、推送、离线、应用商店、上架。
---

# 移动端开发技能

## 自动选型规则

| 项目特征 | 推荐技术栈 |
|---------|-----------|
| 跨平台+JS生态 | React Native + Expo |
| 跨平台+高性能 | Flutter + Riverpod |
| 小程序+App一套代码 | uni-app (App端) |
| 国内生态+原生体验 | 鸿蒙 ArkTS + ArkUI |
| 纯iOS | Swift + SwiftUI |
| 纯Android | Kotlin + Jetpack Compose |
| 已有Vue前端团队 | uni-app (统一技术栈) |
| 已有React前端团队 | React Native (统一技术栈) |

## React Native 项目规范

### 技术栈组合
```
React Native 0.74+ / Expo SDK 51+
TypeScript 严格模式
React Navigation 6 路由
Zustand 状态管理
TanStack Query 数据获取
react-native-mmkv 本地存储
expo-image 图片缓存
```

### 文件结构
```
src/
├── app/           # 路由页面
├── components/    # 组件
│   ├── ui/        # 基础组件
│   └── business/  # 业务组件
├── hooks/         # 自定义Hooks
├── services/      # API服务
├── stores/        # 状态管理
├── utils/         # 工具函数
├── constants/     # 常量
└── types/         # 类型定义
```

## uni-app App端规范

### 关键差异处理
```javascript
// #ifdef APP-PLUS
// App端特有代码：原生模块调用、权限申请
// #endif

// #ifdef MP-WEIXIN
// 微信小程序特有代码
// #endif

// nvue 原生渲染页面（长列表/动画密集页面）
// vue  webview渲染页面（普通页面）
```

### 性能要点
1. 长列表用 nvue + list 组件
2. 图片用 CDN + 缩略图 + 懒加载
3. 避免频繁 setData，批量更新
4. 分包加载，主包 < 2MB
5. 首屏数据预取

## 推送通知方案

| 平台 | 推送服务 |
|------|---------|
| Android | 极光推送 / 个推 / 华为/小米/OPPO厂商通道 |
| iOS | APNs (必须) |
| 鸿蒙 | 华为推送 |
| uni-app | uni-push (聚合) |

## 上架清单

### iOS App Store
- [ ] Apple 开发者账号 ($99/年)
- [ ] App Store Connect 配置
- [ ] 隐私政策 URL
- [ ] 应用截图 (6.7寸 + 5.5寸)
- [ ] 审核注意事项：无热更新、无虚拟支付、隐私合规

### Android 各商店
- [ ] 签名证书 (.jks/.keystore)
- [ ] 应用加固 (360加固/腾讯乐固)
- [ ] 华为/小米/VIVO/OPPO开发者账号
- [ ] 隐私政策 + 用户协议

### 鸿蒙 AppGallery
- [ ] 华为开发者账号
- [ ] DevEco Studio 打包 .app 文件
- [ ] AGC 配置
