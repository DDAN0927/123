"""运营管理接口：统计看板、会话管理与注册用户使用情况（仅管理员）"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_admin
from app.config import settings
from app.rag import retriever
from app.schemas import AdminCreateUserRequest, SessionSummary, StatsResponse
from app.store import create_user, get_session, get_stats, list_sessions, list_users_usage

router = APIRouter(prefix="/api/admin", tags=["admin"])

__all__ = ["require_admin", "router"]


@router.get("/stats", response_model=StatsResponse)
def stats(_admin: str = Depends(require_admin)):
    """运营统计：会话数、消息数、各专家调用分布、系统状态"""
    s = get_stats()
    return StatsResponse(
        total_sessions=s["total_sessions"],
        total_messages=s["total_messages"],
        agent_calls=s["agent_calls"],
        likes=s.get("likes", 0),
        dislikes=s.get("dislikes", 0),
        index_ready=retriever.index_ready(),
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        llm_usage=s.get("llm_usage", {}),
    )


@router.get("/sessions", response_model=list[SessionSummary])
def sessions(limit: int = 50, _admin: str = Depends(require_admin)):
    """最近会话列表"""
    return list_sessions(limit)


@router.get("/sessions/{session_id}")
def session_detail(session_id: str, _admin: str = Depends(require_admin)):
    """会话详情（完整消息记录）"""
    s = get_session(session_id)
    if not s:
        raise HTTPException(404, "会话不存在")
    return s


@router.get("/users")
def users(_admin: str = Depends(require_admin)):
    """注册用户使用情况：角色 / 注册时间 / 会话数 / 消息数 / 最近活跃"""
    return {"users": list_users_usage()}


@router.post("/users")
def create_user_api(req: AdminCreateUserRequest, _admin: str = Depends(require_admin)):
    """管理员开通账号。

    公网部署默认关闭开放注册（ALLOW_REGISTRATION=false），
    新账号只能由管理员从这里创建，避免任意人注册后白嫖 LLM 额度。
    """
    role = req.role if req.role in ("user", "admin") else "user"
    user, err = create_user(req.username, req.password, role=role)
    if user is None:
        raise HTTPException(400, err)
    return {
        "ok": True,
        "username": user["username"],
        "role": user["role"],
        "message": f"账号「{user['username']}」已创建",
    }


@router.get("/ratelimit")
def ratelimit_status(_admin: str = Depends(require_admin)):
    """当前限流配置与各窗口占用情况（排查额度被刷时用）"""
    from app.ratelimit import snapshot

    return snapshot()
