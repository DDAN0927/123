"""外部内容库：存放从站外导入的攻略内容（小红书 / 抖音 / 手工录入）。

为什么不做自动抓取
------------------
小红书开放平台与抖音开放平台都要求**企业营业执照 + 企业认证**，且开放的接口
面向订单 / 商品 / 广告 / 授权用户数据，**并不提供通用的旅游内容与笔记检索**；
绕过平台反爬直接抓取则违反其服务协议。所以这里不做抓取。

这里提供的是一条**合规的导入通道**：由管理员把站外看到的攻略正文粘贴进来，
落库后可以被关键词检索，并可通过 `export_to_kb()` 写成知识库文档参与 RAG 检索，
从而真正进入多 Agent 的回答链路。
"""

import contextlib
import re
import time
import uuid
from pathlib import Path

from app import db
from app.config import settings

# 允许的来源标记：小红书 / 抖音 / 手工录入 / 其他
SOURCES = ("xiaohongshu", "douyin", "manual", "other")
SOURCE_LABELS = {
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "manual": "手工录入",
    "other": "其他",
}

_MAX_CONTENT = 20000  # 单条正文上限，避免把库撑爆


def _now() -> float:
    return time.time()


def _clean(v: str | None, limit: int) -> str:
    return (v or "").strip()[:limit]


def add_note(
    source: str,
    title: str,
    content: str,
    city: str = "",
    tags: str = "",
    url: str = "",
    author: str = "",
    imported_by: str = "",
) -> dict:
    """新增一条外部攻略内容。content 为空则抛 ValueError。"""
    content = (content or "").strip()
    if not content:
        raise ValueError("内容不能为空")
    if len(content) > _MAX_CONTENT:
        raise ValueError(f"内容过长（上限 {_MAX_CONTENT} 字）")

    source = (source or "manual").strip().lower()
    if source not in SOURCES:
        source = "other"

    item = {
        "id": uuid.uuid4().hex[:12],
        "source": source,
        "title": _clean(title, 80) or content[:40],
        "content": content,
        "city": _clean(city, 20),
        "tags": _clean(tags, 120),
        "url": _clean(url, 300),
        "author": _clean(author, 40),
        "imported_by": _clean(imported_by, 40),
        "created_at": _now(),
    }
    db.x(
        "INSERT INTO notes(id, source, title, content, city, tags, url, author, imported_by, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            item["id"],
            item["source"],
            item["title"],
            item["content"],
            item["city"],
            item["tags"],
            item["url"],
            item["author"],
            item["imported_by"],
            item["created_at"],
        ),
    )
    return item


def get_note(nid: str) -> dict | None:
    row = db.q1("SELECT * FROM notes WHERE id = ?", (nid,))
    return dict(row) if row is not None else None


def _where(
    city: str | None = None, keyword: str | None = None, source: str | None = None
) -> tuple[str, list]:
    """把「城市 / 来源 / 关键词」三个过滤条件拼成 WHERE 片段。

    抽出来是为了让 `list_notes()` 与 `count_notes()` 共用同一套条件 ——
    否则分页时「本页条数」和「总数」很容易因为条件不一致而对不上。
    """
    sql = ""
    params: list = []
    if city:
        sql += " AND city = ?"
        params.append(city.strip())
    if source:
        sql += " AND source = ?"
        params.append(source.strip().lower())
    if keyword:
        kw = f"%{keyword.strip()}%"
        sql += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
        params += [kw, kw, kw]
    return sql, params


