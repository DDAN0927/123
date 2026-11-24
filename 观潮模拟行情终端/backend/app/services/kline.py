"""K 线区间切片、周/月聚合、均线。

逐行对齐前端 index.html：
  rangeData()   → slice_range()
  aggBars()     → aggregate()
  drawerBars()  → bars_for()
  movingAvg()   → moving_avg()

对齐是硬要求：前端保留离线回退路径（后端不可用时用本地 genSeries + 本地聚合），
若两套聚合口径不同，同一标的会在"在线/离线"两种状态下画出不同的周 K。
backend/tests/test_parity.py 会用前端真实源码做基准比对。
"""

from __future__ import annotations

# 前端: const RANGE_MAP = { '1W': 5, '1M': 22, '3M': 66, '6M': 126, '1Y': 252, '5Y': 1300 };
RANGE_MAP: dict[str, int] = {
    "1W": 5,
    "1M": 22,
    "3M": 66,
    "6M": 126,
    "1Y": 252,
    "5Y": 1300,
}

# 前端: const DH_CANDLE_MAX = 170; 聚合后超限从最旧端截尾
DH_CANDLE_MAX = 170

PERIOD_MULT = {"W": 5, "M": 21}
SUPPORTED_PERIODS = {"D", *PERIOD_MULT}
SUPPORTED_RANGES = {"1W", "1M", "3M", "6M", "1Y", "5Y"}


class UnsupportedRange(ValueError):
    """1D 分时在前端是本地合成的（genIntraday），后端不伪造分时。"""


def slice_range(bars: list[dict], range_key: str) -> list[dict]:
    if range_key == "1D":
        raise UnsupportedRange("1D")
    n = RANGE_MAP.get(range_key, 22)
    return bars[-n:] if n < len(bars) else list(bars)


def _valid(bar: dict) -> bool:
    """前端 drawerBars 的残行过滤：o/h/l/c 必须是有限正数。"""
    for k in ("o", "h", "l", "c"):
        v = bar.get(k)
        if v is None:
            return False
        try:
            f = float(v)
        except (TypeError, ValueError):
            return False
        if not (f > 0) or f != f or f in (float("inf"), float("-inf")):
            return False
    return True


def aggregate(bars: list[dict], mult: int) -> list[dict]:
    """等价前端 aggBars：o 取组首、c 取组尾、h/l 取极值、v 求和、t 取组首。"""
    if mult <= 1:
        return list(bars)
    out: list[dict] = []
    for i in range(0, len(bars), mult):
        g = bars[i : i + mult]
        if not g:
            break
        out.append(
            {
                "t": g[0]["t"],
                "o": g[0]["o"],
                "h": max(b["h"] for b in g),
                "l": min(b["l"] for b in g),
                "c": g[-1]["c"],
                "v": sum(float(b.get("v") or 0) for b in g),
            }
        )
    return out


def moving_avg(arr: list[float], w: int) -> list[float | None]:
    """等价前端 movingAvg：前 w-1 个为 None，不用未来数据。"""
    out: list[float | None] = [None] * len(arr)
    s = 0.0
    for i, x in enumerate(arr):
        s += x
        if i >= w:
            s -= arr[i - w]
        if i >= w - 1:
            out[i] = s / w
    return out


def bars_for(bars: list[dict], range_key: str, period: str) -> list[dict]:
    """等价前端 drawerBars（含残行过滤与 170 根截尾）。"""
    raw = slice_range(bars, range_key)
    if period == "D":
        return raw
    mult = PERIOD_MULT.get(period)
    if mult is None:
        raise ValueError(f"未知周期 {period}")
    cleaned = [b for b in raw if _valid(b)]
    agg = aggregate(cleaned, mult)
    return agg[-DH_CANDLE_MAX:] if len(agg) > DH_CANDLE_MAX else agg


def ma_bundle(bars: list[dict]) -> dict[str, list[float | None]]:
    closes = [float(b["c"]) for b in bars]
    return {
        "ma5": moving_avg(closes, 5),
        "ma10": moving_avg(closes, 10),
        "ma20": moving_avg(closes, 20),
    }
