"""存储层：密码哈希、收藏归属隔离、会话与消息持久化、计数。"""

import uuid

from app import store


def _uniq(prefix: str = "u") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------- 密码
def test_password_is_salted_hash_not_plaintext():
    name = _uniq()
    store.create_user(name, "secret-123", role="user")
    user = store.get_user(name)

    assert user is not None
    # 绝不能是明文
    assert user["password_hash"] != "secret-123"
    assert len(user["password_hash"]) == 64  # pbkdf2-hmac-sha256 的十六进制长度
    assert user["salt"] and user["salt"] != user["password_hash"]


def test_same_password_different_users_get_different_hashes():
    """每用户独立随机盐：相同密码不能产生相同哈希（防彩虹表）。"""
    a, b = _uniq("a"), _uniq("b")
    store.create_user(a, "same-password", role="user")
    store.create_user(b, "same-password", role="user")

    ua, ub = store.get_user(a), store.get_user(b)
    assert ua["salt"] != ub["salt"]
    assert ua["password_hash"] != ub["password_hash"]


def test_authenticate_success_and_failure():
    name = _uniq()
    store.create_user(name, "right-password", role="user")

    assert store.authenticate(name, "right-password") is not None
    assert store.authenticate(name, "wrong-password") is None
    assert store.authenticate("no-such-user", "whatever") is None


def test_create_duplicate_user_rejected():
    name = _uniq()
    store.create_user(name, "pw123456", role="user")
    user, err = store.create_user(name, "pw123456", role="user")
    assert user is None
    assert err


def test_change_password_requires_old_password():
    name = _uniq()
    store.create_user(name, "old-pw-123", role="user")

    assert store.change_password(name, "wrong-old", "new-pw-123")[0] is False
    assert store.change_password(name, "old-pw-123", "")[0] is False
    assert store.change_password(name, "old-pw-123", "new-pw-123")[0] is True

    assert store.authenticate(name, "new-pw-123") is not None
    assert store.authenticate(name, "old-pw-123") is None


# ---------------------------------------------------------------- 收藏归属
def test_favorite_is_scoped_to_owner():
    alice, bob = _uniq("alice"), _uniq("bob")
    store.create_user(alice, "pw123456", role="user")
    store.create_user(bob, "pw123456", role="user")

    fav = store.add_favorite("标题", "内容", "", username=alice)

    assert [f["id"] for f in store.list_favorites(username=alice)] == [fav["id"]]
    assert store.list_favorites(username=bob) == []

    # 他人不能删除
    assert store.delete_favorite(fav["id"], username=bob) is False
    # 本人可以删除
    assert store.delete_favorite(fav["id"], username=alice) is True
    assert store.list_favorites(username=alice) == []


def test_delete_unknown_favorite_returns_false():
    assert store.delete_favorite("no-such-favorite", username="anyone") is False


# ---------------------------------------------------------------- 会话
def test_session_and_messages_persist():
    session = store.get_or_create_session()
    sid = session["id"]

    store.append_message(sid, "user", "帮我规划北京三天")
    store.append_message(sid, "assistant", "第一天故宫……")

    loaded = store.get_session(sid)
    assert loaded is not None
    assert [m["role"] for m in loaded["messages"]] == ["user", "assistant"]
    assert loaded["messages"][0]["content"] == "帮我规划北京三天"


def test_get_or_create_session_is_idempotent():
    session = store.get_or_create_session()
    again = store.get_or_create_session(session["id"])
    assert again["id"] == session["id"]


def test_session_list_shows_message_count_and_preview():
    session = store.get_or_create_session()
    store.append_message(session["id"], "user", "去成都吃什么")

    listed = {s["id"]: s for s in store.list_sessions(limit=50)}
    assert session["id"] in listed
    assert listed[session["id"]]["message_count"] == 1
    assert "成都" in listed[session["id"]]["preview"]


def test_unknown_session_returns_none():
    assert store.get_session("no-such-session") is None


# ------------------------------------------------- 会话标题的 Markdown 清洗
def test_session_title_strips_markdown_markers():
    """标题取自首条用户消息，含 ### / ** / 链接时必须压成纯文本。"""
    session = store.get_or_create_session()
    store.append_message(
        session["id"],
        "user",
        "### 第1天 中轴线皇城\n**上午(8:00-12:30)**: [故宫](https://x.cn) `提示`",
    )
    title = {s["id"]: s for s in store.list_user_sessions("")}.get(session["id"], {}).get("title", "")
    assert "#" not in title
    assert "**" not in title
    assert "https://" not in title
    assert "第1天" in title


def test_session_preview_strips_table_pipes():
    """预览是最后一条消息，模型爱输出表格，列表里不能露裸竖线。"""
    session = store.get_or_create_session()
    store.append_message(session["id"], "assistant", "| 项目 | 金额 |\n| --- | --- |\n| 住宿 | 800 |")
    preview = {s["id"]: s for s in store.list_sessions(limit=50)}[session["id"]]["preview"]
    assert "|" not in preview
    assert "---" not in preview
    assert "住宿" in preview


# ---------------------------------------------------------------- 计数
def test_agent_call_counter_increments():
    before = store.get_stats()["agent_calls"].get("planner", 0)
    store.record_agent_call("planner")
    store.record_agent_call("planner")
    after = store.get_stats()["agent_calls"].get("planner", 0)
    assert after == before + 2


def test_feedback_rating_is_recorded():
    session = store.get_or_create_session()
    store.append_message(session["id"], "user", "问题")
    store.append_message(session["id"], "assistant", "回答")

    likes_before = store.get_stats()["likes"]
    assert store.record_feedback(session["id"], 1, "like") is True
    assert store.get_stats()["likes"] == likes_before + 1
