"""共享鉴权依赖：管理员 / 登录用户校验"""
from fastapi import Header, HTTPException

from app.api.auth import current_username, optional_username
from app.store import get_user


def require_user(authorization: str | None = Header(None)) -> str:
    """要求已登录，返回用户名；未登录抛 401"""
    return current_username(authorization)


def require_admin(authorization: str | None = Header(None)) -> str:
    """要求管理员角色，返回用户名；未登录 401 / 非管理员 403"""
    username = current_username(authorization)
    user = get_user(username)
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    return username


def current_user_or_none(authorization: str | None = Header(None)) -> str | None:
    """可选鉴权：未登录返回 None"""
    return optional_username(authorization)
