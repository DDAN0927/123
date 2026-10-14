"""LangGraph 多Agent协作图：Supervisor 调度 + 5位专家 + 汇总节点"""
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents import EXPERTS
from app.agents.prompts import SYNTHESIZE_PROMPT
from app.agents.supervisor import route_supervisor
from app.llm import get_llm
from app.store import record_agent_call
from app.tools.rag_tool import get_rag_context


class AgentState(TypedDict, total=False):
    query: str        # 当前用户问题
    history: list     # 会话历史 [{"role", "content", "ts"}]
    outputs: dict     # {专家名: 回答}
    thinking: dict    # {专家名: {"content", "seconds"}} 思维链
    trace: list       # 路由轨迹 [{"agent", "reason"}]
    steps: int        # 已路由次数
    final_answer: str
    final_thinking: str
    thinking_seconds: float


def supervisor_node(state: AgentState) -> Command:
    """调度中心：决定下一位专家，或 FINISH 进入汇总"""
    decision = route_supervisor(
        state["query"], state.get("history", []), state.get("outputs", {}), state.get("steps", 0)
    )
    entry = {"agent": decision.next_agent, "reason": decision.reason}
    update = {"trace": state.get("trace", []) + [entry]}
    if decision.next_agent == "FINISH":
        return Command(goto="synthesize", update=update)
    return Command(goto=decision.next_agent, update={**update, "steps": state.get("steps", 0) + 1})


def _make_expert_node(name: str):
    module = EXPERTS[name]

    def node(state: AgentState) -> dict:
        # 自动检索知识库，注入专家上下文
        context = get_rag_context(state["query"])
        result = module.run(state["query"], context, state.get("outputs", {}))
        if isinstance(result, tuple):
            answer, thinking, seconds = result
        else:  # 兼容旧式只返回字符串的专家
            answer, thinking, seconds = result, None, 0
        record_agent_call(name)
        update = {
            "outputs": {**state.get("outputs", {}), name: answer},
            "thinking": {**state.get("thinking", {}),
                         **({name: {"content": thinking, "seconds": seconds}} if thinking else {})},
        }
        return update

    return node


def synthesize_node(state: AgentState) -> dict:
    """汇总节点：单专家直接透传，多专家综合成一份最终回答"""
    outputs = state.get("outputs", {})
    query = state["query"]
    llm = get_llm()
    final_thinking, thinking_seconds = None, 0

    if not outputs:
        if llm is None:
            answer = (
                "你好！我是旅游智能助手 👋\n\n"
                "我的团队可以帮你：规划行程 🗓️、查询景点 🏛️、推荐美食 🍜、分析天气与预算 📊、解答旅行咨询 💬。\n\n"
                "试试问我：「帮我规划北京3天的行程」「成都有什么必吃的美食」「十一去杭州天气怎么样」\n\n"
                "（当前为 Mock 演示模式，接入 LLM 后可获得完整智能回答，配置方法见 README）"
            )
        else:
            resp = llm.invoke([
                SystemMessage(content="你是旅游智能助手，请友好地回应用户并引导其提出具体旅行需求。"),
                HumanMessage(content=query),
            ])
            answer = resp.content
            final_thinking = getattr(resp, "reasoning_content", None)
            thinking_seconds = getattr(resp, "seconds", 0)
    elif len(outputs) == 1:
        # 单专家：直接透传，同时把该专家的思维链一并带出（避免思考过程丢失）
        answer = next(iter(outputs.values()))
        only = next(iter(outputs))
        th = (state.get("thinking") or {}).get(only) or {}
        final_thinking = th.get("content")
        thinking_seconds = th.get("seconds", 0)
    else:
        if llm is None:
            parts = [f"### {EXPERTS[k].ICON} {EXPERTS[k].TITLE}\n\n{v}" for k, v in outputs.items()]
            answer = "\n\n---\n\n".join(parts)[:3000]
        else:
            outs = "\n\n".join(f"[{k}]\n{v}" for k, v in outputs.items())
            resp = llm.invoke([
                SystemMessage(content=SYNTHESIZE_PROMPT.format(query=query, outputs=outs[:8000])),
                HumanMessage(content=query),
            ])
            answer = resp.content
            final_thinking = getattr(resp, "reasoning_content", None)
            thinking_seconds = getattr(resp, "seconds", 0)
    return {
        "final_answer": answer,
        "final_thinking": final_thinking,
        "thinking_seconds": thinking_seconds,
    }


_graph = None


def get_graph():
    """懒加载编译 LangGraph 图"""
    global _graph
    if _graph is None:
        g = StateGraph(AgentState)
        g.add_node("supervisor", supervisor_node)
        for name in EXPERTS:
            g.add_node(name, _make_expert_node(name))
            g.add_edge(name, "supervisor")  # 专家完成后回到调度中心
        g.add_node("synthesize", synthesize_node)
        g.add_edge(START, "supervisor")
        g.add_edge("synthesize", END)
        _graph = g.compile()
    return _graph
