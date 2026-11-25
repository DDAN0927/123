"""共享鉴权依赖：管理员 / 登录用户校验

两种身份来源，优先级从高到低：
1. **内部信任头**（`X-Internal-Secret` + `X-User-Name` + `X-User-Role`）——
   SpringBoot 主后端验完 JWT 后转发过来的请求。这是现在线上实际走的路径：
   对外只有 SpringBoot 一个入口，AI 服务不直接暴露鉴权逻辑。
2. 本服务自己的 token（`X-Auth-Token` / `Authorization: Bearer`）——
   保留下来用于直连调试与兼容旧前端。

内部头的安全性靠「密钥只有两侧知道」：外部请求带不了正确密钥，
带错了就退回第 2 条路径，不会被当成已登录。
"""

from fastapi import Header, HTTPException

from app.api.auth import current_username, optional_username
from app.config import settings
from app.store import get_user


def _internal_identity(
    x_internal_secret: str | None, x_user_name: str | None, x_user_role: str | None
) -> tuple[str, str] | None:
    """校验内部信任头；不匹配返回 None（调用方继续走 token 路径）。"""
    if not settings.ai_internal_secret:
        return None  # 未配置即关闭，不给默认值开后门
    if x_internal_secret != settings.ai_internal_secret or not x_user_name:
        return None
    return x_user_name, (x_user_role or "user")


def require_user(
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None),
    x_internal_secret: str | None = Header(None),
    x_user_name: str | None = Header(None),
    x_user_role: str | None = Header(None),
) -> str:
    """要求已登录，返回用户名；未登录抛 401"""
    internal = _internal_identity(x_internal_secret, x_user_name, x_user_role)
    if internal:
        return internal[0]
    return current_username(authorization, x_auth_token)


def require_admin(
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None),
    x_internal_secret: str | None = Header(None),
    x_user_name: str | None = Header(None),
    x_user_role: str | None = Header(None),
) -> str:
    """要求管理员角色，返回用户名；未登录 401 / 非管理员 403"""
    internal = _internal_identity(x_internal_secret, x_user_name, x_user_role)
    if internal:
        if internal[1] != "admin":
            raise HTTPException(403, "需要管理员权限")
        return internal[0]
    username = current_username(authorization, x_auth_token)
    user = get_user(username)
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    return username


def current_user_or_none(
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None),
    x_internal_secret: str | None = Header(None),
    x_user_name: str | None = Header(None),
    x_user_role: str | None = Header(None),
) -> str | None:
    """可选鉴权：未登录返回 None"""
    internal = _internal_identity(x_internal_secret, x_user_name, x_user_role)
    if internal:
        return internal[0]
    return optional_username(authorization, x_auth_token)
