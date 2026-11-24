"""进程内的标的注册表与 provider 单例。

数据来源切换点：
- 现在：`backend/data/universe.json`（从 index.html 的 UNIVERSE 抽取）+ MockProvider
- 将来：接真实行情时替换 provider（见 providers/mock.py 的 MarketDataProvider 协议），
  routers 与 services 无需改动。

注意标的规模：精选 31 条 + 前端程序生成的约 1 万条（GEN_STOCKS）。
本后端只持有精选集的元数据，序列按需生成并缓存，避免全量预生成吃内存。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..providers.mock import MarketDataProvider, MockProvider, SymParams

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
UNIVERSE_FILE = DATA_DIR / "universe.json"


class Store:
    def __init__(self) -> None:
        self.provider: MarketDataProvider = MockProvider()
        self._rows: list[dict] = []
        self._by_code: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        if not UNIVERSE_FILE.exists():
            raise RuntimeError(
                f"缺少标的资产 {UNIVERSE_FILE}，请先执行 "
                "`node backend/scripts/extract_universe.js`"
            )
        rows = json.loads(UNIVERSE_FILE.read_text("utf-8"))
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("universe.json 不是非空数组")
        self._rows = rows
        self._by_code = {str(r["code"]): r for r in rows}

    @property
    def rows(self) -> list[dict]:
        return self._rows

    def get(self, code: str) -> dict | None:
        return self._by_code.get(str(code).strip())

    def params(self, code: str) -> SymParams | None:
        row = self.get(code)
        return SymParams.from_universe(row) if row else None

    def series(self, code: str) -> list[dict] | None:
        sym = self.params(code)
        if sym is None:
            return None
        return self.provider.series(sym)


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store
