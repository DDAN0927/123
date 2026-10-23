"""行程工作台：把「一段攻略文字」变成一次真实旅行的可执行载体。

为什么需要这一层
----------------
只有问答时，用户拿到的是 2000 字 Markdown：看完还得自己抄进备忘录、自己排时间、
自己记着哪些还没订。收藏夹解决的是「存起来」，这里解决的是
「按天排好、能打勾、有倒计时、有进度」。

数据模型只有两张表
------------------
`trips` 是行程本身（城市/日期/天数/预算），`trip_items` 是条目。
条目用 `day_index` 区分两类：**0 = 行前清单**（证件、装备、预订），
**1..N = 第几天**。用一张表而不是两张，是因为「这趟旅行我还差几件事没做」
这个进度必须只有一个口径，分两张表算就会互相矛盾。
"""

import contextlib
import datetime
import json
import re
import time
import uuid

from app import db
from app.llm import get_llm, get_router_llm, usage_of
from app.store import record_llm_usage
from app.tools import packing, weather
from app.tools.rag_tool import get_rag_context_ex

MAX_DAYS = 30
KINDS = {"spot", "food", "stay", "transit", "experience", "packing", "doc"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TripError(ValueError):
    """行程参数不合法。接口层统一转 400，不把内部异常暴露出去。"""


def _ensure():
    db.init()


def _now() -> float:
    return time.time()


def _clean_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if not _DATE_RE.match(value):
        raise TripError("开始日期格式应为 YYYY-MM-DD")
    try:
        datetime.date.fromisoformat(value)
    except ValueError as e:
        raise TripError("开始日期不是有效日期") from e
    return value


def _clean_days(value) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError) as e:
        raise TripError("天数必须是整数") from e
    if not 1 <= days <= MAX_DAYS:
        raise TripError(f"天数应在 1~{MAX_DAYS} 之间")
    return days


def _clean_budget(value) -> int:
    try:
        budget = int(value or 0)
    except (TypeError, ValueError) as e:
        raise TripError("预算必须是整数（元）") from e
    if budget < 0:
        raise TripError("预算不能为负数")
    return min(budget, 10_000_000)


# --------------------------------------------------------------------------- 行程


def create_trip(
    username: str,
    city: str,
    start_date: str = "",
    days: int = 3,
    budget: int = 0,
    title: str = "",
    note: str = "",
) -> dict:
    _ensure()
    city = (city or "").strip()
    if not city:
        raise TripError("目的地不能为空")
    start_date = _clean_date(start_date)
    days = _clean_days(days)
    budget = _clean_budget(budget)

    tid = uuid.uuid4().hex[:12]
    now = _now()
    default_title = f"{city} {days} 天"
    db.x(
        "INSERT INTO trips(id, username, title, city, start_date, days, budget, note, created_at, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            tid,
            username or "",
            (title or default_title).strip()[:60],
            city,
            start_date,
            days,
            budget,
            (note or "")[:500],
            now,
            now,
        ),
    )
    return get_trip(tid, username=username)  # type: ignore[return-value]


