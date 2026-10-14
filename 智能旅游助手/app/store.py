"""会话与运营统计存储（演示实现：内存缓存 + JSONL 追加持久化）"""
import atexit
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path

from app.config import settings

_lock = threading.RLock()
_sessions: dict[str, dict] = {}
_loaded = False
_stats: dict | None = None
_save_timer: threading.Timer | None = None
_STATS_FLUSH_INTERVAL = 2.0  # 统计落盘防抖间隔（秒）


def _now() -> float:
    return time.time()


def _sessions_file() -> Path:
    return Path(settings.data_dir) / "sessions.jsonl"


def _stats_file() -> Path:
    return Path(settings.data_dir) / "stats.json"


def _append_event(evt: dict):
    f = _sessions_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(evt, ensure_ascii=False) + "\n")


def _ensure_loaded():
    """进程启动后首次访问时，从 JSONL 事件日志回放会话"""
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        f = _sessions_file()
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                if evt.get("type") == "session":
                    s = evt["session"]
                    _sessions[s["id"]] = {
                        "id": s["id"],
                        "messages": [],
                        "created_at": s.get("created_at", _now()),
                        "updated_at": s.get("created_at", _now()),
                        "username": s.get("username", ""),
                    }
                elif evt.get("type") == "session_user":
                    s = _sessions.get(evt.get("session_id"))
                    if s is not None:
                        s["username"] = evt.get("username", "")
                elif evt.get("type") == "message":
                    s = _sessions.get(evt.get("session_id"))
                    if s is not None:
                        s["messages"].append({
                            "role": evt.get("role"),
                            "content": evt.get("content"),
                            "ts": evt.get("ts"),
                        })
                        s["updated_at"] = evt.get("ts", _now())
        _loaded = True


# ================= 会话 =================
def get_or_create_session(session_id: str | None = None) -> dict:
    _ensure_loaded()
    with _lock:
        if session_id and session_id in _sessions:
            return _sessions[session_id]
        sid = session_id or uuid.uuid4().hex[:12]
        session = {"id": sid, "messages": [], "created_at": _now(), "updated_at": _now()}
        _sessions[sid] = session
        _append_event({"type": "session", "session": {"id": sid, "created_at": session["created_at"]}})
        _bump("total_sessions", 1)
        return session


def append_message(session_id: str, role: str, content: str):
    _ensure_loaded()
    with _lock:
        s = _sessions.get(session_id)
        if s is None:
            return
        ts = _now()
        s["messages"].append({"role": role, "content": content, "ts": ts})
        s["updated_at"] = ts
        _append_event({"type": "message", "session_id": session_id,
                       "role": role, "content": content, "ts": ts})
        _bump("total_messages", 1)


def get_session(session_id: str) -> dict | None:
    _ensure_loaded()
    with _lock:
        return _sessions.get(session_id)


def record_feedback(session_id: str, message_index: int, rating: str) -> bool:
    """记录用户对某条助手消息的点赞/点踩"""
    _ensure_loaded()
    with _lock:
        s = _sessions.get(session_id)
        if s is None:
            return False
        evt = {"type": "feedback", "session_id": session_id,
               "message_index": message_index, "rating": rating, "ts": _now()}
        _append_event(evt)
        _bump("likes" if rating == "like" else "dislikes", 1)
        return True


def set_session_user(session_id: str, username: str):
    """将会话关联到登录用户（用于运营侧统计各用户使用情况）"""
    _ensure_loaded()
    with _lock:
        s = _sessions.get(session_id)
        if s is None or not username:
            return
        if s.get("username") == username:
            return
        s["username"] = username
        _append_event({"type": "session_user", "session_id": session_id, "username": username})


def list_sessions(limit: int = 50) -> list[dict]:
    _ensure_loaded()
    with _lock:
        items = sorted(_sessions.values(), key=lambda s: s["updated_at"], reverse=True)[:limit]
        return [{
            "id": s["id"],
            "message_count": len(s["messages"]),
            "created_at": s["created_at"],
            "updated_at": s["updated_at"],
            "username": s.get("username", ""),
            "preview": (s["messages"][-1]["content"][:60] if s["messages"] else ""),
        } for s in items]


def list_user_sessions(username: str, limit: int = 50) -> list[dict]:
    """某个登录用户自己的会话列表（按最近活跃倒序）"""
    _ensure_loaded()
    with _lock:
        items = [s for s in _sessions.values() if s.get("username") == username]
        items.sort(key=lambda s: s["updated_at"], reverse=True)
        out = []
        for s in items[:limit]:
            first_user = next((m["content"] for m in s["messages"] if m.get("role") == "user"), "")
            out.append({
                "id": s["id"],
                "title": (first_user or "新对话").strip()[:40],
                "message_count": len(s["messages"]),
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
            })
        return out


def list_users_usage() -> list[dict]:
    """注册用户使用情况：会话数 / 消息数 / 最近活跃（基于会话归属统计）"""
    _load_users()
    _ensure_loaded()
    with _lock:
        usage: dict[str, dict] = {}
        for s in _sessions.values():
            u = s.get("username")
            if not u:
                continue
            it = usage.setdefault(u, {"session_count": 0, "message_count": 0, "last_active": 0})
            it["session_count"] += 1
            it["message_count"] += len(s.get("messages", []))
            it["last_active"] = max(it["last_active"], s.get("updated_at", 0))
        result = []
        for name, u in _users.items():
            it = usage.get(name, {"session_count": 0, "message_count": 0, "last_active": 0})
            result.append({
                "username": name,
                "role": u.get("role", "user"),
                "created_at": u.get("created_at", 0),
                **it,
            })
        result.sort(key=lambda x: x["last_active"] or x["created_at"], reverse=True)
        return result


