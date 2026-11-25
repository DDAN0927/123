"""对话接口：多Agent协作回答（同步 + SSE 流式）"""

import json
import logging
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agents import EXPERTS
from app.agents.graph import get_graph
from app.api.deps import current_user_or_none, require_user
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

log = logging.getLogger(__name__)

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


# 提示词里用「约 X 元」「通常 X 点开放」教模型**怎么写**不确定的价格与时间，
# 但模型偶尔会把占位符原样抄进回答（实测清单档城市必现），对用户毫无信息量，
# 还等于把内部提示词漏给了用户。出站前统一替换成可执行的话术。
_PLACEHOLDER_MONEY = re.compile(r"(?:约|大约|通常|一般)?\s*[Xx×]{1,2}\s*(?:元|块钱?|块)")
_PLACEHOLDER_TIME = re.compile(r"(?:通常|一般|大约)?\s*[Xx×]{1,2}\s*点(?:开放|开门|左右)?")
_PLACEHOLDER_SPAN = re.compile(r"(?:约|大约)?\s*[Xx×]{1,2}\s*(?:小时|分钟|钟头)")
# 替换后常与后半句的「请以官方渠道为准」撞车，合并成一句
_DOUBLE_HEDGE = re.compile(r"以景区公告为准[，,]\s*请以(?:官方渠道|景区公告)为准")


def _strip_placeholders(text: str) -> str:
    """把模型抄进回答的占位符（「约 X 元」「X 点开放」「约X小时」）换成正常话术。"""
    if not text or not any(c in text for c in "Xx×"):
        return text
    text = _PLACEHOLDER_MONEY.sub("以景区公告为准", text)
    text = _PLACEHOLDER_TIME.sub("以景区公告为准", text)
    text = _PLACEHOLDER_SPAN.sub("视行程节奏而定", text)
    return _DOUBLE_HEDGE.sub("以官方渠道为准", text)


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
    cov: dict = {}
    error_message = None
    elapsed_ms = 0

    # 用户消息必须在**任何 yield 与任何同步阻塞调用之前**落库。
    #
    # 为什么不能只放 finally：断流若发生在同步 LLM 调用内部，生成器根本没
    # 展开到 yield 点（它可能停在半空、也可能在别的线程里执行到一半就被丢弃），
    # `close()` 抛的是 `ValueError: generator already executing`，`finally`
    # 不保证执行 —— 验收实测 6 个样本会丢 1 次。
    # 此刻 pipeline 还没开始跑，客户端不可能已经断开，竞态从根上消失。
    try:
        append_message(session["id"], "user", message)
    except Exception as exc:
        # 用户消息都写不进去，跑完也存不下来，白烧 token —— 直接放弃本轮。
        log.error("会话 %s 写入用户消息失败，放弃本轮：%s", session["id"], exc)
        yield {
            "type": "error",
            "message": "会话存储暂时不可用，请稍后重试",
            "session_id": session["id"],
        }
        return

    # 整段（含最初两次 yield）都放进 try/finally：客户端随时可能收到第一个
    # 事件就断开，助手回答的落库必须覆盖这种情况。
    try:
        # 先把会话ID下发，前端即使后续失败也能恢复历史
        yield {"type": "session", "session_id": session["id"]}

        # 城市覆盖判定在调度之前下发：前端能立刻把「这个城市没有攻略库」的提示条
        # 显示出来，而不是等模型答完再补一句免责声明。
        cov = coverage.detect(message).to_dict()
        yield {"type": "coverage", **cov}

        for update in get_graph().stream(state, stream_mode="updates"):
            for node, data in update.items():
                if not isinstance(data, dict):
                    continue
                if node == "supervisor" and data.get("trace"):
                    item = data["trace"][-1]
                    trace.append(item)
                    yield {"type": "route", **item}
                elif node == "synthesize" and data.get("final_answer") is not None:
                    final_answer = _strip_placeholders(data["final_answer"])
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
    finally:
        # 助手回答：失败与断流时都要保留**已产出**的部分（便于前端展示与重试）。
        # 用户消息已经在 pipeline 之前落库，这里只补回答。
        # 注意：断流若发生在同步调用内部，这个 finally 本身可能不执行 ——
        # 所以「用户消息不丢」不能依赖它，只能依赖前置落库。
        elapsed_ms = int((time.time() - t0) * 1000)
        if final_answer:
            try:
                append_message(session["id"], "assistant", final_answer)
            except Exception as exc:  # 落库失败不能盖掉真正的错误 / 断流
                log.warning("会话 %s 写入回答失败：%s", session["id"], exc)

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
def chat(req: ChatRequest, username: str | None = Depends(current_user_or_none)):
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
    for evt in _run_pipeline(req, username):
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
def chat_stream(req: ChatRequest, username: str | None = Depends(current_user_or_none)):
    """SSE 流式对话：实时推送路由/完成事件，便于前端展示多Agent协作过程"""
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")

    def gen():
        for evt in _run_pipeline(req, username):
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
