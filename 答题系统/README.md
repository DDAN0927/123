# 在线考试答题系统

基于前后端分离架构的在线考试答题系统，支持管理员题库管理、学生在线答题、自动判分等功能。

## 技术栈

- **后端**：Node.js + Express + sql.js（SQLite）+ JWT
- **前端**：Vue 3 + Vite + Element Plus + Vue Router + Axios

## 环境要求

- [Node.js](https://nodejs.org/) 16 及以上版本

## 快速启动

### 1. 克隆项目

```bash
git clone https://github.com/DDAN0927/DD.git
cd DD/答题系统
```

### 2. 安装后端依赖

```bash
cd exam-system-server
npm install
```

### 3. 安装前端依赖

```bash
cd ../exam-system-frontend
npm install
```

### 4. 构建前端

```bash
npm run build
```

构建完成后会在 `exam-system-frontend/dist` 目录生成静态文件，后端会自动托管该目录。

### 5. 启动后端服务

```bash
cd ../exam-system-server
npm start
```

启动成功后会看到以下提示：

```
考试系统后端已启动: http://localhost:8088
默认账号: DDAN/admin123 (管理员), student/123456 (学生)
```

### 6. 访问系统

浏览器打开 http://localhost:8088 即可使用。

## 公网访问（非同一局域网访问）

默认情况下系统只能在同一局域网内访问，如需让不同网络的人也能访问，可使用 **Cloudflare Tunnel** 内网穿透。

### 1. 下载 cloudflared

前往 [Cloudflare Tunnel 官方页面](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) 下载对应系统的 `cloudflared` 客户端。

Windows 也可使用以下命令下载：

```bash
curl -L -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
```

### 2. 启动隧道

确保后端服务已在运行（http://localhost:8088），然后新开一个终端执行：

```bash
cloudflared tunnel --url http://localhost:8088
```

启动后会输出类似以下内容：

```
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
|  https://xxxx-xxxx-xxxx.trycloudflare.com                                                  |
+--------------------------------------------------------------------------------------------+
```

### 3. 分享公网地址

将生成的 `https://xxxx-xxxx-xxxx.trycloudflare.com` 地址分享给其他人，即可在不同网络下访问答题系统。

> **注意**：
> - 每次启动隧道会生成不同的公网地址，重启后需重新分享
> - 隧道需要保持运行，关闭终端则公网访问失效
> - 该地址无需注册 Cloudflare 账号即可使用（免费临时隧道）

## 默认账号

| 角色   | 用户名    | 密码       |
| ------ | --------- | ---------- |
| 管理员 | DDAN      | admin123   |
| 学生   | student   | 123456     |

## 项目结构

```
答题系统/
├── exam-system-server/          # 后端
│   ├── server.js                # 主服务文件（API接口 + 静态文件托管）
│   ├── database.js              # 数据库初始化与连接
│   └── package.json
├── exam-system-frontend/        # 前端
│   ├── src/
│   │   ├── api/                 # API 请求封装
│   │   ├── components/          # 公共组件
│   │   ├── router/              # 路由配置
│   │   ├── utils/               # 工具函数
│   │   ├── views/               # 页面
│   │   │   ├── admin/           # 管理员页面（题库管理、成绩管理、学生管理）
│   │   │   └── student/         # 学生页面（在线答题、我的成绩）
│   │   ├── App.vue
│   │   └── main.js
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── .gitignore
```

## 功能说明

- **管理员**：题库增删改查、随机组卷、成绩查看、学生账号管理（添加/删除/重置密码）
- **学生**：在线答题、自动判分、成绩查询
- **安全**：JWT 登录认证、角色权限拦截（ADMIN/STUDENT）
- **适配**：支持 PC 端和手机端访问