# ================= 收藏 =================
def _favorites_file() -> Path:
    return Path(settings.data_dir) / "favorites.jsonl"


def _load_favorites() -> list[dict]:
    f = _favorites_file()
    items = []
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items


def _append_favorite(item: dict):
    f = _favorites_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def add_favorite(title: str, content: str, session_id: str = "", username: str = "") -> dict:
    """新增收藏；username 为归属用户，收藏按用户隔离"""
    with _lock:
        item = {
            "id": uuid.uuid4().hex[:10],
            "title": (title or content[:40]).strip()[:60],
            "content": content,
            "session_id": session_id,
            "username": username or "",
            "created_at": _now(),
        }
        _append_favorite(item)
        return item


def list_favorites(limit: int = 100, username: str | None = None) -> list[dict]:
    """列出收藏；传入 username 时只返回该用户自己的收藏"""
    with _lock:
        items = _load_favorites()
        if username is not None:
            items = [i for i in items if i.get("username", "") == username]
        items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return items[:limit]


def delete_favorite(fid: str, username: str | None = None) -> bool:
    """删除收藏；传入 username 时校验归属，只能删除自己的收藏"""
    with _lock:
        items = _load_favorites()
        target = next((i for i in items if i.get("id") == fid), None)
        if target is None:
            return False
        if username is not None and target.get("username", "") != username:
            return False
        rest = [i for i in items if i.get("id") != fid]
        f = _favorites_file()
        f.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in rest) + "\n",
                     encoding="utf-8")
        return True


# ================= 统计 =================
def _load_stats() -> dict:
    default = {"total_sessions": 0, "total_messages": 0, "agent_calls": {},
               "likes": 0, "dislikes": 0}
    f = _stats_file()
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            default.update({k: v for k, v in data.items() if k in default})
        except Exception:
            pass
    return default


def _write_stats_file():
    """真正落盘（调用方需持有 _lock）"""
    f = _stats_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(_stats, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_stats():
    """防抖落盘：合并高频计数变更，避免每条消息都同步写盘"""
    global _save_timer
    with _lock:
        if _save_timer is not None and _save_timer.is_alive():
            return
        _save_timer = threading.Timer(_STATS_FLUSH_INTERVAL, flush_stats)
        _save_timer.daemon = True
        _save_timer.start()


def flush_stats():
    """立即把内存统计写入磁盘（防抖定时器回调 / 进程退出时调用）"""
    global _save_timer
    with _lock:
        _save_timer = None
        if _stats is None:
            return
        try:
            _write_stats_file()
        except Exception:
            pass


def _bump(key: str, delta: int):
    global _stats
    if _stats is None:
        _stats = _load_stats()
    _stats[key] = _stats.get(key, 0) + delta
    _save_stats()


def record_agent_call(agent: str):
    global _stats
    with _lock:
        if _stats is None:
            _stats = _load_stats()
        calls = _stats.setdefault("agent_calls", {})
        calls[agent] = calls.get(agent, 0) + 1
    _save_stats()


def get_stats() -> dict:
    global _stats
    with _lock:
        if _stats is None:
            _stats = _load_stats()
        return {
            "total_sessions": _stats.get("total_sessions", 0),
            "total_messages": _stats.get("total_messages", 0),
            "agent_calls": dict(_stats.get("agent_calls", {})),
            "likes": _stats.get("likes", 0),
            "dislikes": _stats.get("dislikes", 0),
        }


# ================= 用户 =================
_users: dict[str, dict] = {}
_users_loaded = False


def _users_file() -> Path:
    return Path(settings.data_dir) / "users.json"


def _load_users():
    global _users_loaded
    if _users_loaded:
        return
    with _lock:
        if _users_loaded:
            return
        f = _users_file()
        if f.exists():
            try:
                _users.update(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        _users_loaded = True


def _save_users():
    f = _users_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(_users, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


def create_user(username: str, password: str, role: str = "user") -> tuple[dict | None, str]:
    username = (username or "").strip()
    if not username or not password:
        return None, "用户名和密码不能为空"
    _load_users()
    with _lock:
        if username in _users:
            return None, "用户名已存在"
        salt = uuid.uuid4().hex
        user = {
            "username": username,
            "salt": salt,
            "password_hash": _hash_password(password, salt),
            "role": role,
            "created_at": _now(),
        }
        _users[username] = user
        _save_users()
        return user, ""


def authenticate(username: str, password: str) -> dict | None:
    _load_users()
    with _lock:
        user = _users.get((username or "").strip())
        if not user:
            return None
        if user["password_hash"] != _hash_password(password, user["salt"]):
            return None
        return user


def get_user(username: str) -> dict | None:
    _load_users()
    with _lock:
        return _users.get((username or "").strip())


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    _load_users()
    with _lock:
        user = _users.get((username or "").strip())
        if not user:
            return False, "用户不存在"
        if user["password_hash"] != _hash_password(old_password, user["salt"]):
            return False, "旧密码错误"
        if not new_password:
            return False, "新密码不能为空"
        user["salt"] = uuid.uuid4().hex
        user["password_hash"] = _hash_password(new_password, user["salt"])
        _save_users()
        return True, ""


def ensure_default_admin():
    """启动时确保默认管理员账号存在（可用 .env 的 ADMIN_USERNAME/ADMIN_PASSWORD 覆盖）"""
    _load_users()
    username = settings.admin_username
    with _lock:
        if username not in _users:
            salt = uuid.uuid4().hex
            _users[username] = {
                "username": username,
                "salt": salt,
                "password_hash": _hash_password(settings.admin_password, salt),
                "role": "admin",
                "created_at": _now(),
            }
            _save_users()


# 进程退出时把防抖中的统计刷盘，避免丢计数
atexit.register(flush_stats)
