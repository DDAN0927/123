"""AI 能力服务接口（供 SpringBoot 主后端调用）

设计要点
--------
* **只做「生成」，不落库**：行程数据在 SpringBoot 侧，这里写库就会变成两份真相。
* **只允许内部调用**：必须带 `X-Internal-Secret`，密钥不匹配直接 403。
  这不是「多此一举」——本服务如果直接暴露在公网，任何人都能拿它烧 LLM 额度。
* 返回结构与主后端约定好：`{"items": [{day, slot, title, note, kind}]}`。
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app import trips
from app.config import settings

router = APIRouter(prefix="/api/ai", tags=["ai"])


class PlanRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=40)
    days: int = 3
    budget: int = 0


class ReviseRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=40)
    days: int = 3
    instruction: str = Field(..., min_length=1, max_length=200)
    items: list[dict] = Field(default_factory=list)


def _guard(secret: str | None) -> None:
    """内部密钥校验。未配置密钥时一律拒绝（不给默认值开后门）。"""
    if not settings.ai_internal_secret:
        raise HTTPException(403, "AI 内部接口未启用（未配置 AI_INTERNAL_SECRET）")
    if secret != settings.ai_internal_secret:
        raise HTTPException(403, "仅限内部调用")


@router.post("/plan")
def plan(req: PlanRequest, x_internal_secret: str | None = Header(None)):
    """按城市 / 天数 / 预算生成每日安排（结合本地攻略库检索）。"""
    _guard(x_internal_secret)
    try:
        items = trips.plan_items(req.city, req.days, req.budget)
    except trips.TripError as e:
        raise HTTPException(400, str(e)) from e
    return {"items": items}


@router.post("/revise")
def revise(req: ReviseRequest, x_internal_secret: str | None = Header(None)):
    """按自然语言要求改行程，只改相关的那几天。"""
    _guard(x_internal_secret)
    try:
        items = trips.revise_items(req.city, req.days, req.instruction, req.items)
    except trips.TripError as e:
        raise HTTPException(400, str(e)) from e
    return {"items": items}
