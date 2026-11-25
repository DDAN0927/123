"""确定性行情数据 provider（mock）。

设计约束（重要，改动前先读）：

1. **必须逐位复刻前端 `index.html` 的 `genSeries()` 算法。**
   前端有离线回退路径（后端不可用时退回本地 genSeries），如果两边算法不同，
   同一标的在"有后端/无后端"两种状态下会给出不同序列 —— 用户会看到 K 线跳变，
   且 selftest 的确定性断言会变成两套口径。

2. 因此本文件里的 `mulberry32` / `gauss` / `hash_str` 都是从 JS 逐行翻译的，
   包括 while 循环的**消耗顺序**（gauss 里先去零 u 再取 v，顺序错了序列就全变）。

3. 浮点：Python float 与 JS number 同为 IEEE-754 double，`math.exp/sin/cos/log/sqrt`
   与 JS `Math.*` 可能存在 1 ulp 级差异。因此对外宣称只能说"同种子同量级、统计一致"，
   **不要说"逐字节相同"** —— 需要用 test_parity 脚本实测偏差后再描述。

4. 这里不做真实现实行情。接真实数据应新增 provider（见 base.py 协议），
   而不是改本文件的算法。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

# --- 与前端 index.html 保持一致的常量 ---------------------------------------
SERIES_DAYS = 1300
# 前端: const TODAY = new Date(2026, 10, 17);  JS 月份 0 基 → 11 月
TODAY = date(2026, 11, 17)


def _imul(a: int, b: int) -> int:
    """等价 JS `Math.imul`：32 位有符号乘法，只保留低 32 位。"""
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def hash_str(s: str) -> int:
    """等价 JS `hashStr`：FNV-1a 32bit。

    注意 JS 用 `charCodeAt` 取 UTF-16 码元。BMP 内字符（含常用汉字）与 Python
    `ord()` 一致；代理对（emoji 等）会有差异，故仅在 ASCII 代码与 BMP 名上使用。
    """
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = _imul(h, 16777619)
    return h & 0xFFFFFFFF


class Mulberry32:
    """等价 JS 闭包版 `mulberry32(seed)`。"""

    __slots__ = ("a",)

    def __init__(self, seed: int) -> None:
        self.a = seed & 0xFFFFFFFF

    def next(self) -> float:
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        a = self.a
        t = _imul(a ^ (a >> 15), 1 | a)
        t = (t ^ (t + _imul(t ^ (t >> 7), 61 | t))) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296


def gauss(rng: Mulberry32) -> float:
    """等价 JS `gauss`：Box-Muller。

    消耗顺序是算法的一部分：先把 u 取到非零，再取 v。
    """
    u = 0.0
    while not u:
        u = rng.next()
    v = 0.0
    while not v:
        v = rng.next()
    return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)


@dataclass(frozen=True)
class SymParams:
    """genSeries 所需的最小参数集（其余字段不参与序列生成）。"""

    code: str
    price: float
    vol: float
    drift: float
    mcap: float

    @classmethod
    def from_universe(cls, row: dict) -> "SymParams":
        return cls(
            code=str(row["code"]),
            price=float(row["price"]),
            vol=float(row.get("vol") or 0.3),
            drift=float(row.get("drift") or 0.1),
            mcap=float(row.get("mcap") or 0),
        )


def gen_series(sym: SymParams) -> list[dict]:
    """生成 SERIES_DAYS 根日线，返回 [{t,o,h,l,c,v}]，与前端结构一致。"""
    rng = Mulberry32(hash_str(sym.code))
    n = SERIES_DAYS
    daily_vol = sym.vol / math.sqrt(252)
    seed_phase = hash_str(sym.code) % 7

    closes = [0.0] * n
    p = sym.price / math.exp(sym.drift * (n / 252))
    for i in range(n):
        shock = gauss(rng) * daily_vol
        cycle = math.sin(i / 210 + seed_phase) * 0.0016
        p = max(p * math.exp(sym.drift / 252 + shock + cycle), 0.01)
        closes[i] = p

    k = sym.price / closes[n - 1]
    for i in range(n):
        closes[i] *= k

    out: list[dict] = []
    for i in range(n):
        c = closes[i]
        o = c * (1 - daily_vol * 0.3) if i == 0 else closes[i - 1] * (1 + gauss(rng) * 0.002)
        hi = max(o, c) * (1 + abs(gauss(rng)) * daily_vol * 0.55)
        lo = min(o, c) * (1 - abs(gauss(rng)) * daily_vol * 0.55)
        base_v = max(1.0, sym.mcap * 2.2e6 / max(c, 1.0)) if sym.mcap > 0 else 45000.0
        v = base_v * (0.55 + rng.next() * 0.9) * (1 + abs(c / o - 1) * 22)
        d = TODAY - timedelta(days=(n - 1 - i))
        out.append({"t": d.isoformat(), "o": o, "h": hi, "l": lo, "c": c, "v": v})
    return out


class MarketDataProvider(Protocol):
    """provider 协议。接真实行情（akshare/tushare/券商）时实现本协议即可，
    上层 routers/services 不需改动 —— 这是本次全栈化的主要收益点。
    """

    name: str

    def series(self, sym: SymParams) -> list[dict]: ...

    def health(self) -> dict: ...


class MockProvider:
    """本地确定性生成。标签里必须说自己"模拟"，不能冒充真实行情。"""

    name = "mock"
    label = "本地确定性模拟序列"

    def __init__(self) -> None:
        self._cache: dict[str, list[dict]] = {}

    def series(self, sym: SymParams) -> list[dict]:
        # 1300 根 × 1 万标的若全量预生成会吃掉大量内存，故按 code 缓存懒生成。
        hit = self._cache.get(sym.code)
        if hit is not None:
            return hit
        data = gen_series(sym)
        self._cache[sym.code] = data
        return data

    def health(self) -> dict:
        return {
            "provider": self.name,
            "label": self.label,
            "deterministic": True,
            "cached_symbols": len(self._cache),
            "note": "本地模拟序列，非真实行情",
        }
