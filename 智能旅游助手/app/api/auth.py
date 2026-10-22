"""认证接口：注册 / 登录 / 改密码 / 当前用户"""

import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.ratelimit import auth_rate_limit
from app.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserInfo,
)
from app.store import authenticate, change_password, create_user, get_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 登录态：token -> (username, 过期时间戳)
#
# 为什么带 TTL：早期实现是 `token -> username` 的永久映射，token 一旦泄露
# 就没有任何失效手段（只能重启进程）。现在签发时写入过期时间，校验时顺带判断。
#
# 局限（明确说明，不假装它是生产级方案）：这是**进程内**存储，重启即失效，
# 多实例之间也不共享。真要多副本部署，应换成 Redis 或签名 JWT。
_tokens: dict[str, tuple[str, float]] = {}


def _sweep_expired() -> None:
    """清理过期 token，避免字典无限增长。"""
    now = time.time()
    for token in [t for t, (_, exp) in _tokens.items() if exp <= now]:
        _tokens.pop(token, None)


def _issue_token(username: str) -> str:
    token = uuid.uuid4().hex
    _tokens[token] = (username, time.time() + settings.token_ttl_seconds)
    if len(_tokens) > 1000:  # 顺手回收，避免长期运行内存只增不减
        _sweep_expired()
    return token


def _lookup_token(token: str | None) -> str | None:
    """按 token 查用户名；不存在或已过期返回 None（并顺手清掉过期项）。"""
    if not token:
        return None
    rec = _tokens.get(token)
    if rec is None:
        return None
    username, expires_at = rec
    if expires_at <= time.time():
        _tokens.pop(token, None)
        return None
    return username


def _revoke_user_tokens(username: str) -> int:
    """作废某个用户的全部登录态，返回作废数量。

    改密码后必须调用：否则旧密码泄露导致签发的 token 依然有效，
    「改密码」就等于没改。
    """
    doomed = [t for t, (u, _) in _tokens.items() if u == username]
    for t in doomed:
        _tokens.pop(t, None)
    return len(doomed)


def _extract_token(authorization: str | None, x_auth_token: str | None) -> str | None:
    """从请求头里取出 token，两种携带方式都支持。

    为什么要支持两种
    ----------------
    * `Authorization: Bearer <token>` —— 标准做法，本地与大多数平台都用它；
    * `X-Auth-Token: <token>` —— 兜底。**部分云平台的边缘 WAF 会把任何带
      `Authorization: Bearer` 的请求当成「SDK Token 直连」直接返回 403**
      （实测魔搭创空间的 `*.ms.show` 域名就是如此，且与 token 内容无关，
      应用层根本收不到请求）。此时前端改用 `X-Auth-Token` 即可正常通行。

    后端两种都认，所以前端换头、或换回标准头，都不需要动服务端。
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    if x_auth_token and x_auth_token.strip():
        return x_auth_token.strip()
    return None


def current_username(
    authorization: str | None = Header(None), x_auth_token: str | None = Header(None)
) -> str:
    """解析当前登录用户名，未登录 / token 失效或过期抛 401"""
    username = _lookup_token(_extract_token(authorization, x_auth_token))
    if username:
        return username
    raise HTTPException(401, "未登录或登录已过期")


def optional_username(
    authorization: str | None = Header(None), x_auth_token: str | None = Header(None)
) -> str | None:
    """宽松版鉴权：未登录或 token 无效 / 过期时返回 None 而不报错"""
    return _lookup_token(_extract_token(authorization, x_auth_token))


@router.get("/options")
def options():
    """公开的登录页选项：前端据此决定是否展示「注册」入口与限流提示。

    只暴露布尔开关，不含任何敏感信息。
    """
    return {
        "allow_registration": settings.allow_registration,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_anonymous_per_minute": settings.rate_limit_anonymous_per_minute,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
    }


@router.post("/register", response_model=AuthResponse, dependencies=[Depends(auth_rate_limit)])
def register(req: RegisterRequest):
    """注册普通用户账号（默认角色 user），注册成功即自动登录。

    公网部署默认关闭开放注册（ALLOW_REGISTRATION=false），新账号由管理员创建。
    """
    if not settings.allow_registration:
        raise HTTPException(403, "本站已关闭开放注册，请联系管理员开通账号")
    user, err = create_user(req.username, req.password, role="user")
    if user is None:
        raise HTTPException(400, err)
    return AuthResponse(token=_issue_token(user["username"]), username=user["username"], role=user["role"])


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(auth_rate_limit)])
def login(req: LoginRequest):
    """用户名密码登录，返回 token 与角色"""
    user = authenticate(req.username, req.password)
    if user is None:
        raise HTTPException(401, "用户名或密码错误")
    return AuthResponse(token=_issue_token(user["username"]), username=user["username"], role=user["role"])


@router.get("/me", response_model=UserInfo)
def me(authorization: str | None = Header(None), x_auth_token: str | None = Header(None)):
    """查询当前登录用户信息"""
    username = current_username(authorization, x_auth_token)
    user = get_user(username)
    return UserInfo(username=username, role=user["role"] if user else "")


@router.post("/change-password")
def change_password_api(
    req: ChangePasswordRequest,
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None),
):
    """修改当前登录用户密码（需校验旧密码）。

    改密成功后**作废该用户的全部旧 token**，强制所有设备重新登录 ——
    否则密码泄露后即使改了密码，攻击者手里的 token 仍然有效。
    """
    username = current_username(authorization, x_auth_token)
    ok, err = change_password(username, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(400, err)
    revoked = _revoke_user_tokens(username)
    return {"ok": True, "message": "密码修改成功，请重新登录", "revoked_tokens": revoked}


@router.post("/logout")
def logout(authorization: str | None = Header(None), x_auth_token: str | None = Header(None)):
    """退出登录（作废当前 token）"""
    token = _extract_token(authorization, x_auth_token)
    if token:
        _tokens.pop(token, None)
    return {"ok": True}
