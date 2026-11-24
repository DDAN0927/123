"""后端 /api/market/kline 与前端 drawerBars 的逐根一致性校验。

前置：
    node backend/tests/parity_gen.js index.html backend/tests/parity_js.json
    node backend/tests/parity_kline_gen.js index.html backend/tests/parity_kline_js.json
    python -m uvicorn backend.app.main:app --port 8000      # 另开一个终端
    python backend/tests/test_parity_api.py

判定：
- 根数必须相等（差一根就说明聚合或切片逻辑不同）
- 每根 t 必须完全相等
- 数值只允许 1e-12 量级浮点末位差异
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
BASELINE = Path(__file__).with_name("parity_kline_js.json")
TOL = 1e-12
FIELDS = ("o", "h", "l", "c", "v")


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def rel(a: float, b: float) -> float:
    if a == b:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def main() -> int:
    if not BASELINE.exists():
        print(f"[FAIL] 缺少基准 {BASELINE}，请先跑 node parity_kline_gen.js")
        return 1

    try:
        health = get("/api/health")
    except (urllib.error.URLError, ConnectionError) as e:
        print(f"[FAIL] 后端未启动或不可达: {e}")
        return 1
    print(f"后端 {health['version']} | provider={health['provider']['provider']}\n")

    cases = json.loads(BASELINE.read_text("utf-8"))["cases"]
    fails: list[str] = []
    worst_all = 0.0
    checked = 0

    for c in cases:
        label = f"{c['code']:<7} {c['range']}/{c['period']}"
        resp = get(f"/api/market/kline?code={c['code']}&range={c['range']}&period={c['period']}")
        bars = resp["data"]

        if len(bars) != c["n"]:
            fails.append(f"{label}: 根数 前端={c['n']} 后端={len(bars)}")
            print(f"  {label}  [FAIL] 根数 {c['n']} → {len(bars)}")
            continue

        worst = 0.0
        bad_date = 0
        for a, b in zip(bars, c["bars"]):
            if a["t"] != b["t"]:
                bad_date += 1
            for f in FIELDS:
                worst = max(worst, rel(float(a[f]), float(b[f])))
        if bad_date:
            fails.append(f"{label}: {bad_date} 根日期不一致")
        if worst > TOL:
            fails.append(f"{label}: 最大相对误差 {worst:.3e} 超阈值")
        worst_all = max(worst_all, worst)
        checked += 1
        flag = "ok" if (not bad_date and worst <= TOL) else "FAIL"
        print(f"  {label}  n={len(bars):<4} 最大相对误差={worst:.2e}  {flag}")

    print()
    print(f"用例 {checked}/{len(cases)} 通过，最大相对误差 {worst_all:.2e}")
    if fails:
        print("=== 失败明细 ===")
        for f in fails:
            print("  [FAIL]", f)
        return 1
    print("结论：后端 K 线（含周/月聚合与边界组合）与前端 drawerBars 一致，可安全切换数据源。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
