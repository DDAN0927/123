"""健康检查与自描述。

参考 QuantFlow Pro 的 /api/health：它不仅返回 ok，还逐个报数据源可用性与
provider 配置（akshare/ai_keys 等）。观潮这里精简为三块：provider、universe、checks。
"""

from __future__ import annotations

from fastapi import APIRouter

from ..core.store import get_store
from ..schemas.market import HealthResponse
from ..version import APP_VERSION

router = APIRouter(tags=["健康检查"])


@router.get("/api/health", response_model=HealthResponse, summary="健康检查")
def health() -> HealthResponse:
    store = get_store()
    prov = store.provider.health()
    markets: dict[str, int] = {}
    for row in store.rows:
        m = str(row.get("market") or "?")
        markets[m] = markets.get(m, 0) + 1

    checks = {
        "universe_loaded": len(store.rows) > 0,
        "deterministic_provider": bool(prov.get("deterministic")),
        # 明确声明：这是模拟序列，不是真实行情。避免下游误用为投资依据。
        "data_is_simulated": True,
        "provider_ready": prov.get("provider") == "mock",
    }

    return HealthResponse(
        status="ok" if all(checks.values()) else "degraded",
        version=APP_VERSION,
        provider=prov,
        universe={"total": len(store.rows), "by_market": markets},
        checks=checks,
    )
