"""LangGraph 多Agent协作图：Supervisor 调度 + 5位专家 + 汇总节点"""

import contextlib
import inspect
import logging
from functools import lru_cache
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents import EXPERTS
from app.agents.prompts import SYNTHESIZE_PROMPT
from app.agents.supervisor import route_supervisor
from app.llm import get_llm, usage_of
from app.store import record_agent_call, record_llm_usage
from app.tools.rag_tool import get_rag_context

logger = logging.getLogger("travel.graph")


def _invoke_synth(llm, messages):
    """汇总阶段的 LLM 调用：顺带记录 token 用量（agent=synthesize）"""
    resp = llm.invoke(messages)
    with contextlib.suppress(Exception):  # 统计失败不能影响回答
        record_llm_usage(
            getattr(llm, "model", None) or getattr(llm, "model_name", None) or "unknown",
            *usage_of(resp),
            agent="synthesize",
        )
    return resp


class AgentState(TypedDict, total=False):
    query: str  # 当前用户问题
    history: list  # 会话历史 [{"role", "content", "ts"}]
    outputs: dict  # {专家名: 回答}
    errors: dict  # {专家名: 失败原因} —— 失败也算「已处理」，否则会被重复路由
    thinking: dict  # {专家名: {"content", "seconds"}} 思维链
    trace: list  # 路由轨迹 [{"agent", "reason"}]
    steps: int  # 已路由次数
    final_answer: str
    final_thinking: str
    thinking_seconds: float


def supervisor_node(state: AgentState) -> Command:
    """调度中心：决定下一位专家，或 FINISH 进入汇总"""
    # 把失败专家合并进「已完成」集合：否则 supervisor 会反复路由到同一个失败节点，
    # 直到撞上 max_agent_steps 才收敛，白白消耗轮次与时间。
    done = {**dict.fromkeys(state.get("errors", {}), "(该专家处理失败)"), **state.get("outputs", {})}
    decision = route_supervisor(state["query"], state.get("history", []), done, state.get("steps", 0))
    entry = {"agent": decision.next_agent, "reason": decision.reason}
    update = {"trace": [*state.get("trace", []), entry]}
    if decision.next_agent == "FINISH":
        return Command(goto="synthesize", update=update)
    return Command(goto=decision.next_agent, update={**update, "steps": state.get("steps", 0) + 1})


@lru_cache(maxsize=32)
def _accepts_history(fn) -> bool:
    """探测专家 run() 是否接受 history 参数（结果缓存，避免每个节点重复反射）。"""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):  # 内建函数 / C 扩展没有签名
        return False
    if "history" in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _call_expert(module, query: str, context: str, outputs: dict, history: list):
    """调用专家模块，兼容「三参旧契约」与「四参新契约」。

    历史契约是 `run(query, context, outputs)`；本轮为了让专家能理解指代与追问
    （「那第二天呢？」「换个便宜点的」），扩成四参。这里做签名探测而不是硬传
    `history=`：否则任何一个漏改的专家都会抛 TypeError，被上层当成「模型服务
    不可用」静默降级——**功能悄悄失效，日志里却看不出真正原因**。
    """
    if _accepts_history(module.run):
        return module.run(query, context, outputs, history=history)
    return module.run(query, context, outputs)


def _make_expert_node(name: str):
    module = EXPERTS[name]

    def node(state: AgentState) -> dict:
        # 自动检索知识库，注入专家上下文
        context = get_rag_context(state["query"])
        try:
            result = _call_expert(
                module, state["query"], context, state.get("outputs", {}), state.get("history", [])
            )
        except Exception as e:
            # 真实缺陷修复：此前这里没有兜底，任一专家抛异常都会击穿 LangGraph stream，
            # 用户拿到 502，且**已经成功完成的专家输出全部丢失**（final_answer 为空，
            # assistant 消息也不落库）。现在降级为「该专家失败」，其余专家照常汇总。
            logger.warning("专家 %s 执行失败，已降级: %s", name, e, exc_info=True)
            return {
                "errors": {**state.get("errors", {}), name: str(e)},
                "trace": [*state.get("trace", []), {"agent": name, "reason": f"执行失败: {e}"}],
            }
        if isinstance(result, tuple):
            answer, thinking, seconds = result
        else:  # 兼容旧式只返回字符串的专家
            answer, thinking, seconds = result, None, 0
        record_agent_call(name)
        update = {
            "outputs": {**state.get("outputs", {}), name: answer},
            "thinking": {
                **state.get("thinking", {}),
                **({name: {"content": thinking, "seconds": seconds}} if thinking else {}),
            },
        }
        return update

    return node


