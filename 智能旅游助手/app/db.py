"""SQLite 存储层：连接管理 + 建表 + 旧 JSON 数据一次性自动迁移。

为什么用 SQLite 而不是 PostgreSQL / MySQL
----------------------------------------
* **零配置、单文件**：数据库文件跟着 `$DATA_DIR` 持久化卷走，容器里不必再起
  一个数据库服务，也就不必为它单独买实例、配连接串、做备份。
* **有事务和索引**：收藏、会话这类持续追加的流水数据不必再「每次删除都全量重写文件」。
* **标准库自带 `sqlite3`**：不新增任何依赖，镜像体积与构建时间都不受影响。

线程模型
--------
uvicorn 单进程 + 线程池。这里用「单连接 + 可重入锁」，并把 `check_same_thread`
关掉：写入串行化，读多写少的场景完全够用，也避免了连接池带来的复杂度。
"""

import contextlib
import json
import logging
import sqlite3
import threading
from pathlib import Path

from app.config import settings

logger = logging.getLogger("travel.db")

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

# --------------------------------------------------------------------------- 表结构

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    salt          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    username   TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(username, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    ts         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

CREATE TABLE IF NOT EXISTS feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    message_index INTEGER NOT NULL,
    rating        TEXT NOT NULL,
    ts            REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    content    TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    username   TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(username, created_at DESC);

CREATE TABLE IF NOT EXISTS counters (
    key   TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agent_calls (
    agent TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
);

-- LLM 用量明细：token 消耗与成本是 AI 应用最核心的运行指标，
-- 只统计「调用次数」无法回答「这个月烧了多少钱」。
CREATE TABLE IF NOT EXISTS llm_usage (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    model             TEXT NOT NULL DEFAULT '',
    agent             TEXT NOT NULL DEFAULT '',
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens  INTEGER NOT NULL DEFAULT 0,
    ts                REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_usage_ts ON llm_usage(ts DESC);

-- 外部内容库：存放从站外导入的攻略内容（小红书 / 抖音 / 手工录入）
CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL DEFAULT 'manual',
    title       TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    city        TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    author      TEXT NOT NULL DEFAULT '',
    imported_by TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_city ON notes(city, created_at DESC);
"""


# --------------------------------------------------------------------------- 连接


def db_path() -> Path:
    """数据库文件位置：跟随 settings.data_dir（容器里即持久化卷）。"""
    return Path(settings.data_dir) / "travel.db"


def connect() -> sqlite3.Connection:
    """返回全局单例连接；首次调用时建表。"""
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is not None:
            return _conn
        p = db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(p),
            check_same_thread=False,  # 由 _lock 保证串行
            isolation_level=None,  # 自动提交，事务由调用方显式 BEGIN
            timeout=15,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        _conn = conn
        return conn


def init() -> dict:
    """建表 + 执行一次性的旧数据迁移。返回迁移统计，供启动日志使用。"""
    connect()
    try:
        return migrate_from_json()
    except Exception as e:
        # 迁移失败不能拖垮整站：旧文件原样还在（迁移只在其末尾改名），
        # 下次启动会重试；期间应用以空库运行，管理后台仍可正常使用。
        logger.exception("旧数据迁移失败，已跳过（下次启动会重试）: %s", e)
        return {"migrated": False, "error": str(e)}


# --------------------------------------------------------------------------- 查询辅助


def q(sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
    with _lock:
        return connect().execute(sql, params).fetchall()


def q1(sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
    with _lock:
        return connect().execute(sql, params).fetchone()


def x(sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
    with _lock:
        return connect().execute(sql, params)


# --------------------------------------------------------------------------- meta


def get_meta(key: str, default: str = "") -> str:
    row = q1("SELECT value FROM meta WHERE key = ?", (key,))
    return row["value"] if row else default


def set_meta(key: str, value: str):
    x(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


# --------------------------------------------------------------------------- 旧数据迁移


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def migrate_from_json() -> dict:
    """把历史 JSON / JSONL 数据一次性导入 SQLite。

    只在 meta.json_migrated 未置位时执行；导入完成后把旧文件改名为
    *.imported，既留了退路，也避免下次启动重复导入。
    """
    if get_meta("json_migrated") == "1":
        return {"migrated": False}

    data_dir = Path(settings.data_dir)
    stats = {"users": 0, "favorites": 0, "sessions": 0, "messages": 0, "migrated": True}

    # ---- users.json
    users = _read_json(data_dir / "users.json")
    if isinstance(users, dict):
        for name, u in users.items():
            if not isinstance(u, dict) or not u.get("password_hash"):
                continue
            x(
                "INSERT OR IGNORE INTO users(username, salt, password_hash, role, created_at) "
                "VALUES(?,?,?,?,?)",
                (
                    u.get("username") or name,
                    u.get("salt", ""),
                    u["password_hash"],
                    u.get("role", "user"),
                    float(u.get("created_at") or 0),
                ),
            )
            stats["users"] += 1

    # ---- favorites.jsonl
    for it in _read_jsonl(data_dir / "favorites.jsonl"):
        if not it.get("id"):
            continue
        x(
            "INSERT OR IGNORE INTO favorites(id, title, content, session_id, username, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                it["id"],
                it.get("title", ""),
                it.get("content", ""),
                it.get("session_id", ""),
                it.get("username", ""),
                float(it.get("created_at") or 0),
            ),
        )
        stats["favorites"] += 1

    # ---- sessions.jsonl（事件日志回放）
    sess_seen: set[str] = set()
    for evt in _read_jsonl(data_dir / "sessions.jsonl"):
        t = evt.get("type")
        if t == "session":
            s = evt.get("session") or {}
            sid = s.get("id")
            if not sid or sid in sess_seen:
                continue
            sess_seen.add(sid)
            created = float(s.get("created_at") or 0)
            x(
                "INSERT OR IGNORE INTO sessions(id, username, created_at, updated_at) VALUES(?,?,?,?)",
                (sid, "", created, created),
            )
            stats["sessions"] += 1
        elif t == "message":
            sid = evt.get("session_id")
            if not sid or sid not in sess_seen:
                continue
            x(
                "INSERT INTO messages(session_id, role, content, ts) VALUES(?,?,?,?)",
                (sid, evt.get("role", ""), evt.get("content", ""), float(evt.get("ts") or 0)),
            )
            x("UPDATE sessions SET updated_at = ? WHERE id = ?", (float(evt.get("ts") or 0), sid))
            stats["messages"] += 1
        elif t == "session_user":
            sid = evt.get("session_id")
            if sid and sid in sess_seen:
                x("UPDATE sessions SET username = ? WHERE id = ?", (evt.get("username", ""), sid))

    # ---- stats.json
    st = _read_json(data_dir / "stats.json")
    if isinstance(st, dict):
        for key in ("total_sessions", "total_messages", "likes", "dislikes"):
            if isinstance(st.get(key), (int, float)):
                x("INSERT OR REPLACE INTO counters(key, value) VALUES(?,?)", (key, int(st[key])))
        for agent, cnt in (st.get("agent_calls") or {}).items():
            if isinstance(cnt, (int, float)):
                x("INSERT OR REPLACE INTO agent_calls(agent, count) VALUES(?,?)", (agent, int(cnt)))

    set_meta("json_migrated", "1")

    # 旧文件留档，避免重复导入
    for name in ("users.json", "favorites.jsonl", "sessions.jsonl", "stats.json"):
        f = data_dir / name
        if f.exists():
            # 改名失败（如文件被占用）不应中断迁移：数据已经入库，
            # 留档只是防止下次重复导入。
            with contextlib.suppress(OSError):
                f.rename(f.with_suffix(f.suffix + ".imported"))

    return stats
