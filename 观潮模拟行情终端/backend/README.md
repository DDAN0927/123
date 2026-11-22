# 观潮后端 · Cloudflare Worker + D1

一个文件的后端:邮箱密码登录、跨设备同步(自选/对比/提醒/模拟账户)、A 股快照缓存、每 5 分钟检查价格提醒(可选 Resend 邮件)。

## 1. 准备

- 一个 Cloudflare 账号(免费版即可)
- Node.js 18+
- 可选:Resend 账号(免费额度,用于邮件提醒)

```powershell
npm install -g wrangler
wrangler login
```

## 2. 创建数据库

在 `backend` 目录执行:

```powershell
wrangler d1 create guanchao
```

把输出里的 `database_id` 填进 `wrangler.toml` 的 `database_id`。
然后建表:

```powershell
wrangler d1 execute guanchao --remote --file=./schema.sql
```

## 3. 配置

`wrangler.toml` 里:

- `ALLOWED_ORIGIN`:填你页面的**精确来源**,例如 `https://your-site.pages.dev`。不要填 `*`,也不要带尾斜杠——通配符会让任意站点代访客发起登录/注册,把按 IP 的限流整个绕开(代码会显式忽略 `*`,但别依赖这层兜底)。
- `ALERT_FROM`:发件人地址,必须是 Resend 里验证过的域名邮箱。

可选邮件:

```powershell
wrangler secret put RESEND_API_KEY
```

不配置也能用,只是不会发邮件;提醒仍会在同步时写回云端。

## 4. 部署

```powershell
wrangler deploy
```

得到类似 `https://guanchao-api.yourname.workers.dev` 的地址,访问 `/api/health` 应返回 `{"ok":true}`。
`wrangler.toml` 里的 cron `*/5 * * * *` 会自动生效,每 5 分钟检查一次提醒。

## 5. 前端接入

1. 打开 `index.html`,点导航栏的云朵图标。
2. API 地址填 Worker 根地址(不要带 `/api`)。
3. 输入邮箱和 8 位以上密码,点「注册」。
4. 首次注册会把本机自选、对比、提醒、模拟账户上传;换设备登录会自动拉取。
5. 需要覆盖时用「上传本机 / 拉取云端」;可勾选自动同步。

> 地址限制:前端只接受 `https://` 且满足以下之一的地址——与页面同源、`*.workers.dev`、`localhost` / `127.0.0.1`。绑了自定义域名(如 `https://api.example.com`)时,请把该域名加入 `index.html` 的 `CLOUD_HOST_ALLOW` 白名单,否则会被拒绝(界面上会提示「该地址不会被使用」)。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| POST | `/api/register` | `{email,password}` → `{token,email}` |
| POST | `/api/login` | `{email,password}` → `{token,email}` |
| POST | `/api/logout` | Bearer token |
| GET | `/api/state` | Bearer;返回 `{state,updatedAt}` |
| PUT | `/api/state` | Bearer;`{state:{...}}`,上限 400KB |
| GET | `/api/snapshot?part=1` | 全市场 A 股快照,前半部分;`part=2` 为后半部分,各缓存 10 分钟 |

快照由服务端分页抓取东方财富(每页 100 条),拆成 `part=1/2` 两次请求,每次 30 页,避开免费版 Worker 单次 50 个子请求的上限。前端「同步真实 A 股」会优先走这两个接口,失败再回退到浏览器 JSONP。

## 安全与限制

- 密码使用 PBKDF2-SHA256(30,000 次)加盐存储;令牌 30 天,存于浏览器 localStorage。生产环境建议改为 HttpOnly Cookie。
- 这是个人/小团队自建服务:状态整体存为一个 JSON,D1 免费额度足够;用户量增大后应拆分自选/提醒/交易表。
- 快照接口是公开的、带 10 分钟缓存;请勿高频调用。东方财富是非官方接口,可能限流。
- 邮件提醒依赖 Resend 免费额度(约 100 封/天),发件域名需验证。
- 页面内的行情、诊断与模拟交易仍是演示性质,不构成投资建议。
