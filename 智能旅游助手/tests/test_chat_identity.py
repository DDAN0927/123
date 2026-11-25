"""对话链路的身份识别：内部信任头优先。

背景（真实事故，审计 #44）
--------------------------
公网只有 SpringBoot 一个入口，`AiProxyController` 转发前会**有意剥掉**
`Authorization` / `X-Auth-Token`，身份改由 `X-Internal-Secret` + `X-User-Name`
+ `X-User-Role` 传递（外部带不了正确密钥，所以不可伪造）。

但 `/api/chat` 与 `/api/chat/stream` 早期直接调 `optional_username(...)`，
只读被剥掉的那两个头；而 Python 自己的 token 库只由 Python 的
`/api/auth/login` 填充，那条路在公网拓扑下不可达。于是真实链路上用户名
**恒为 None**，引发四个用户可见故障：

1. 历史会话列表恒空（`sessions.username` 永远没人写）
2. 历史详情恒 404（归属校验必然不通过）
3. 登录用户被按匿名阈值限流（`_llm_user` 桶永远为空）
4. 运营看板里所有用户的会话数都是 0

这组用例把「身份头必须被对话链路识别」钉死，防止再退回只读 token。
"""

_INTERNAL_SECRET = "test-internal-secret"  # 与 conftest.py 的 AI_INTERNAL_SECRET 一致


def _identity(username: str) -> dict:
    """模拟 Spring 反代注入的身份头（不含任何 token）。"""
    return {"X-Internal-Secret": _INTERNAL_SECRET, "X-User-Name": username}


def _reset_llm_windows() -> None:
    from app import ratelimit

    ratelimit._llm_global.reset()
    ratelimit._llm_user.reset()
    ratelimit._llm_anon.reset()


def test_chat_binds_session_to_internal_user(client):
    """走一次真实对话，会话必须归属到内部头里的用户。"""
    alice = _identity("alice")

    r = client.post("/api/chat", json={"message": "北京三日游怎么安排"}, headers=alice)
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    assert sid, "对话必须下发 session_id"

    listed = client.get("/api/chat/sessions", headers=alice)
    assert listed.status_code == 200
    assert sid in [it["id"] for it in listed.json()], (
        "内部身份头没被对话链路识别：会话没有归属，用户的「历史会话」永远为空"
    )

    detail = client.get(f"/api/chat/history/{sid}", headers=alice)
    assert detail.status_code == 200, "自己的会话详情必须可读"
    assert detail.json()["messages"], "刚结束的对话至少要落一条消息"


def test_history_is_scoped_to_owner(client):
    """别人的会话一律 404 —— 归属校验依赖的正是同一个身份来源。"""
    alice = _identity("alice")
    r = client.post("/api/chat", json={"message": "上海周末去哪"}, headers=alice)
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]

    assert client.get(f"/api/chat/history/{sid}", headers=_identity("bob")).status_code == 404


def test_rate_limit_uses_user_bucket_for_internal_identity(client, monkeypatch, admin_headers):
    """带内部身份头 → 记在 user 桶，而不是匿名桶。"""
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    _reset_llm_windows()

    # message 为空 → 422；但限流依赖在 body 校验之前执行，计数已经发生。
    # 所以这是一次零 LLM 成本的「打一次桶」。
    r = client.post("/api/chat/stream", json={"message": ""}, headers=_identity("carol"))
    assert r.status_code == 422, r.text

    snap = client.get("/api/admin/ratelimit", headers=admin_headers).json()
    assert snap["active_keys"]["user"] >= 1, "登录用户应记在 user 桶（登录后阈值更宽松）"
    assert snap["active_keys"]["anonymous"] == 0, "带内部身份头的请求不应落入匿名桶"


def test_rate_limit_falls_back_to_anonymous_without_internal_header(client, monkeypatch, admin_headers):
    """没有内部头（含密钥错误）仍走匿名桶，不能因为这次改动放开限流。"""
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    _reset_llm_windows()

    r = client.post("/api/chat/stream", json={"message": ""})
    assert r.status_code == 422, r.text

    snap = client.get("/api/admin/ratelimit", headers=admin_headers).json()
    assert snap["active_keys"]["anonymous"] >= 1
    assert snap["active_keys"]["user"] == 0


def test_token_path_still_works_for_direct_debugging(client, new_user):
    """直连 7861 调试时仍可用 X-Auth-Token —— 兜底路径不能被这次改动打坏。"""
    r = client.get("/api/chat/sessions", headers=new_user["headers"])
    assert r.status_code == 200, r.text
