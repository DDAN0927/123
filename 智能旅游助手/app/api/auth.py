"""认证接口：注册 / 登录 / 改密码 / 当前用户"""
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

# 简单内存 token（进程重启后需重新登录，符合演示场景）
_tokens: dict[str, str] = {}  # token -> username


def _issue_token(username: str) -> str:
    token = uuid.uuid4().hex
    _tokens[token] = username
    return token


def current_username(authorization: str | None = Header(None)) -> str:
    """从 Authorization: Bearer <token> 解析当前登录用户名"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token in _tokens:
            return _tokens[token]
    raise HTTPException(401, "未登录或登录已过期")


def optional_username(authorization: str | None = Header(None)) -> str | None:
    """宽松版鉴权：未登录或 token 无效时返回 None 而不报错"""
    if authorization and authorization.startswith("Bearer "):
        return _tokens.get(authorization[7:].strip())
    return None


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


@router.post("/register", response_model=AuthResponse,
             dependencies=[Depends(auth_rate_limit)])
def register(req: RegisterRequest):
    """注册普通用户账号（默认角色 user），注册成功即自动登录。

    公网部署默认关闭开放注册（ALLOW_REGISTRATION=false），新账号由管理员创建。
    """
    if not settings.allow_registration:
        raise HTTPException(403, "本站已关闭开放注册，请联系管理员开通账号")
    user, err = create_user(req.username, req.password, role="user")
    if user is None:
        raise HTTPException(400, err)
    return AuthResponse(token=_issue_token(user["username"]),
                        username=user["username"], role=user["role"])


@router.post("/login", response_model=AuthResponse,
             dependencies=[Depends(auth_rate_limit)])
def login(req: LoginRequest):
    """用户名密码登录，返回 token 与角色"""
    user = authenticate(req.username, req.password)
    if user is None:
        raise HTTPException(401, "用户名或密码错误")
    return AuthResponse(token=_issue_token(user["username"]),
                        username=user["username"], role=user["role"])


@router.get("/me", response_model=UserInfo)
def me(authorization: str | None = Header(None)):
    """查询当前登录用户信息"""
    username = current_username(authorization)
    user = get_user(username)
    return UserInfo(username=username, role=user["role"] if user else "")


@router.post("/change-password")
def change_password_api(req: ChangePasswordRequest,
                        authorization: str | None = Header(None)):
    """修改当前登录用户密码（需校验旧密码）"""
    username = current_username(authorization)
    ok, err = change_password(username, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(400, err)
    return {"ok": True, "message": "密码修改成功"}


@router.post("/logout")
def logout(authorization: str | None = Header(None)):
    """退出登录（作废当前 token）"""
    if authorization and authorization.startswith("Bearer "):
        _tokens.pop(authorization[7:].strip(), None)
    return {"ok": True}