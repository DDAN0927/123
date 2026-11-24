# 回归探针

这份目录以前在 `.gitignore` 里,只存在于做过改动的那台机器上 —— 换句话说,
「20 个探针 300+ 条断言全绿」是一句**无法被他人复现**的话。现在 `verify-*` /
`probe-*` / `contrast.js` 入库,报告里引用的证据才站得住。

## 怎么跑

前置:

- Node 18+(脚本用 `require`,没有 ESM)
- Playwright 装在 `../_baseline/node_modules/playwright`(即 `deliverables/gstack/_baseline/`,
  该目录仍被忽略,需要 `npm i playwright` 自己装)
- Windows 上用 Edge:`chromium.launch({ channel: 'msedge' })`(脚本里已写死;
  Linux/macOS 上跑要把它改成 `chromium` 并 `npx playwright install chromium`)

单个:

```sh
node verify-orphan-holding.js
```

批量:

```sh
sh _qa_run.sh verify-*.js probe-*.js contrast.js   # 结果写进 _qa_logs/<name>.log
```

## 两个必须知道的坑

1. **一律带 `?api=off`**。所有探针都以 `file://` 打开 `index.html?api=off`。
   不带这个参数时,`http(s)` 环境下前端会自动探测 `http://127.0.0.1:8000` 并改走后端数据,
   同一份断言在两台机器上会因为后端是否在跑而得出不同结果。
2. **断言条数不是契约**。改动会让它变(比如 29 → 52)。报告里写的数字是当时实测,
   不是要求。要的是「0 FAIL」,不是「等于某个数」。
3. **`verify-deploy.js` 是例外,它做 `http` 而不是 `file://`**。这是唯一一个需要
   真实后端的探针,所以它自己用 `child_process` 起停 uvicorn(端口 18325 / 18326,
   避开常用的 8000),前置条件只剩「Python 装好了 `backend/requirements.txt`」。
   端口被占就改脚本顶部两个常量。

## 约定

- 退出码 0 = 通过,1 = 失败。`ALL PASS` 型探针不逐条打印,只看退出码。
- 每条断言带实际值:`ok('现金按成本退回', cond, '500000.00 -> 518640.00')`。
  没有实际值的断言在失败时等于没说。
- **变红先怀疑探针**。已经发生过三次:
  - 可读性段跑在「恢复股票池」之后,量到的是元素不存在;
  - 修完之后两次取样落在同一主题(页面初始主题随系统偏好),标着「暗色/亮色」实际量了同一套;
  - 对账探针首跑出现 8.5e-6 的权重差,查实是 `liveTick` 在等待期间漂移了 `last`。
- **给「相等」类断言配一段对照**。`verify-diag-source.js` 的 C 段会把旧实现塞回去,
  断言面板数字必须因此变红 —— 没有这一段,A 和 B 可能只是「两边读了同一份缓存」。

## 清单

| 文件 | 管什么 | 输出 |
|---|---|---|
| `verify-acct.js` | 账户、成交、费用、今日盈亏、存储 sanitize | ALL PASS |
| `verify-api-bridge.js` | 前端数据桥与 FastAPI 后端的字段/数值一致性 | 18 条 |
| `verify-borrow.js` | 借鉴 QuantFlow Pro 的四个面板(纪律/周月K/分散度/温度计) | 34 条 |
| `verify-bughunt.js` | localStorage 与输入的注入/污染面 | 12 条 |
| `verify-deploy.js` | 部署链路:制品静检 / 开发态 / 鉴权态 / 前端真实接入(自己起停服务) | 51 条 |
| `verify-diag-source.js` | 诊断面板(RSI/MACD/BOLL/止损)与 K 线图同源 | 48 条 |
| `verify-brand.js` / `verify-brand2.js` | 品牌命名与标题 | 退出码 |
| `verify-fmt.js` | 价格/百分比/大数格式 | 退出码 |
| `verify-ma-contrast.js` | MA5/10/20 三线在亮暗主题下的对比度(图形件 3:1) | 27 条 |
| `verify-mobile-menu.js` | 移动端导航菜单 | 退出码 |
| `verify-n1.js` / `verify-n2.js` / `verify-n3.js` | 三轮迭代的回归合集 | 退出码 |
| `verify-orphan-holding.js` | 持仓掉出股票池:不静默蒸发 + 按成本注销 | 52 条 |
| `verify-pf-parity.js` | 持仓/纪律改动前后用 `git HEAD` 旧文件对账 | 14 条 |
| `verify-py.js` | 拼音搜索 | 退出码 |
| `verify-r2motion.js` / `verify-r6b.js` / `verify-r7.js` | 动效、滚动、交互 | 15 条 / 退出码 / 退出码 |
| `verify-readable.js` | 字号与行高可读性 | 退出码 |
| `verify-round2.js` | 第二轮验收合集 | 退出码 |
| `verify-strip.js` | 顶部行情条 | 退出码 |
| `verify-thermo-quality.js` | 温度计四维缺失态与权重归一 | 34 条 |
| `verify-tide.js` | 大盘温度计数值与分档 | 33 条 |
| `verify-touch.js` | 触控目标尺寸 | 退出码 |
| `probe-selftest.js` | 跑页内自检(`#selftestPanel`),读通过数 | JSON |
| `probe-layout.js` | 各断点的横向溢出扫描 | 退出码 |
| `probe-mobile.js` | 390px 下关键区块可见性 | 退出码 |
| `probe-invisible.js` | 不可见元素扫描(display/visibility/opacity) | 退出码 |
| `probe-nav.js` | 导航锚点与滚动位置 | 退出码 |
| `contrast.js` | 全页文本对比度扫描(WCAG 4.5:1,亮暗各一遍) | 违规计数 |

`qa-*.js` 与 `shot-*.js` 是一次性排查脚本和截图工具,不纳入回归集,也不入库。
