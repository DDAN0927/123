# 开发环境配置指南 (D盘版)

> 所有工具和依赖都放在 D 盘，不占用 C 盘空间

## 目录结构

```
D:\dev-tools\                    # 开发环境根目录
├── node-global\                  # npm 全局包 (typescript/vue-cli/vite等)
├── node-cache\                   # npm 缓存
├── pnpm-home\                   # pnpm 全局包
├── pnpm-store\                  # pnpm 内容寻址存储
├── python-projects\              # Python 项目目录
├── projects\                     # 通用项目目录
└── scripts\                      # 初始化脚本

D:\tools\                        # 已有工具
├── Git\                          # Git 2.47.1

C:\Program Files\nodejs\          # Node.js v24.14.0 (系统安装)
```

## 快速开始（3步）

### 第1步：初始化基础环境

```powershell
# 以管理员身份打开 PowerShell，执行:
Set-ExecutionPolicy Bypass -Scope Process -Force
cd D:\xm\skills\dev-env-setup
.\init-dev-env.ps1
```

这会自动完成：
- ✅ 创建 D:\dev-tools 目录结构
- ✅ 配置 npm (prefix/cache/registry)
- ✅ 安装 pnpm 并配置到 D 盘
- ✅ 配置 Git 全局设置
- ✅ 设置 PATH 环境变量 (User级)
- ✅ 安装常用全局包 (10个)

### 第2步：安装 Python（可选）

```powershell
cd D:\xm\skills\dev-env-setup
.\install-python.ps1
```

这会：
- ✅ 下载安装 Python 3.12 到 D:\dev-tools\Python
- ✅ 配置 pip 清华镜像源
- ✅ 安装 15 个常用 Python 包
- ✅ 添加到 PATH

### 第3步：配置 VS Code

```powershell
# 安装推荐扩展 (26个)
cd D:\xm\skills\dev-env-setup
.\install-vscode-extensions.ps1

# 复制 VS Code 设置
# 方式A: VS Code → Ctrl+Shift+P → Open User Settings(JSON) → 粘贴 vscode-settings.json 内容
# 方式B: 直接复制文件到 %APPDATA%\Code\User\settings.json
```

---

## 验证安装

重新打开终端后运行：

```bash
node --version      # v24.14.x
npm --version       # 10.x
pnpm --version      # 9.x
git --version       # 2.47.1
python --version    # 3.12.x (如果安装了)
code --version      # VSCode 版本
```

---

## 环境变量一览

| 变量名 | 值 | 用途 |
|--------|-----|------|
| `Path` (User) | `D:\dev-tools\node-global` | npm全局包可执行文件 |
| `Path` (User) | `D:\dev-tools\pnpm-home` | pnpm全局包可执行文件 |
| `Path` (User) | `D:\tools\Git\cmd` | Git 命令 |
| `Path` (User) | `C:\Program Files\nodejs` | Node.js 命令 |
| `NODE_PATH` (User) | `D:\dev-tools\node-global\node_modules` | Node.js 模块查找路径 |

---

## 常用全局包清单

### npm 全局包 (已预装)

| 包名 | 用途 |
|------|------|
| typescript | TypeScript 编译器 |
| ts-node | 直接运行 TS 文件 |
| @vue/cli | Vue 项目脚手架 |
| create-vite | Vite 脚手架 |
| tailwindcss | Tailwind CSS CLI |
| prettier | 代码格式化 |
| eslint | 代码检查 |
| nodemon | Node 自动重启 |
| pm2 | 进程管理器 |
| serve | 静态文件服务器 |

### Python 包 (可选安装)

| 包名 | 用途 |
|------|------|
| fastapi + uvicorn | Python Web API |
| sqlalchemy | ORM |
| requests / httpx | HTTP 客户端 |
| pydantic | 数据校验 |
| pytest | 测试框架 |
| black + ruff | 格式化 + Lint |

---

## VS Code 推荐扩展 (26个)

核心: Volar, ESLint, Prettier, Tailwind CSS IntelliSense
Vue: TypeScript Vue Plugin, uni-app VSCode Extension
Git: GitLens, Git Graph
效率: Error Lens, Path Intellisense, Todo Tree, REST Client
美化: Material Icon Theme, One Dark Pro

详见 [vscode-extensions.js](./vscode-extensions.js)

---

## 新建项目模板命令

```bash
# Vue3 + Vite 项目
pnpm create vite my-app --template vue-ts
cd my-app && pnpm install

# React + Next.js 项目
npx create-next-app@latest my-app --typescript --tailwind --app

# uni-app 小程序
npx degit dcloudio/uni-preset-vue#vite-ts my-uniapp
cd my-uniapp && pnpm install

# NestJS 后端
npx @nestjs/cli new api --package-manager=pnpm

# FastAPI 后端
mkdir my-api && cd my-api
python -m venv venv
.\venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy
```
