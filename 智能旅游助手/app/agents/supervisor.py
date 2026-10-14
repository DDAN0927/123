"""调度中心：意图识别与专家路由"""
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.prompts import SUPERVISOR_PROMPT
from app.config import settings
from app.llm import get_router_llm


class RouteDecision(BaseModel):
    next_agent: Literal["planner", "attractions", "food", "analyst", "consultant", "FINISH"] = Field(
        description="下一位处理的专家，或 FINISH 表示信息已足够"
    )
    reason: str = Field(default="", description="路由原因（简短一句话）")


# Mock 模式 / LLM 异常时的关键词路由规则（按优先级）
_KEYWORD_RULES = [
    ("planner", ["行程", "规划", "路线", "怎么玩", "怎么安排", "几天", "天游", "日程", "第一天"]),
    ("attractions", ["景点", "门票", "开放时间", "必去", "必玩", "玩什么", "值得去", "博物馆", "故宫", "长城"]),
    ("food", ["美食", "吃的", "吃啥", "餐厅", "小吃", "特色菜", "特产", "好吃的", "夜市", "火锅"]),
    ("analyst", ["天气", "下雨", "预算", "多少钱", "花费", "贵不贵", "分析", "消费"]),
]


def _keyword_route(query: str, outputs: dict) -> RouteDecision:
    for agent, words in _KEYWORD_RULES:
        if any(w in query for w in words) and agent not in outputs:
            return RouteDecision(next_agent=agent, reason="关键词匹配")
    return RouteDecision(next_agent="FINISH", reason="信息已足够")


def _history_digest(messages: list) -> str:
    if not messages:
        return "(无)"
    lines = []
    for m in messages[-6:]:
        role = "用户" if m.get("role") == "user" else "助手"
        lines.append(f"{role}: {str(m.get('content', ''))[:80]}")
    return "\n".join(lines) or "(无)"


def route_supervisor(query: str, history: list, outputs: dict, steps: int) -> RouteDecision:
    """决定下一位专家；超过步数上限自动收敛，LLM 不可用时降级为关键词路由"""
    if steps >= settings.max_agent_steps:
        return RouteDecision(next_agent="FINISH", reason="达到最大协作轮次")
    if settings.is_mock:
        return _keyword_route(query, outputs)

    # 路由走快速模型：低延迟 + 支持结构化输出
    llm = get_router_llm()
    outputs_brief = "\n".join(f"- {k}: {str(v)[:150]}" for k, v in outputs.items()) or "(暂无)"
    system = SUPERVISOR_PROMPT.format(history=_history_digest(history), outputs=outputs_brief)
    try:
        # function_calling 方式：DeepSeek 不支持 OpenAI 专有的 json_schema response_format
        router = llm.with_structured_output(RouteDecision, method="function_calling")
        resp = router.invoke([
            SystemMessage(content=system),
            HumanMessage(content=f"用户问题: {query}\n\n请决定路由。"),
        ])
        if resp and resp.next_agent:
            # 硬保障：拒绝重复路由已完成的专家（避免浪费思考时间与 token）
            if resp.next_agent in outputs:
                return RouteDecision(next_agent="FINISH", reason="所需专家均已完成，进入汇总")
            return resp
    except Exception:
        pass
    return _keyword_route(query, outputs)
