"""行程工作台接口：行程 CRUD、条目勾选、装备清单生成、行程天气（按用户隔离）

和收藏接口的区别：收藏是「把一段文字存起来」，行程是「把一次旅行排好并跟踪进度」。
所以这里的写操作都按条目粒度做（勾选一个、改一条），而不是整篇覆盖 ——
整篇覆盖会让用户勾了半天的进度在改一个字之后全部归零。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import trips
from app.api.deps import require_user

router = APIRouter(prefix="/api/trips", tags=["trips"])


class TripCreate(BaseModel):
    city: str = Field(..., min_length=1, max_length=40)
    start_date: str = ""
    days: int = 3
    budget: int = 0
    title: str = ""
    note: str = ""


class TripUpdate(BaseModel):
    city: str | None = None
    start_date: str | None = None
    days: int | None = None
    budget: int | None = None
    title: str | None = None
    note: str | None = None


class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    day_index: int = 0
    slot: str = ""
    kind: str = "spot"
    note: str = ""


class ItemUpdate(BaseModel):
    title: str | None = None
    note: str | None = None
    slot: str | None = None
    done: bool | None = None


def _guard(fn, *args, **kwargs):
    """把业务层的参数校验错误统一转成 400，而不是 500。"""
    try:
        return fn(*args, **kwargs)
    except trips.TripError as e:
        raise HTTPException(400, str(e)) from e


@router.get("")
def get_trips(username: str = Depends(require_user)):
    """我的行程列表（带进度与倒计时）"""
    return {"trips": trips.list_trips(username)}


@router.post("")
def create(req: TripCreate, username: str = Depends(require_user)):
    """新建行程：填目的地、出发日期、天数、预算即可"""
    trip = _guard(
        trips.create_trip,
        username,
        req.city,
        start_date=req.start_date,
        days=req.days,
        budget=req.budget,
        title=req.title,
        note=req.note,
    )
    return {"trip": trip}


@router.get("/{tid}")
def get_one(tid: str, username: str = Depends(require_user)):
    """行程详情：行前清单 + 按天分组的行程 + 进度"""
    trip = trips.get_trip(tid, username=username)
    if trip is None:
        raise HTTPException(404, "行程不存在或无权访问")
    return {"trip": trip}


@router.patch("/{tid}")
def patch(tid: str, req: TripUpdate, username: str = Depends(require_user)):
    """修改行程基本信息（部分更新：只改传进来的字段）"""
    ok = _guard(trips.update_trip, tid, username, **req.model_dump(exclude_none=True))
    if not ok:
        raise HTTPException(404, "行程不存在或无权修改")
    return {"trip": trips.get_trip(tid, username=username)}


@router.delete("/{tid}")
def remove(tid: str, username: str = Depends(require_user)):
    if not trips.delete_trip(tid, username):
        raise HTTPException(404, "行程不存在或无权删除")
    return {"ok": True}


@router.post("/{tid}/items")
def add_item(tid: str, req: ItemCreate, username: str = Depends(require_user)):
    """新增一条行程/清单条目。day_index=0 表示行前清单，1..N 表示第几天。"""
    item = _guard(
        trips.add_item,
        tid,
        username,
        req.title,
        day_index=req.day_index,
        slot=req.slot,
        kind=req.kind,
        note=req.note,
    )
    if item is None:
        raise HTTPException(404, "行程不存在或无权修改")
    return {"item": item}


@router.patch("/{tid}/items/{item_id}")
def patch_item(tid: str, item_id: int, req: ItemUpdate, username: str = Depends(require_user)):
    """勾选 / 改标题 / 改备注。勾选是最常用的操作，所以单独走这个轻量接口。"""
    ok = _guard(trips.update_item, tid, username, item_id, **req.model_dump(exclude_none=True))
    if not ok:
        raise HTTPException(404, "条目不存在或无权修改")
    return {"trip": trips.get_trip(tid, username=username)}


@router.delete("/{tid}/items/{item_id}")
def remove_item(tid: str, item_id: int, username: str = Depends(require_user)):
    if not trips.delete_item(tid, username, item_id):
        raise HTTPException(404, "条目不存在或无权删除")
    return {"ok": True}


@router.post("/{tid}/packing")
def build_packing(tid: str, username: str = Depends(require_user)):
    """按目的地与日期生成行前装备清单（有预报用预报，没有则按季节估算）。"""
    data = trips.generate_packing(tid, username)
    if data is None:
        raise HTTPException(404, "行程不存在或无权访问")
    return data


@router.post("/{tid}/plan")
def build_plan(tid: str, username: str = Depends(require_user)):
    """让模型结合攻略库生成按天行程，覆盖已有的行程条目（不动行前清单）。"""
    data = _guard(trips.plan_trip, tid, username)
    if data is None:
        raise HTTPException(404, "行程不存在或无权访问")
    return data


@router.get("/{tid}/weather")
def get_weather(tid: str, username: str = Depends(require_user)):
    """行程期间的天气与出行建议"""
    data = trips.trip_weather(tid, username)
    if data is None:
        raise HTTPException(404, "行程不存在或无权访问")
    return data
