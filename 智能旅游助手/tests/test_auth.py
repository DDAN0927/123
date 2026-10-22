"""认证与鉴权：登录、双鉴权头、token 过期/失效、RBAC。"""

import time

from app.api import auth as auth_mod


# ---------------------------------------------------------------- 登录
def test_login_success(client, admin_token):
    assert isinstance(admin_token, str) and len(admin_token) >= 16


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody-here", "password": "whatever"})
    assert r.status_code == 401


# ---------------------------------------------------------------- 双鉴权头
# 线上平台（魔搭创空间 *.ms.show）的边缘 WAF 会拦掉任何 Authorization: Bearer 请求，
# 前端因此改用 X-Auth-Token。两种头后端都必须认，否则换平台就全站登录态失效。
def test_me_with_x_auth_token(client, admin_headers):
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert r.json()["role"] == "admin"


def test_me_with_authorization_bearer(client, admin_token):
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_me_without_header_is_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_token_is_401(client):
    assert client.get("/api/auth/me", headers={"X-Auth-Token": "deadbeef"}).status_code == 401


def test_authorization_without_bearer_prefix_is_401(client, admin_token):
    """`Authorization: <token>`（漏了 Bearer 前缀）不应被当作有效凭证。"""
    r = client.get("/api/auth/me", headers={"Authorization": admin_token})
    assert r.status_code == 401


def test_empty_token_is_401(client):
    assert client.get("/api/auth/me", headers={"X-Auth-Token": "   "}).status_code == 401


# ---------------------------------------------------------------- 登出
def test_logout_invalidates_token(client, new_user):
    headers = new_user["headers"]
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


# ---------------------------------------------------------------- token 过期
def test_token_expiry_unit():
    """单元级：过期 token 查不到，且会被顺手清出字典（避免内存只增不减）。

    注意：这里**不能** `_tokens.clear()` —— 会把 session 级的 admin token 一起清掉，
    导致后续用例全部 401。只操作自己刚签发的那个 token。
    """
    token = auth_mod._issue_token("someone")
    assert auth_mod._lookup_token(token) == "someone"

    auth_mod._tokens[token] = ("someone", time.time() - 1)
    assert auth_mod._lookup_token(token) is None
    assert token not in auth_mod._tokens


def test_expired_token_rejected_by_api(client, new_user):
    token = new_user["token"]
    username, _ = auth_mod._tokens[token]
    auth_mod._tokens[token] = (username, time.time() - 1)

    r = client.get("/api/auth/me", headers={"X-Auth-Token": token})
    assert r.status_code == 401
    assert token not in auth_mod._tokens


# ---------------------------------------------------------------- 改密码
def test_change_password_revokes_old_tokens(client, new_user):
    """改密后旧 token 必须失效，否则「改密码」形同虚设。"""
    headers = new_user["headers"]
    new_pw = "newpw654321"

    r = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": new_user["password"], "new_password": new_pw},
    )
    assert r.status_code == 200, r.text
    assert r.json()["revoked_tokens"] >= 1

    assert client.get("/api/auth/me", headers=headers).status_code == 401

    r = client.post("/api/auth/login", json={"username": new_user["username"], "password": new_pw})
    assert r.status_code == 200


def test_change_password_wrong_old_password(client, new_user):
    r = client.post(
        "/api/auth/change-password",
        headers=new_user["headers"],
        json={"old_password": "not-my-password", "new_password": "whatever123"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------- 注册
def test_register_duplicate_username(client, new_user):
    r = client.post("/api/auth/register", json={"username": new_user["username"], "password": "another123"})
    assert r.status_code == 400


def test_register_rejects_short_password(client):
    r = client.post("/api/auth/register", json={"username": "shortpw-user", "password": "123"})
    assert r.status_code == 422


# ---------------------------------------------------------------- RBAC
def test_normal_user_cannot_read_admin_stats(client, new_user):
    assert client.get("/api/admin/stats", headers=new_user["headers"]).status_code == 403


def test_admin_can_read_admin_stats(client, admin_headers):
    r = client.get("/api/admin/stats", headers=admin_headers)
    assert r.status_code == 200
    assert "total_sessions" in r.json()


def test_anonymous_cannot_read_admin_stats(client):
    assert client.get("/api/admin/stats").status_code == 401
