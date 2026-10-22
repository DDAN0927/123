"""会话 / 收藏 / 用户 / 运营统计存储（SQLite 实现）。

历史沿革
--------
早期版本是「内存缓存 + JSON/JSONL 追加持久化」，在单机演示场景够用，但有三个问题：
每次删除收藏都要全量重写整个文件、进程崩溃会丢掉防抖中的计数、数据量大时启动要全量回放。

现在统一落到 `app/db.py` 提供的 SQLite 上：**公开函数签名与返回结构保持完全一致**，
所以 `app/api/*` 与前端都不需要改动。首次启动会把历史的 JSON / JSONL 数据自动导入。
"""

import atexit
import hashlib
import re
import threading
import time
import uuid

from app import db
from app.config import settings

_lock = threading.RLock()
_ready = False

# 会话标题 / 预览取自用户与模型的原始消息，里面常带 Markdown 标记。
# 直接截断会在列表里露出 `### 第1天…`、`**加粗**`、`| 表格 |` 这类噪声，
# 所以在「读」的时候统一压成纯文本（不动库里的原始内容，无需迁移）。
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_MD_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]{4,}\|?\s*$", re.MULTILINE)
_MD_INLINE = re.compile(r"(\*\*|__|`{1,3}|~~)")


def _plain(text: str, limit: int) -> str:
    """把 Markdown 摘要压成单行纯文本。"""
    if not text:
        return ""
    s = _MD_LINK.sub(r"\1", text)
    s = _MD_HEADING.sub("", s)
    s = _MD_TABLE_SEP.sub("", s)
    s = _MD_INLINE.sub("", s).replace("|", " ")
    return re.sub(r"\s+", " ", s).strip()[:limit]


def _ensure():
    """惰性初始化：建表 + 一次性迁移旧数据（幂等）。"""
    global _ready
    if _ready:
        return
    with _lock:
        if _ready:
            return
        db.init()
        _ready = True


def _now() -> float:
    return time.time()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


# ================= 会话 =================


def _session_dict(row) -> dict:
    sid = row["id"]
    msgs = db.q("SELECT role, content, ts FROM messages WHERE session_id = ? ORDER BY id", (sid,))
    return {
        "id": sid,
        "messages": [{"role": m["role"], "content": m["content"], "ts": m["ts"]} for m in msgs],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "username": row["username"],
    }