def _row_to_trip(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "city": row["city"],
        "start_date": row["start_date"],
        "days": row["days"],
        "budget": row["budget"],
        "note": row["note"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _countdown(start_date: str, days: int) -> tuple[int | None, str]:
    """返回 (距出发天数, 阶段)。阶段用于前端决定显示「倒计时 / 进行中 / 已结束」。"""
    if not start_date:
        return None, "undated"
    try:
        start = datetime.date.fromisoformat(start_date)
    except ValueError:
        return None, "undated"
    today = datetime.date.today()
    delta = (start - today).days
    if delta > 0:
        return delta, "upcoming"
    if delta > -days:
        return delta, "ongoing"
    return delta, "past"


def _progress(items: list[dict]) -> dict:
    total = len(items)
    done = sum(1 for i in items if i["done"])
    return {"done": done, "total": total, "percent": round(done * 100 / total) if total else 0}


def _items_of(tid: str) -> list[dict]:
    rows = db.q(
        "SELECT id, day_index, slot, kind, title, note, done, sort FROM trip_items "
        "WHERE trip_id = ? ORDER BY day_index, sort, id",
        (tid,),
    )
    return [
        {
            "id": r["id"],
            "day_index": r["day_index"],
            "slot": r["slot"],
            "kind": r["kind"],
            "title": r["title"],
            "note": r["note"],
            "done": bool(r["done"]),
        }
        for r in rows
    ]


def get_trip(tid: str, username: str | None = None) -> dict | None:
    """取单个行程（含条目、进度、倒计时）。传 username 时校验归属。"""
    _ensure()
    row = db.q1("SELECT * FROM trips WHERE id = ?", (tid,))
    if row is None:
        return None
    if username is not None and (row["username"] or "") != username:
        return None

    trip = _row_to_trip(row)
    items = _items_of(tid)
    countdown, phase = _countdown(trip["start_date"], trip["days"])

    prep = [i for i in items if i["day_index"] == 0]
    by_day: dict[int, list[dict]] = {}
    for i in items:
        if i["day_index"] >= 1:
            by_day.setdefault(i["day_index"], []).append(i)

    trip.update(
        {
            "countdown": countdown,
            "phase": phase,
            "progress": _progress(items),
            "prep": prep,
            "itinerary": [{"day": d, "items": by_day[d]} for d in sorted(by_day)],
        }
    )
    return trip


def list_trips(username: str) -> list[dict]:
    """当前用户的行程列表（按更新时间倒序），每条带进度与倒计时。"""
    _ensure()
    rows = db.q(
        "SELECT * FROM trips WHERE username = ? ORDER BY updated_at DESC LIMIT 100", (username or "",)
    )
    out = []
    for row in rows:
        trip = _row_to_trip(row)
        items = _items_of(trip["id"])
        countdown, phase = _countdown(trip["start_date"], trip["days"])
        trip.update(
            {
                "countdown": countdown,
                "phase": phase,
                "progress": _progress(items),
                "item_count": len(items),
            }
        )
        out.append(trip)
    return out


def update_trip(tid: str, username: str, **fields) -> bool:
    _ensure()
    row = db.q1("SELECT username FROM trips WHERE id = ?", (tid,))
    if row is None or (row["username"] or "") != (username or ""):
        return False

    allowed = {}
    if "title" in fields and fields["title"] is not None:
        allowed["title"] = str(fields["title"]).strip()[:60] or "未命名行程"
    if "city" in fields and fields["city"] is not None:
        city = str(fields["city"]).strip()
        if not city:
            raise TripError("目的地不能为空")
        allowed["city"] = city
    if "start_date" in fields and fields["start_date"] is not None:
        allowed["start_date"] = _clean_date(str(fields["start_date"]))
    if "days" in fields and fields["days"] is not None:
        allowed["days"] = _clean_days(fields["days"])
    if "budget" in fields and fields["budget"] is not None:
        allowed["budget"] = _clean_budget(fields["budget"])
    if "note" in fields and fields["note"] is not None:
        allowed["note"] = str(fields["note"])[:500]

    if not allowed:
        return True
    allowed["updated_at"] = _now()
    sets = ", ".join(f"{k} = ?" for k in allowed)
    db.x(f"UPDATE trips SET {sets} WHERE id = ?", (*allowed.values(), tid))
    return True


def delete_trip(tid: str, username: str) -> bool:
    _ensure()
    row = db.q1("SELECT username FROM trips WHERE id = ?", (tid,))
    if row is None or (row["username"] or "") != (username or ""):
        return False
    db.x("DELETE FROM trip_items WHERE trip_id = ?", (tid,))
    db.x("DELETE FROM trips WHERE id = ?", (tid,))
    return True


# --------------------------------------------------------------------------- 条目


def _touch(tid: str):
    db.x("UPDATE trips SET updated_at = ? WHERE id = ?", (_now(), tid))


def _owns(tid: str, username: str) -> bool:
    row = db.q1("SELECT username FROM trips WHERE id = ?", (tid,))
    return row is not None and (row["username"] or "") == (username or "")


def add_item(
    tid: str,
    username: str,
    title: str,
    day_index: int = 0,
    slot: str = "",
    kind: str = "spot",
    note: str = "",
) -> dict | None:
    _ensure()
    if not _owns(tid, username):
        return None
    title = (title or "").strip()
    if not title:
        raise TripError("条目内容不能为空")
    try:
        day_index = int(day_index)
    except (TypeError, ValueError) as e:
        raise TripError("day_index 必须是整数") from e
    if day_index < 0 or day_index > MAX_DAYS:
        raise TripError("day_index 超出范围")
    if kind not in KINDS:
        kind = "spot"

    row = db.q1(
        "SELECT COALESCE(MAX(sort), -1) AS m FROM trip_items WHERE trip_id = ? AND day_index = ?",
        (tid, day_index),
    )
    nxt = (row["m"] if row else -1) + 1
    cur = db.x(
        "INSERT INTO trip_items(trip_id, day_index, slot, kind, title, note, done, sort) "
        "VALUES(?,?,?,?,?,?,0,?)",
        (tid, day_index, (slot or "")[:10], kind, title[:120], (note or "")[:500], nxt),
    )
    _touch(tid)
    return {"id": cur.lastrowid, "day_index": day_index, "slot": slot, "kind": kind, "title": title}


def update_item(tid: str, username: str, item_id: int, **fields) -> bool:
    _ensure()
    if not _owns(tid, username):
        return False
    row = db.q1("SELECT id FROM trip_items WHERE id = ? AND trip_id = ?", (item_id, tid))
    if row is None:
        return False

    allowed = {}
    if "done" in fields and fields["done"] is not None:
        allowed["done"] = 1 if fields["done"] else 0
    if "title" in fields and fields["title"] is not None:
        title = str(fields["title"]).strip()
        if not title:
            raise TripError("条目内容不能为空")
        allowed["title"] = title[:120]
    if "note" in fields and fields["note"] is not None:
        allowed["note"] = str(fields["note"])[:500]
    if "slot" in fields and fields["slot"] is not None:
        allowed["slot"] = str(fields["slot"])[:10]
    if not allowed:
        return True
    sets = ", ".join(f"{k} = ?" for k in allowed)
    db.x(f"UPDATE trip_items SET {sets} WHERE id = ? AND trip_id = ?", (*allowed.values(), item_id, tid))
    _touch(tid)
    return True


def delete_item(tid: str, username: str, item_id: int) -> bool:
    _ensure()
    if not _owns(tid, username):
        return False
    cur = db.x("DELETE FROM trip_items WHERE id = ? AND trip_id = ?", (item_id, tid))
    if cur.rowcount == 0:
        return False
    _touch(tid)
    return True


# --------------------------------------------------------------------------- 装备清单


def generate_packing(tid: str, username: str) -> dict | None:
    """按行程的城市/日期/天数生成行前装备清单，覆盖旧的生成条目。

    只替换 `kind = 'packing'` 的行前条目，用户自己加的「给朋友带礼物」之类
    （前端以 `kind='doc'` 写入）不会被清掉 —— 重新生成清单不该把手工内容一起抹了。
    """
    _ensure()
    trip = get_trip(tid, username=username)
    if trip is None:
        return None

    rows = weather.forecast(trip["city"], days=max(trip["days"], 1), start_date=trip["start_date"])
    tmax = max((r["tmax"] for r in rows), default=None) if rows else None
    tmin = min((r["tmin"] for r in rows), default=None) if rows else None
    precip = max(((r["precip"] or 0) for r in rows), default=None) if rows else None

    groups = packing.build(
        trip["city"],
        days=trip["days"],
        start_date=trip["start_date"],
        tmax=tmax,
        tmin=tmin,
        precip=precip,
    )
    entries = packing.items_of(groups)

    db.x("DELETE FROM trip_items WHERE trip_id = ? AND day_index = 0 AND kind = 'packing'", (tid,))
    for i, e in enumerate(entries):
        db.x(
            "INSERT INTO trip_items(trip_id, day_index, slot, kind, title, note, done, sort) "
            "VALUES(?,0,?,?,?,'',0,?)",
            (tid, e["group"], "packing", e["title"][:120], i),
        )
    _touch(tid)
    return {
        "groups": groups,
        "source": "forecast" if rows else "season",
        "weather": rows,
        "advice": weather.advice(rows) if rows else [],
    }


def trip_weather(tid: str, username: str) -> dict | None:
    """行程期间的天气预报 + 出行建议。超出预报范围时返回空列表并说明原因。"""
    _ensure()
    trip = get_trip(tid, username=username)
    if trip is None:
        return None
    rows = weather.forecast(trip["city"], days=max(trip["days"], 1), start_date=trip["start_date"])
    if not rows:
        return {
            "supported": False,
            "reason": "该城市暂无实时预报（仅支持 20 个热门城市），或出发日期超出未来 16 天",
            "rows": [],
            "advice": [],
        }
    return {"supported": True, "rows": rows, "advice": weather.advice(rows)}


# --------------------------------------------------------------------------- AI 生成行程

_PLAN_PROMPT = """你是行程规划师。请为「{city}」规划 {days} 天行程。

## 硬性要求
1. 只输出**一个 JSON 数组**，不要任何解释、不要 Markdown 代码块、不要前后缀文字。
2. 数组每一项的字段固定为：
   {{"day": 1, "slot": "上午", "title": "景点或活动名", "note": "一句实用提示", "kind": "spot"}}
3. `day` 从 1 到 {days}；`slot` 只能是 上午 / 下午 / 晚上；`kind` 只能是
   spot（景点）、food（餐饮）、stay（住宿）、transit（交通）、experience（体验项目）。
4. 每天 3~4 项，同一天的景点按地理就近排列，不要来回折返。
5. 优先使用下面资料里的景点、餐厅与价格；资料没覆盖的内容可以补充，但**不要编造具体门票价格**，
   不确定就写「以官方渠道为准」。
6. `note` 要写能直接执行的信息（预约提前几天、大致耗时、交通方式、避坑点），不要写空话。

## 参考资料
<<<资料开始>>>
{context}
<<<资料结束>>>
"""


def _parse_plan(text: str) -> list[dict]:
    """从模型输出里抠出 JSON 数组。

    模型即使被要求「只输出 JSON」，也常会包一层 ```json 或加一句「好的，以下是行程」。
    这里先直接解析，失败再用正则找第一个 `[` 到最后一个 `]`，仍失败就抛可读错误。
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.S)
        if not m:
            raise TripError("行程生成失败：模型没有返回可解析的行程结构，请重试") from None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise TripError("行程生成失败：返回内容不是合法 JSON，请重试") from e

    if not isinstance(data, list):
        raise TripError("行程生成失败：返回结构不是数组，请重试")

    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        try:
            day = int(item.get("day") or 1)
        except (TypeError, ValueError):
            day = 1
        kind = str(item.get("kind") or "spot")
        out.append(
            {
                "day": max(1, min(day, MAX_DAYS)),
                "slot": str(item.get("slot") or "").strip()[:10],
                "title": title[:120],
                "note": str(item.get("note") or "").strip()[:500],
                "kind": kind if kind in KINDS else "spot",
            }
        )
    if not out:
        raise TripError("行程生成失败：返回的行程条目为空，请重试")
    return out


def plan_trip(tid: str, username: str) -> dict | None:
    """调用模型 + 知识库为行程生成按天安排，写入 `day_index >= 1` 的条目。

    只替换**行程条目**，不碰行前清单（那是用户勾选到一半的东西）。
    模型不可用时抛 `TripError`，前端提示「请稍后重试或手动添加」。
    """
    _ensure()
    trip = get_trip(tid, username=username)
    if trip is None:
        return None

    llm = get_router_llm() or get_llm()
    if llm is None:
        raise TripError("当前未配置大模型，无法自动生成行程；可手动添加条目")

    context, _ = get_rag_context_ex(f"{trip['city']} 行程 景点 美食 住宿")
    prompt = _PLAN_PROMPT.format(city=trip["city"], days=trip["days"], context=context[:6000])
    resp = llm.invoke(prompt)
    content = getattr(resp, "content", "") or ""
    with contextlib.suppress(Exception):  # 统计失败不能影响主流程
        record_llm_usage(
            getattr(llm, "model", None) or getattr(llm, "model_name", None) or "unknown",
            *usage_of(resp),
            agent="planner",
        )

    plan = _parse_plan(content)
    db.x("DELETE FROM trip_items WHERE trip_id = ? AND day_index >= 1", (tid,))
    for i, it in enumerate(plan):
        db.x(
            "INSERT INTO trip_items(trip_id, day_index, slot, kind, title, note, done, sort) "
            "VALUES(?,?,?,?,?,?,0,?)",
            (tid, it["day"], it["slot"], it["kind"], it["title"], it["note"], i),
        )
    _touch(tid)
    return {"items": len(plan), "trip": get_trip(tid, username=username)}
