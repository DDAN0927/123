"""前后端序列一致性校验。

用法（在项目根目录执行）:
    node backend/tests/parity_gen.js index.html backend/tests/parity_js.json
    python backend/tests/test_parity.py

判定口径：
  - 日期：必须 100% 相等（日期错了说明时区/起点逻辑错，属真 bug）
  - 数值：记录最大相对误差。若 == 0 则前后端逐位一致；若 > 0 但在 1e-12 量级，
    属 math.* 与 Math.* 的浮点实现差异，可接受但**不得对外宣称"逐位相同"**。
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.providers.mock import SERIES_DAYS, SymParams, gen_series, hash_str  # noqa: E402

BASELINE = Path(__file__).with_name("parity_js.json")

CASES = [
    {"code": "600519", "price": 1624.5, "vol": 0.27, "drift": 0.09, "mcap": 20412},
    {"code": "300750", "price": 258.4, "vol": 0.38, "drift": 0.14, "mcap": 11368},
    {"code": "AAPL", "price": 242.7, "vol": 0.24, "drift": 0.12, "mcap": 36210},
    {"code": "BTC", "price": 96420, "vol": 0.62, "drift": 0.24, "mcap": 19120},
]

FIELDS = ("o", "h", "l", "c", "v")


def rel_err(a: float, b: float) -> float:
    if a == b:
        return 0.0
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom


def main() -> int:
    if not BASELINE.exists():
        print(f"[FAIL] 缺少基准文件 {BASELINE}，请先跑 node parity_gen.js")
        return 1

    js = json.loads(BASELINE.read_text("utf-8"))
    js_by_code = {c["code"]: c for c in js["cases"]}

    fails: list[str] = []
    print(f"前端 SERIES_DAYS = {js['series_days']} / 后端 = {SERIES_DAYS}")
    if int(js["series_days"]) != SERIES_DAYS:
        fails.append("SERIES_DAYS 不一致")

    worst = 0.0
    for case in CASES:
        code = case["code"]
        ref = js_by_code.get(code)
        if not ref:
            fails.append(f"{code}: 基准缺失")
            continue

        seed = hash_str(code)
        if seed != ref["seed"]:
            fails.append(f"{code}: 种子不一致 前端={ref['seed']} 后端={seed}")

        py = gen_series(SymParams(**case))
        if len(py) != ref["n"]:
            fails.append(f"{code}: 长度 前端={ref['n']} 后端={len(py)}")
            continue

        date_mismatch = sum(1 for a, b in zip(py, ref["bars"]) if a["t"] != b["t"])
        if date_mismatch:
            fails.append(f"{code}: {date_mismatch}/{len(py)} 根日期不一致")

        case_worst = 0.0
        worst_field = ""
        for a, b in zip(py, ref["bars"]):
            for f in FIELDS:
                e = rel_err(a[f], b[f])
                if e > case_worst:
                    case_worst, worst_field = e, f
        worst = max(worst, case_worst)

        last_py, last_js = py[-1]["c"], ref["last_close"]
        print(
            f"  {code:<8} n={len(py):<5} 末收 后端={last_py:.6f} 前端={last_js:.6f} "
            f"最大相对误差={case_worst:.3e}{' (' + worst_field + ')' if worst_field else ''}"
        )

    print()
    if fails:
        print("=== 不一致项 ===")
        for f in fails:
            print("  [FAIL]", f)

    if worst == 0.0 and not fails:
        print("结论：前后端序列**逐位一致**（最大相对误差为 0），可安全迁移。")
        return 0
    if worst < 1e-12 and not fails:
        print(f"结论：无结构差异，仅浮点末位差异（最大相对误差 {worst:.2e}），可安全迁移。")
        print("     对外表述应为「同算法同种子，数值一致到 1e-12」，不要写「逐字节相同」。")
        return 0

    print(f"结论：存在实质差异（最大相对误差 {worst:.3e}），迁移会导致 K 线跳变，需先修平。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
