"""API 响应模型。

与 QuantFlow Pro 的差异（刻意为之）：
它 148 个路由的响应几乎全是 `{"additionalProperties": true}` 裸 dict，只有请求有
Pydantic 模型 —— 于是前端读字段全靠约定，后端改个名就静默失效。这里请求与响应
**两边都有模型**，OpenAPI 里能直接看到数据契约。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..core.envelope import DataQuality


class Bar(BaseModel):
    t: str = Field(description="交易日期 YYYY-MM-DD（本地口径，非 UTC）")
    o: float
    h: float
    l: float
    c: float
    v: float


class StockMeta(BaseModel):
    """标的元数据。字段名刻意与前端 UNIVERSE 保持一致（如 revG），
    避免前后端各用一套命名导致适配层要做映射。"""

    code: str
    name: str
    en: str | None = None
    market: str
    sector: str
    price: float
    pe: float | None = None
    pb: float | None = None
    mcap: float | None = None
    dy: float | None = None
    revG: float | None = None
    eps: float | None = None
    beta: float | None = None
    vol: float | None = None
    drift: float | None = None
    rating: str | None = None
    conv: int | None = None
    thesis: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class Quote(BaseModel):
    code: str
    name: str
    market: str
    sector: str
    last: float
    prev_close: float
    chg_pct: float
    day_high: float
    day_low: float
    volume: float
    as_of: str


class MaBundle(BaseModel):
    ma5: list[float | None]
    ma10: list[float | None]
    ma20: list[float | None]


class UniverseResponse(BaseModel):
    data: list[StockMeta]
    quality: DataQuality
    provider: str
    generated_at: str


class QuoteResponse(BaseModel):
    data: Quote
    quality: DataQuality
    provider: str
    generated_at: str


class KlineResponse(BaseModel):
    code: str
    period: str = Field(description="D 日 / W 周 / M 月")
    range: str = Field(description="1W/1M/3M/6M/1Y/5Y；1D 暂不支持")
    data: list[Bar]
    ma: MaBundle | None = Field(default=None, description="仅周/月返回；日线由前端画 MA20/MA60")
    quality: DataQuality
    provider: str
    generated_at: str


class BarsResponse(BaseModel):
    """最近 N 根日线。给前端做增量同步用 —— 全量 1300 根 × 31 只约 4MB，
    首屏不该付这个代价，所以只取尾部窗口。"""

    code: str
    total: int = Field(description="该标的可用日线总数")
    data: list[Bar]
    quality: DataQuality
    provider: str
    generated_at: str


class HealthResponse(BaseModel):
    status: str
    version: str
    provider: dict
    universe: dict
    checks: dict
    # 鉴权自描述：让下游（和用户）一眼看出这服务要不要 token。
    # 缺这个字段时，"接口裸奔"只能靠读代码发现。
    auth: dict = Field(default_factory=dict, description="off=无鉴权 / bearer=需要 token")