def get_or_create_session(session_id: str | None = None) -> dict:
    _ensure()
    if session_id:
        row = db.q1("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if row is not None:
            return _session_dict(row)
    sid = session_id or uuid.uuid4().hex[:12]
    ts = _now()
    with _lock:
        db.x(
            "INSERT OR IGNORE INTO sessions(id, username, created_at, updated_at) VALUES(?,?,?,?)",
            (sid, "", ts, ts),
        )
        _bump("total_sessions", 1)
    return {"id": sid, "messages": [], "created_at": ts, "updated_at": ts, "username": ""}


def append_message(session_id: str, role: str, content: str):
    _ensure()
    row = db.q1("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if row is None:
        return
    ts = _now()
    with _lock:
        db.x(
            "INSERT INTO messages(session_id, role, content, ts) VALUES(?,?,?,?)",
            (session_id, role, content, ts),
        )
        db.x("UPDATE sessions SET updated_at = ? WHERE id = ?", (ts, session_id))
        _bump("total_messages", 1)


def get_session(session_id: str) -> dict | None:
    _ensure()
    row = db.q1("SELECT * FROM sessions WHERE id = ?", (session_id,))
    return _session_dict(row) if row is not None else None


def record_feedback(session_id: str, message_index: int, rating: str) -> bool:
    """记录用户对某条助手消息的点赞/点踩"""
    _ensure()
    row = db.q1("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if row is None:
        return False
    with _lock:
        db.x(
            "INSERT INTO feedback(session_id, message_index, rating, ts) VALUES(?,?,?,?)",
            (session_id, message_index, rating, _now()),
        )
        _bump("likes" if rating == "like" else "dislikes", 1)
    return True


def set_session_user(session_id: str, username: str):
    """将会话关联到登录用户（用于运营侧统计各用户使用情况）"""
    _ensure()
    if not username:
        return
    row = db.q1("SELECT username FROM sessions WHERE id = ?", (session_id,))
    if row is None or row["username"] == username:
        return
    db.x("UPDATE sessions SET username = ? WHERE id = ?", (username, session_id))


def list_sessions(limit: int = 50) -> list[dict]:
    _ensure()
    rows = db.q(
        """
        SELECT s.id, s.created_at, s.updated_at, s.username,
               (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count,
               (SELECT m.content FROM messages m WHERE m.session_id = s.id
                ORDER BY m.id DESC LIMIT 1) AS preview
        FROM sessions s
        ORDER BY s.updated_at DESC
        LIMIT ?
    """,
        (limit,),
    )
    return [
        {
            "id": r["id"],
            "message_count": r["message_count"] or 0,
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "username": r["username"] or "",
            "preview": _plain(r["preview"], 60),
        }
        for r in rows
    ]


def list_user_sessions(username: str, limit: int = 50) -> list[dict]:
    """某个登录用户自己的会话列表（按最近活跃倒序）"""
    _ensure()
    rows = db.q(
        """
        SELECT s.id, s.created_at, s.updated_at,
               (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count,
               (SELECT m.content FROM messages m WHERE m.session_id = s.id AND m.role = 'user'
                ORDER BY m.id ASC LIMIT 1) AS first_user
        FROM sessions s
        WHERE s.username = ?
        ORDER BY s.updated_at DESC
        LIMIT ?
    """,
        (username, limit),
    )
    return [
        {
            "id": r["id"],
            "title": _plain(r["first_user"], 40) or "新对话",
            "message_count": r["message_count"] or 0,
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def list_users_usage() -> list[dict]:
    """注册用户使用情况：会话数 / 消息数 / 最近活跃（基于会话归属统计）"""
    _ensure()
    rows = db.q("""
        SELECT s.username AS username,
               COUNT(*) AS session_count,
               COALESCE(SUM((SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id)), 0) AS message_count,
               MAX(s.updated_at) AS last_active
        FROM sessions s
        WHERE s.username != ''
        GROUP BY s.username
    """)
    usage = {r["username"]: r for r in rows}

    result = []
    for u in db.q("SELECT username, role, created_at FROM users"):
        it = usage.get(u["username"])
        result.append(
            {
                "username": u["username"],
                "role": u["role"],
                "created_at": u["created_at"],
                "session_count": it["session_count"] if it else 0,
                "message_count": it["message_count"] if it else 0,
                "last_active": it["last_active"] if it else 0,
            }
        )
    result.sort(key=lambda x: x["last_active"] or x["created_at"], reverse=True)
    return result


# ================= 收藏 =================


def add_favorite(title: str, content: str, session_id: str = "", username: str = "") -> dict:
    """新增收藏；username 为归属用户，收藏按用户隔离"""
    _ensure()
    item = {
        "id": uuid.uuid4().hex[:10],
        "title": (title or content[:40]).strip()[:60],
        "content": content,
        "session_id": session_id,
        "username": username or "",
        "created_at": _now(),
    }
    db.x(
        "INSERT INTO favorites(id, title, content, session_id, username, created_at) VALUES(?,?,?,?,?,?)",
        (
            item["id"],
            item["title"],
            item["content"],
            item["session_id"],
            item["username"],
            item["created_at"],
        ),
    )
    return item


def list_favorites(limit: int = 100, username: str | None = None) -> list[dict]:
    """列出收藏；传入 username 时只返回该用户自己的收藏"""
    _ensure()
    if username is None:
        rows = db.q("SELECT * FROM favorites ORDER BY created_at DESC LIMIT ?", (limit,))
    else:
        rows = db.q(
            "SELECT * FROM favorites WHERE username = ? ORDER BY created_at DESC LIMIT ?", (username, limit)
        )
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "content": r["content"],
            "session_id": r["session_id"],
            "username": r["username"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def delete_favorite(fid: str, username: str | None = None) -> bool:
    """删除收藏；传入 username 时校验归属，只能删除自己的收藏"""
    _ensure()
    row = db.q1("SELECT username FROM favorites WHERE id = ?", (fid,))
    if row is None:
        return False
    if username is not None and (row["username"] or "") != username:
        return False
    db.x("DELETE FROM favorites WHERE id = ?", (fid,))
    return True


# ================= 统计 =================

_COUNTER_KEYS = ("total_sessions", "total_messages", "likes", "dislikes")


def _bump(key: str, delta: int):
    db.x(
        "INSERT INTO counters(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = counters.value + excluded.value",
        (key, delta),
    )


def record_agent_call(agent: str):
    _ensure()
    db.x(
        "INSERT INTO agent_calls(agent, count) VALUES(?, 1) "
        "ON CONFLICT(agent) DO UPDATE SET count = agent_calls.count + 1",
        (agent,),
    )


def record_llm_usage(
    model: str, prompt_tokens: int, completion_tokens: int, reasoning_tokens: int = 0, agent: str = ""
):
    """记录一次 LLM 调用的 token 用量。

    **绝不抛异常**：可观测性不该成为主链路的单点故障。
    没有拿到 usage（部分 OpenAI 兼容实现不返回）时静默跳过。
    """
    if not prompt_tokens and not completion_tokens:
        return
    try:
        _ensure()
        db.x(
            "INSERT INTO llm_usage(model, agent, prompt_tokens, completion_tokens, reasoning_tokens, ts) "
            "VALUES(?,?,?,?,?,?)",
            (
                model or "",
                agent or "",
                int(prompt_tokens),
                int(completion_tokens),
                int(reasoning_tokens),
                time.time(),
            ),
        )
    except Exception:
        pass


def _price_of(model: str) -> tuple[float, float]:
    """按模型返回 (输入单价, 输出单价)，单位元/百万 tokens。

    * 含 reasoner → 推理模型档（贵）
    * 含 chat / 其他 → 快速模型档（便宜）
    * 名字拿不到（unknown）→ 按推理模型档，宁可高估不可低估
    """
    name = (model or "").lower()
    if name and "reasoner" not in name and ("chat" in name or "router" in name):
        return settings.llm_price_chat_input_per_mtok, settings.llm_price_chat_output_per_mtok
    return settings.llm_price_input_per_mtok, settings.llm_price_output_per_mtok


def get_stats() -> dict:
    _ensure()
    counters = {r["key"]: r["value"] for r in db.q("SELECT key, value FROM counters")}
    agents = {r["agent"]: r["count"] for r in db.q("SELECT agent, count FROM agent_calls")}

    total = db.q1(
        "SELECT COUNT(*) AS calls, "
        "COALESCE(SUM(prompt_tokens),0) AS p, "
        "COALESCE(SUM(completion_tokens),0) AS c, "
        "COALESCE(SUM(reasoning_tokens),0) AS r FROM llm_usage"
    ) or {"calls": 0, "p": 0, "c": 0, "r": 0}
    p, c = int(total["p"]), int(total["c"])
    by_agent = {
        (row["agent"] or "unknown"): {
            "calls": row["calls"],
            "prompt_tokens": int(row["p"]),
            "completion_tokens": int(row["c"]),
        }
        for row in db.q(
            "SELECT agent, COUNT(*) AS calls, SUM(prompt_tokens) AS p, SUM(completion_tokens) AS c "
            "FROM llm_usage GROUP BY agent ORDER BY (SUM(prompt_tokens)+SUM(completion_tokens)) DESC"
        )
    }

    # 成本必须按模型分组累加：双模型单价差 2~4 倍，
    # 用总量乘单一单价会同时高估路由、低估专家，最后得到一个「看着精确其实错」的数。
    estimated_cost = 0.0
    by_model: dict[str, dict] = {}
    for row in db.q(
        "SELECT model, COUNT(*) AS calls, "
        "COALESCE(SUM(prompt_tokens),0) AS p, "
        "COALESCE(SUM(completion_tokens),0) AS c "
        "FROM llm_usage GROUP BY model"
    ):
        mp, mc = int(row["p"]), int(row["c"])
        in_price, out_price = _price_of(row["model"])
        cost = mp / 1_000_000 * in_price + mc / 1_000_000 * out_price
        estimated_cost += cost
        by_model[row["model"] or "unknown"] = {
            "calls": int(row["calls"]),
            "prompt_tokens": mp,
            "completion_tokens": mc,
            "estimated_cost_cny": round(cost, 4),
        }

    return {
        "total_sessions": counters.get("total_sessions", 0),
        "total_messages": counters.get("total_messages", 0),
        "agent_calls": agents,
        "likes": counters.get("likes", 0),
        "dislikes": counters.get("dislikes", 0),
        "llm_usage": {
            "calls": int(total["calls"]),
            "prompt_tokens": p,
            "completion_tokens": c,
            "reasoning_tokens": int(total["r"]),
            "total_tokens": p + c,
            "estimated_cost_cny": round(estimated_cost, 4),
            "by_agent": by_agent,
            "by_model": by_model,
        },
    }


def flush_stats():
    """保留接口：SQLite 下计数是即时落库的，不再需要防抖刷盘。"""
    return None


# ================= 用户 =================


def _user_dict(username: str) -> dict | None:
    row = db.q1("SELECT * FROM users WHERE username = ?", (username,))
    if row is None:
        return None
    return {
        "username": row["username"],
        "salt": row["salt"],
        "password_hash": row["password_hash"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def create_user(username: str, password: str, role: str = "user") -> tuple[dict | None, str]:
    _ensure()
    username = (username or "").strip()
    if not username or not password:
        return None, "用户名和密码不能为空"
    with _lock:
        if db.q1("SELECT username FROM users WHERE username = ?", (username,)) is not None:
            return None, "用户名已存在"
        salt = uuid.uuid4().hex
        db.x(
            "INSERT INTO users(username, salt, password_hash, role, created_at) VALUES(?,?,?,?,?)",
            (username, salt, _hash_password(password, salt), role, _now()),
        )
    return _user_dict(username), ""


def authenticate(username: str, password: str) -> dict | None:
    _ensure()
    user = _user_dict((username or "").strip())
    if not user:
        return None
    if user["password_hash"] != _hash_password(password, user["salt"]):
        return None
    return user


def get_user(username: str) -> dict | None:
    _ensure()
    return _user_dict((username or "").strip())


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    _ensure()
    user = _user_dict((username or "").strip())
    if not user:
        return False, "用户不存在"
    if user["password_hash"] != _hash_password(old_password, user["salt"]):
        return False, "旧密码错误"
    if not new_password:
        return False, "新密码不能为空"
    salt = uuid.uuid4().hex
    db.x(
        "UPDATE users SET salt = ?, password_hash = ? WHERE username = ?",
        (salt, _hash_password(new_password, salt), user["username"]),
    )
    return True, ""


def set_user_password(username: str, new_password: str, role: str = "admin") -> bool:
    """直接设置某个账号的密码（运维脚本用）。

    返回 True 表示账号原本就存在（密码已重置），False 表示新建了账号。
    """
    _ensure()
    username = (username or "").strip()
    if not username or not new_password:
        raise ValueError("用户名和新密码不能为空")
    existed = db.q1("SELECT username FROM users WHERE username = ?", (username,)) is not None
    salt = uuid.uuid4().hex
    if existed:
        db.x(
            "UPDATE users SET salt = ?, password_hash = ? WHERE username = ?",
            (salt, _hash_password(new_password, salt), username),
        )
    else:
        db.x(
            "INSERT INTO users(username, salt, password_hash, role, created_at) VALUES(?,?,?,?,?)",
            (username, salt, _hash_password(new_password, salt), role, _now()),
        )
    return existed


def ensure_default_admin():
    """启动时确保默认管理员账号存在（可用 .env 的 ADMIN_USERNAME/ADMIN_PASSWORD 覆盖）"""
    _ensure()
    username = settings.admin_username
    with _lock:
        if db.q1("SELECT username FROM users WHERE username = ?", (username,)) is not None:
            return
        salt = uuid.uuid4().hex
        db.x(
            "INSERT INTO users(username, salt, password_hash, role, created_at) VALUES(?,?,?,?,?)",
            (username, salt, _hash_password(settings.admin_password, salt), "admin", _now()),
        )


# 进程退出时收尾（SQLite 下已即时落库，保留调用以兼容旧入口）
atexit.register(flush_stats)
