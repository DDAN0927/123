"""行情域接口：标的清单、实时快照、K 线。

质量信封的用法（这是本次全栈化要立的核心规矩）：
- 能算就给值，同时报「应有/实有」；
- 算不出就降级并在 missing/note 里说清楚，**不补 0、不给假值**；
- 1D 分时前端是本地合成（genIntraday），后端不伪造分时数据，直接明确拒绝。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from ..core.envelope import DataQuality
from ..core.store import get_store
from ..schemas.market import (
    Bar,
    BarsResponse,
    KlineResponse,
    MaBundle,
    Quote,
    QuoteResponse,
    StockMeta,
    UniverseResponse,
)
from ..services.kline import (
    PERIOD_MULT,
    RANGE_MAP,
    SUPPORTED_PERIODS,
    SUPPORTED_RANGES,
    UnsupportedRange,
    bars_for,
    ma_bundle,
    slice_range,
)

router = APIRouter(prefix="/api/market", tags=["行情"])


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@router.get("/universe", response_model=UniverseResponse, summary="标的清单")
def universe() -> UniverseResponse:
    store = get_store()
    rows = [StockMeta.model_validate(r) for r in store.rows]
    missing = [r.code for r in rows if r.vol is None or r.drift is None or r.mcap is None]
    quality = (
        DataQuality.build(len(rows), missing, "部分标的缺少波动/漂移参数，序列质量会下降")
        if missing
        else DataQuality.full(len(rows), "精选标的清单，序列由本地确定性算法生成")
    )
    return UniverseResponse(
        data=rows,
        quality=quality,
        provider=store.provider.name,
        generated_at=_now(),
    )


@router.get("/quote/{code}", response_model=QuoteResponse, summary="单个标的快照")
def quote(code: str) -> QuoteResponse:
    store = get_store()
    row = store.get(code)
    series = store.series(code)
    if row is None or not series:
        raise HTTPException(status_code=404, detail=f"标的不存在: {code}")
    if len(series) < 2:
        raise HTTPException(status_code=503, detail=f"{code} 序列不足 2 根，无法计算涨跌幅")

    last, prev = series[-1], series[-2]
    prev_close = float(prev["c"])
    last_close = float(last["c"])
    chg = (last_close - prev_close) / prev_close * 100 if prev_close else 0.0

    return QuoteResponse(
        data=Quote(
            code=str(row["code"]),
            name=str(row["name"]),
            market=str(row["market"]),
            sector=str(row["sector"]),
            last=last_close,
            prev_close=prev_close,
            chg_pct=chg,
            day_high=float(last["h"]),
            day_low=float(last["l"]),
            volume=float(last.get("v") or 0),
            as_of=str(last["t"]),
        ),
        quality=DataQuality.full(1, "单标的最新日线推导，非逐笔实时"),
        provider=store.provider.name,
        generated_at=_now(),
    )


@router.get("/kline", response_model=KlineResponse, summary="K 线（支持周/月聚合）")
def kline(
    code: str,
    range_key: str = Query("3M", alias="range", description="1W/1M/3M/6M/1Y/5Y"),
    period: str = Query("D", description="D 日 / W 周 / M 月"),
) -> KlineResponse:
    period = period.upper()
    if period not in SUPPORTED_PERIODS:
        raise HTTPException(status_code=422, detail=f"不支持的周期: {period}（可用 D/W/M）")
    if range_key != "1D" and range_key not in SUPPORTED_RANGES:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的区间: {range_key}（可用 {'/'.join(sorted(SUPPORTED_RANGES))}）",
        )

    store = get_store()
    series = store.series(code)
    if series is None:
        raise HTTPException(status_code=404, detail=f"标的不存在: {code}")

    if range_key == "1D":
        # 不伪造分时。前端本地合成分时是它的既有能力，后端硬造一份会变成两个真相。
        raise HTTPException(
            status_code=422,
            detail="1D 分时由前端本地合成（genIntraday），本接口不提供，避免出现两套分时口径",
        )

    try:
        raw = slice_range(series, range_key)
    except UnsupportedRange:
        raise HTTPException(status_code=422, detail="1D 不支持")

    bars = bars_for(series, range_key, period)
    if period == "D":
        expected = RANGE_MAP[range_key]
        got = len(bars)
    else:
        mult = PERIOD_MULT[period]
        valid = [b for b in raw if all(b.get(k) for k in ("o", "h", "l", "c"))]
        expected = math.ceil(len(valid) / mult)
        got = len(bars)

    missing: list[str] = []
    note = ""
    if got == 0:
        quality = DataQuality.none(1, f"{code} 在 {range_key} 区间无有效 K 线")
    else:
        if got < expected:
            missing.append("bars")
            note = f"该周期应有 {expected} 根，实有 {got} 根" + (
                f"（已按上限截尾至 {got} 根）" if got > 0 and expected > got else ""
            )
        quality = (
            DataQuality.build(1, missing, note)
            if missing
            else DataQuality.full(1, f"{code} {range_key} {period} 共 {got} 根")
        )

    return KlineResponse(
        code=str(code),
        period=period,
        range=range_key,
        data=[Bar(**b) for b in bars],
        ma=MaBundle(**ma_bundle(bars)) if period in ("W", "M") and bars else None,
        quality=quality,
        provider=store.provider.name,
        generated_at=_now(),
    )


@router.get("/bars", response_model=BarsResponse, summary="最近 N 根日线（前端增量同步用）")
def bars(
    code: str,
    limit: int = Query(300, ge=1, le=1300, description="尾部窗口长度"),
) -> BarsResponse:
    store = get_store()
    series = store.series(code)
    if series is None:
        raise HTTPException(status_code=404, detail=f"标的不存在: {code}")

    window = series[-limit:] if limit < len(series) else list(series)
    quality = (
        DataQuality.full(1, f"{code} 尾部 {len(window)} 根（共 {len(series)} 根）")
        if window
        else DataQuality.none(1, f"{code} 无可用日线")
    )
    return BarsResponse(
        code=str(code),
        total=len(series),
        data=[Bar(**b) for b in window],
        quality=quality,
        provider=store.provider.name,
        generated_at=_now(),
    )
