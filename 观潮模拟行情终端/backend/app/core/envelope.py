"""统一响应信封与数据质量元数据。

为什么单独抽一层：观潮各面板目前各自判断"数据够不够、缺不缺"，文案散落。
QuantFlow Pro 的做法是把质量元数据塞进业务响应（`data_quality.available_dims /
total_dims / missing_dims`），前端不需要猜。这里沿用该思路并做成强类型。

硬约束（与项目既有原则一致）：
- 缺失一律降级、**不补 0**、不假装算出来；
- 不可用的维度必须出现在 missing 里，前端必须能看见；
- quality 只回答"这屏数据能不能当结论看"，不做行情预测。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DataQuality(BaseModel):
    """数据质量信封。任何返回数值的接口都必须带上。"""

    available: int = Field(description="可用维度/条目数")
    total: int = Field(description="应有维度/条目总数")
    missing: list[str] = Field(default_factory=list, description="缺失项标识，前端可直接展示")
    degraded: bool = Field(default=False, description="是否降级（有缺失但仍有可用部分）")
    note: str = Field(default="", description="人话说明，给用户看")

    @classmethod
    def full(cls, total: int, note: str = "") -> "DataQuality":
        return cls(available=total, total=total, missing=[], degraded=False, note=note)

    @classmethod
    def build(cls, total: int, missing: list[str], note: str = "") -> "DataQuality":
        available = total - len(missing)
        return cls(
            available=available,
            total=total,
            missing=list(missing),
            degraded=bool(missing),
            note=note,
        )

    @classmethod
    def none(cls, total: int, note: str) -> "DataQuality":
        """全部不可用：不返回估算值，只说明为什么没有。"""
        return cls(available=0, total=total, missing=[], degraded=True, note=note)
