"""一键铺演示数据（走真实 HTTP 接口，不直接写库）

为什么需要这个
--------------
答辩/演示最怕两件事：现场点「AI 生成行程」等 40 秒然后模型抽风，或者数据库是空的、
看不出功能。这个脚本把「一个像样的行程」提前铺好：套好模板、记了几笔账、
勾了两项、生成了装备清单、开了分享链接。

之后演示只需要讲，不需要等。

用法
----
    # 先把两个进程起来
    bash scripts/start_all.sh

    # 另开一个终端
    .venv/Scripts/python.exe scripts/demo_seed.py
    .venv/Scripts/python.exe scripts/demo_seed.py --city 成都 --days 4 --budget 4500
    .venv/Scripts/python.exe scripts/demo_seed.py --base http://127.0.0.1:8080 --user demo

设计约束
--------
* **只走公开接口**：不碰 H2 文件库。这样脚本本身就是一份接口冒烟测试，
  哪天接口改坏了，跑一遍就知道。
* **可重复执行**：同名行程先删再建，不会越跑越多。
* **AI 那步允许失败**：模型没配 / 超时就跳过，其余数据照铺。
  演示时 AI 生成是「现场加分项」，不该是「没有就演示不了」。
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request

# 系统代理会拦 localhost（Windows 上很常见），这里一律绕过
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token = ""

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.token:
            # 用 X-Auth-Token 而不是 Authorization: Bearer —— 平台边缘 WAF 会拦后者
            req.add_header("X-Auth-Token", self.token)
        try:
            with _OPENER.open(req, timeout=60) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return e.code, {"detail": raw.decode("utf-8", "replace")[:200]}
        except urllib.error.URLError as e:
            return 0, {"detail": f"连不上 {self.base}：{e.reason}"}


def step(ok: bool, label: str, extra: str = "") -> None:
    print(f"{'✓' if ok else '·'} {label}{('  ' + extra) if extra else ''}")


def main() -> int:
    ap = argparse.ArgumentParser(description="铺一份可用于演示的行程")
    ap.add_argument("--base", default="http://127.0.0.1:8080", help="SpringBoot 对外地址")
    ap.add_argument("--user", default="demo", help="演示账号（不存在会自动注册）")
    ap.add_argument("--password", default="demo123456")
    ap.add_argument("--city", default="北京")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--budget", type=int, default=3000)
    ap.add_argument("--start", default="", help="出发日期 YYYY-MM-DD，默认 10 天后")
    ap.add_argument("--no-ai", action="store_true", help="跳过 AI 生成（只铺确定性数据）")
    args = ap.parse_args()

    api = Api(args.base)

    # ---------- 1. 账号
    code, r = api.call("POST", "/api/auth/register", {"username": args.user, "password": args.password})
    if code == 200:
        step(True, f"注册演示账号 {args.user}")
        api.token = r["token"]
    else:
        code, r = api.call("POST", "/api/auth/login", {"username": args.user, "password": args.password})
        if code != 200:
            print(f"✗ 账号既注册不了也登录不了：{code} {r.get('detail')}")
            print("  如果这个账号是以前建的、密码不同，换个 --user 或手动改密码")
            return 1
        step(True, f"登录已有账号 {args.user}")
        api.token = r["token"]

    # ---------- 2. 清掉同名旧行程（可重复执行）
    start = args.start or (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    title = f"{args.city} {args.days} 天"
    code, r = api.call("GET", "/api/trips")
    removed = 0
    for t in (r.get("trips") or []) if code == 200 else []:
        if t.get("title") == title:
            api.call("DELETE", f"/api/trips/{t['id']}")
            removed += 1
    if removed:
        step(True, f"清掉 {removed} 份同名旧行程（保证可重复执行）")

    # ---------- 3. 建行程
    code, r = api.call(
        "POST",
        "/api/trips",
        {
            "city": args.city,
            "days": args.days,
            "budget": args.budget,
            "start_date": start,
            "title": title,
        },
    )
    if code != 200:
        print(f"✗ 建行程失败：{code} {r.get('detail')}")
        return 1
    trip = r["trip"]
    tid = trip["id"]
    step(True, f"新建行程「{trip['title']}」", f"{start} · {args.days} 天 · 预算 ¥{args.budget}")

    # ---------- 4. 套模板（确定性，不依赖模型）
    code, r = api.call("POST", f"/api/trips/{tid}/templates/classic")
    step(
        code == 200,
        "套用「三天两夜经典」模板",
        f"{r.get('items', '?')} 项安排" if code == 200 else r.get("detail", ""),
    )

    # ---------- 5. 装备清单
    code, r = api.call("POST", f"/api/trips/{tid}/packing")
    if code == 200:
        groups = r.get("groups") or []
        n = sum(len(g.get("items") or []) for g in groups)
        step(True, "生成行前装备清单", f"{len(groups)} 组 / {n} 项（来源：{r.get('source', '?')}）")
    else:
        step(False, "生成行前装备清单", r.get("detail", ""))

    # ---------- 6. 记几笔账（覆盖三个分类，让预算面板有分布）
    expenses = [
        ("交通", "高铁往返", 553, 0),
        ("住宿", "酒店两晚", 680, 0),
        ("门票", "故宫门票", 60, 1),
        ("餐饮", "簋街夜宵", 128, 1),
    ]
    ok = 0
    for cat, name, amount, day in expenses:
        code, _ = api.call(
            "POST",
            f"/api/trips/{tid}/expenses",
            {"category": cat, "title": name, "amount": amount, "day_index": day},
        )
        ok += code == 200
    step(ok == len(expenses), "记 4 笔账", f"{ok}/{len(expenses)} 成功")

    # ---------- 7. AI 生成（允许失败）
    # 放在「勾选」之前：plan 是整段替换每日行程，会重置勾选状态（revise 才按标题保留）。
    # 演示时要展示的是「revise 保留勾选」，所以先把勾打在这一版行程上。
    if args.no_ai:
        step(False, "跳过 AI 生成（--no-ai）")
    else:
        code, r = api.call("POST", f"/api/trips/{tid}/plan")
        if code == 200:
            step(True, "AI 结合攻略库生成按天行程", f"{r.get('items', '?')} 项")
        else:
            step(False, "AI 生成未成功（不影响演示，模板版已铺好）", str(r.get("detail"))[:60])

    # ---------- 8. 勾三项（1 项行前 + 2 项行程）
    # 勾行程条目是刻意的：只有行程条目会被 revise 重建，
    # 才能演示「改一句需求，已勾选的还在」。
    code, r = api.call("GET", f"/api/trips/{tid}")
    prep, days = [], []
    if code == 200:
        prep = r["trip"].get("prep") or []
        days = r["trip"].get("itinerary") or []
    targets = ([prep[0]] if prep else []) + [i for d in days for i in (d.get("items") or [])][:2]
    ticked = 0
    for it in targets:
        code, _ = api.call("PATCH", f"/api/trips/{tid}/items/{it['id']}", {"done": True})
        ticked += code == 200
    step(
        ticked > 0,
        f"勾选 {ticked} 项（1 行前 + {max(0, ticked - 1)} 行程）",
        "用来演示进度与「改行程保留勾选」",
    )

    # ---------- 9. 分享链接
    code, r = api.call("POST", f"/api/trips/{tid}/share")
    share = args.base + r["url"] if code == 200 else ""

    # ---------- 汇总
    code, r = api.call("GET", f"/api/trips/{tid}")
    print()
    if code == 200:
        t = r["trip"]
        e = t.get("expenses") or {}
        spent, left = float(e.get("spent") or 0), float(e.get("remaining") or 0)
        print("── 演示数据就绪 ─────────────────────────────")
        print(f"  账号      {args.user} / {args.password}")
        print(f"  行程      {t['title']}（{t.get('start_date') or '日期待定'}）")
        print(
            f"  进度      {t['progress']['done']}/{t['progress']['total']} 项（{t['progress']['percent']}%）"
        )
        print(f"  预算      已花 ¥{spent:,.2f} / 剩余 ¥{left:,.2f}（{e.get('percent')}%）")
        print(f"  条目      {len(t.get('prep') or [])} 项行前 + {len(t.get('itinerary') or [])} 天行程")
        if share:
            print(f"  分享      {share}")
        print()
        print("── 演示顺序建议 ─────────────────────────────")
        print("  1. 行程列表 → 点进详情（倒计时 / 进度条 / 预算面板）")
        print("  2. 勾一条 → 进度条即时变化（条目粒度写入）")
        print("  3. 记账区记一笔 → 已花与剩余立刻更新")
        print("  4. 「📋 套用模板」→ 换一套节奏（只替换行程，行前清单不动）")
        print("  5. 「🤖 按我说的改」→ 输入「第三天想换室内，怕下雨」→ 勾选状态保留")
        print("  6. 「🖨 导出」→ 日历文件 / 打印版；「🔗 分享」→ 只读链接")
        print("  7. 聊天页 → 问「故宫门票多少钱」→ 看协作轨迹与攻略库覆盖提示")
    else:
        print(f"读回行程失败：{code} {r.get('detail')}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