def synthesize_node(state: AgentState) -> dict:
    """汇总节点：单专家直接透传，多专家综合成一份最终回答"""
    outputs = state.get("outputs", {})
    errors = state.get("errors", {})
    query = state["query"]
    llm = get_llm()
    final_thinking, thinking_seconds = None, 0

    if not outputs:
        if errors:
            # 所有专家都失败：给用户可读的说明，而不是 502 或一句空回答
            answer = (
                "抱歉，这次没能完成分析 😢\n\n"
                f"参与的专家（{'、'.join(EXPERTS[k].TITLE for k in errors)}）执行时遇到问题，"
                "通常是模型服务临时不可用或超时。\n\n"
                "你可以：\n"
                "1. 稍等片刻后重试同一个问题\n"
                "2. 把问题拆得更具体一些（例如「成都 3 天行程」而不是「帮我看看成都」）\n"
                "3. 如果持续失败，请联系管理员检查模型服务状态"
            )
        elif llm is None:
            answer = (
                "你好！我是旅游智能助手 👋\n\n"
                "我的团队可以帮你：规划行程 🗓️、查询景点 🏛️、推荐美食 🍜、分析天气与预算 📊、解答旅行咨询 💬。\n\n"
                "试试问我：「帮我规划北京3天的行程」「成都有什么必吃的美食」「十一去杭州天气怎么样」\n\n"
                "（当前为 Mock 演示模式，接入 LLM 后可获得完整智能回答，配置方法见 README）"
            )
        else:
            resp = _invoke_synth(
                llm,
                [
                    SystemMessage(content="你是旅游智能助手，请友好地回应用户并引导其提出具体旅行需求。"),
                    HumanMessage(content=query),
                ],
            )
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
            # Mock 模式同样按人数均分预算：此前是 join 完再 [:3000]，
            # 三位专家时最后一位会被整体截掉（与 LLM 分支同一个坑）。
            budget = max(600, 3000 // max(1, len(outputs)))
            parts = [
                f"### {EXPERTS[k].ICON} {EXPERTS[k].TITLE}\n\n{str(v)[:budget]}" for k, v in outputs.items()
            ]
            answer = "\n\n---\n\n".join(parts)
        else:
            # 按专家数量均分字符预算。此前是「先整体拼接再 [:8000]」，
            # 一旦总长超限，排在最后的那位专家会被整体砍掉（典型是
            # 行程规划 + 美食 + 预算三专家协作），表现为最终回答凭空少一整块。
            budget = max(1200, 8000 // max(1, len(outputs)))
            outs = "\n\n".join(f"[{k}]\n{str(v)[:budget]}" for k, v in outputs.items())
            resp = _invoke_synth(
                llm,
                [
                    SystemMessage(
                        content=SYNTHESIZE_PROMPT.format(
                            outputs=f"<<<专家结果开始>>>\n{outs}\n<<<专家结果结束>>>"
                        )
                    ),
                    HumanMessage(content=query),
                ],
            )
            answer = resp.content
            final_thinking = getattr(resp, "reasoning_content", None)
            thinking_seconds = getattr(resp, "seconds", 0)

    if errors and outputs:
        answer += (
            f"\n\n---\n\n> ⚠️ 本次有 {len(errors)} 位专家"
            f"（{'、'.join(EXPERTS[k].TITLE for k in errors)}）未能完成分析，"
            "以上内容来自其余专家，相关部分可能不够完整。"
        )
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
