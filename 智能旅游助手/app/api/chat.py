"""对话接口：多Agent协作回答（同步 + SSE 流式）"""

import json
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.agents import EXPERTS
from app.agents.graph import get_graph
from app.api.auth import optional_username
from app.api.deps import require_user
from app.rag import coverage
from app.ratelimit import llm_rate_limit
from app.schemas import (
    AgentInfo,
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    SessionHistoryResponse,
    SimpleResult,
    TeamResponse,
    TraceItem,
    UserSessionItem,
)
from app.store import (
    append_message,
    get_or_create_session,
    get_session,
    list_user_sessions,
    record_feedback,
    set_session_user,
)

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/agents", response_model=TeamResponse)
def get_team():
    """Agent 团队介绍"""
    experts = [
        AgentInfo(
            name=n, title=m.TITLE, icon=m.ICON, description=m.DESCRIPTION, tools=[t.name for t in m.TOOLS]
        )
        for n, m in EXPERTS.items()
    ]
    return TeamResponse(
        supervisor={
            "name": "supervisor",
            "title": "调度中心",
            "icon": "🧭",
            "description": "意图识别、任务路由与结果汇总",
        },
        experts=experts,
    )


def _run_pipeline(req: ChatRequest, username: str | None = None):
    """运行多Agent协作流水线，逐步产出事件（供同步与SSE两种端点复用）"""
    session = get_or_create_session(req.session_id)
    if username:
        set_session_user(session["id"], username)
    message = req.message.strip()
    t0 = time.time()
    state = {
        "query": message,
        "history": session["messages"],
        "outputs": {},
        "trace": [],
        "steps": 0,
    }
    final_answer, trace, outputs = "", [], {}
    errors: dict[str, str] = {}
    sent_thinking: set[str] = set()
    # 先把会话ID下发，前端即使后续失败也能恢复历史
    yield {"type": "session", "session_id": session["id"]}

    # 城市覆盖判定在调度之前下发：前端能立刻把「这个城市没有攻略库」的提示条
    # 显示出来，而不是等模型答完再补一句免责声明。
    cov = coverage.detect(message).to_dict()
    yield {"type": "coverage", **cov}

    error_message = None
    try:
        for update in get_graph().stream(state, stream_mode="updates"):
            for node, data in update.items():
                if not isinstance(data, dict):
                    continue
                if node == "supervisor" and data.get("trace"):
                    item = data["trace"][-1]
                    trace.append(item)
                    yield {"type": "route", **item}
                elif node == "synthesize" and data.get("final_answer") is not None:
                    final_answer = data["final_answer"]
                    yield {
                        "type": "answer",
                        "content": final_answer,
                        "thinking": data.get("final_thinking"),
                        "thinking_seconds": data.get("thinking_seconds", 0),
                    }
                elif node in EXPERTS:
                    outputs = data.get("outputs", outputs)
                    # 专家级失败降级：告知前端哪一位没跑通，但整条链路继续
                    for agent_name, reason in (data.get("errors") or {}).items():
                        errors[agent_name] = reason
                        yield {"type": "agent_failed", "agent": agent_name, "message": reason}
                    # 推送该专家的思维链（深度思考过程）
                    for agent_name, th in (data.get("thinking") or {}).items():
                        if agent_name not in sent_thinking and th.get("content"):
                            sent_thinking.add(agent_name)
                            yield {
                                "type": "agent_thinking",
                                "agent": agent_name,
                                "content": th["content"],
                                "seconds": th.get("seconds", 0),
                            }
                    yield {"type": "agent_done", "agent": node}
    except Exception as e:
        error_message = f"Pipeline 执行失败: {e}"

    elapsed_ms = int((time.time() - t0) * 1000)
    # 会话持久化（失败时也保留用户提问，便于前端展示与重试）
    append_message(session["id"], "user", message)
    if final_answer:
        append_message(session["id"], "assistant", final_answer)

    if error_message:
        yield {"type": "error", "message": error_message, "session_id": session["id"]}

    yield {
        "type": "done",
        "session_id": session["id"],
        "trace": trace,
        "outputs": outputs,
        "errors": errors,
        "coverage": cov,
        "agent_calls": len(outputs),
        "elapsed_ms": elapsed_ms,
        "error": error_message,
    }


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(llm_rate_limit)])
def chat(req: ChatRequest, authorization: str | None = Header(None), x_auth_token: str | None = Header(None)):
    """同步对话：一次性返回最终结果与协作轨迹"""
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")

    result = {
        "answer": "",
        "session_id": "",
        "trace": [],
        "outputs": {},
        "errors": {},
        "coverage": {},
        "agent_calls": 0,
        "elapsed_ms": 0,
    }
    for evt in _run_pipeline(req, optional_username(authorization, x_auth_token)):
        if evt["type"] == "error":
            raise HTTPException(502, evt["message"])
        elif evt["type"] == "answer":
            result["answer"] = evt["content"]
        elif evt["type"] == "done":
            result.update(
                {
                    k: evt[k]
                    for k in (
                        "session_id",
                        "trace",
                        "outputs",
                        "errors",
                        "coverage",
                        "agent_calls",
                        "elapsed_ms",
                    )
                }
            )

    return ChatResponse(
        session_id=result["session_id"],
        answer=result["answer"],
        trace=[TraceItem(**t) for t in result["trace"]],
        outputs=result["outputs"],
        errors=result["errors"],
        coverage=result["coverage"],
        agent_calls=result["agent_calls"],
        elapsed_ms=result["elapsed_ms"],
    )


@router.post("/chat/feedback", response_model=SimpleResult)
def chat_feedback(req: FeedbackRequest):
    """消息反馈：记录用户对某条助手回答的点赞/点踩"""
    ok = record_feedback(req.session_id, req.message_index, req.rating)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return SimpleResult(
        ok=True, message=f"已记录「{'点赞' if req.rating == 'like' else '点踩'}」反馈，感谢你的评价！"
    )


@router.get("/chat/sessions", response_model=list[UserSessionItem])
def my_sessions(username: str = Depends(require_user)):
    """当前登录用户的会话列表（用于历史会话恢复）"""
    return list_user_sessions(username)


@router.get("/chat/history/{session_id}", response_model=SessionHistoryResponse)
def chat_history(session_id: str, username: str = Depends(require_user)):
    """读取自己某个会话的完整消息记录；非本人会话一律 404"""
    s = get_session(session_id)
    if not s or s.get("username") != username:
        raise HTTPException(404, "会话不存在")
    return SessionHistoryResponse(session_id=session_id, messages=s.get("messages", []))


@router.post("/chat/stream", dependencies=[Depends(llm_rate_limit)])
def chat_stream(
    req: ChatRequest, authorization: str | None = Header(None), x_auth_token: str | None = Header(None)
):
    """SSE 流式对话：实时推送路由/完成事件，便于前端展示多Agent协作过程"""
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")

    username = optional_username(authorization, x_auth_token)

    def gen():
        for evt in _run_pipeline(req, username):
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