def list_notes(
    limit: int = 100,
    offset: int = 0,
    city: str | None = None,
    keyword: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """列出内容库；支持按城市、来源、关键词（标题/正文/标签）过滤与分页。"""
    limit = max(1, min(int(limit or 100), 500))
    offset = max(0, int(offset or 0))
    cond, params = _where(city, keyword, source)
    # 加 id 作为次级排序：created_at 是浮点秒，批量导入时可能撞在同一时刻，
    # 只按时间排序会让分页结果不稳定（翻页出现重复或漏项）。
    sql = "SELECT * FROM notes WHERE 1=1" + cond + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return [dict(r) for r in db.q(sql, params)]


def count_notes(city: str | None = None, keyword: str | None = None, source: str | None = None) -> int:
    """按与 `list_notes()` 完全相同的过滤条件统计总条数，供前端分页使用。"""
    cond, params = _where(city, keyword, source)
    row = db.q1("SELECT COUNT(*) AS n FROM notes WHERE 1=1" + cond, params)
    return int(row["n"]) if row else 0


def list_cities(limit: int = 100) -> list[dict]:
    """返回内容库覆盖的城市及各自条数，供前端做筛选下拉。"""
    limit = max(1, min(int(limit or 100), 500))
    rows = db.q(
        "SELECT city, COUNT(*) AS n FROM notes WHERE city != '' "
        "GROUP BY city ORDER BY n DESC, city ASC LIMIT ?",
        (limit,),
    )
    return [{"city": r["city"], "count": r["n"]} for r in rows]


def update_note(nid: str, **fields) -> dict | None:
    """局部更新一条内容；只更新传入且非 None 的字段。

    返回更新后的完整记录；内容不存在返回 None。
    """
    row = db.q1("SELECT * FROM notes WHERE id = ?", (nid,))
    if row is None:
        return None

    allowed = {"source", "title", "content", "city", "tags", "url", "author"}
    sets: list[str] = []
    params: list = []
    for key, val in fields.items():
        if key not in allowed or val is None:
            continue
        if key == "content":
            val = (val or "").strip()
            if not val:
                raise ValueError("内容不能为空")
            if len(val) > _MAX_CONTENT:
                raise ValueError(f"内容过长（上限 {_MAX_CONTENT} 字）")
        elif key == "source":
            val = (val or "manual").strip().lower()
            if val not in SOURCES:
                val = "other"
        elif key == "title":
            val = _clean(val, 80)
        elif key == "city":
            val = _clean(val, 20)
        elif key == "tags":
            val = _clean(val, 120)
        elif key == "url":
            val = _clean(val, 300)
        elif key == "author":
            val = _clean(val, 40)
        sets.append(f"{key} = ?")
        params.append(val)

    if not sets:
        return dict(row)

    params.append(nid)
    db.x(f"UPDATE notes SET {', '.join(sets)} WHERE id = ?", params)
    return get_note(nid)


def delete_note(nid: str) -> bool:
    if db.q1("SELECT id FROM notes WHERE id = ?", (nid,)) is None:
        return False
    db.x("DELETE FROM notes WHERE id = ?", (nid,))
    return True


def note_stats() -> dict:
    """内容库概览：总量、按来源分布、覆盖城市数、城市明细。"""
    total = db.q1("SELECT COUNT(*) AS n FROM notes")
    by_source = {r["source"]: r["n"] for r in db.q("SELECT source, COUNT(*) AS n FROM notes GROUP BY source")}
    cities = db.q("SELECT COUNT(DISTINCT city) AS n FROM notes WHERE city != ''")
    return {
        "total": (total["n"] if total else 0),
        "by_source": {SOURCE_LABELS.get(k, k): v for k, v in by_source.items()},
        "city_count": (cities[0]["n"] if cities else 0),
        # 城市明细直接带在概览里：前端一次请求就能同时渲染概览卡片与筛选下拉，
        # 不必再多打一个接口。
        "cities": list_cities(),
    }


def _safe_city(city: str) -> str:
    """城市名做文件名时的净化，避免路径穿越与非法字符。"""
    c = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", (city or "").strip())
    return c.strip("_") or "未分类"


def export_to_kb() -> dict:
    """把内容库写成知识库文档（按城市分文件），供 RAG 检索。

    只写「由本功能生成」的文件（统一前缀），不会动用户自己上传的文档。
    返回 {files: N, notes: M}；调用方随后应触发一次索引重建。
    """
    kb = Path(settings.kb_dir)
    kb.mkdir(parents=True, exist_ok=True)

    # 先清掉上一次导出的文件，避免内容删改后残留
    for old in kb.glob("外部攻略-*.md"):
        # 单个文件删不掉（被占用等）不影响其余文件的清理与后续导出
        with contextlib.suppress(OSError):
            old.unlink()

    rows = db.q("SELECT * FROM notes ORDER BY city, created_at")
    if not rows:
        return {"files": 0, "notes": 0}

    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r["city"] or "", []).append(r)

    for city, items in grouped.items():
        lines = [f"# {city or '未分类'}·外部攻略合集", ""]
        lines.append(f"> 由站外内容导入功能生成，共 {len(items)} 条。")
        lines.append("")
        for it in items:
            label = SOURCE_LABELS.get(it["source"], it["source"])
            lines.append(f"## {it['title']}")
            lines.append(f"- 来源：{label}" + (f"（{it['author']}）" if it["author"] else ""))
            if it["tags"]:
                lines.append(f"- 标签：{it['tags']}")
            if it["url"]:
                lines.append(f"- 原文链接：{it['url']}")
            lines.append("")
            lines.append(it["content"])
            lines.append("")
        (kb / f"外部攻略-{_safe_city(city)}.md").write_text("\n".join(lines), encoding="utf-8")

    return {"files": len(grouped), "notes": len(rows)}
