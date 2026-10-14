"""专家 Agent 运行基座：统一的 RAG 上下文注入、工具调用循环、思维链捕获"""
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm, get_router_llm

_MAX_TOOL_ROUNDS = 4  # 单个专家最多工具调用轮次


def _mock_expert_answer(title: str, query: str, context: str) -> str:
    """Mock 模式：无 LLM 时的降级回答（用于演示与联调）"""
    lines = [
        f"> ⚙️ 当前为 Mock 模式（未接入 LLM），以下为「{title}」基于知识库资料的简化回答：",
        "",
    ]
    if context and not context.startswith("("):
        lines.append(context[:1200])
        lines += ["", "—— 完整个性化回答需要接入 LLM（配置方法见 README）——"]
    else:
        lines.append(f"收到问题「{query}」。接入 LLM 后我将提供完整分析。")
    return "\n".join(lines)


def run_expert(name: str, title: str, system_prompt: str, query: str,
               context: str, outputs: dict | None = None, tools: list | None = None):
    """运行一个专家 Agent：注入RAG上下文与协作上下文，处理工具调用循环

    返回 (回答, 思维链, 思考耗时秒)；非思考模型思维链为 None
    """
    llm = get_llm()
    prompt = system_prompt
    if context:
        prompt += f"\n\n## 知识库参考资料（检索自旅游攻略库）\n{context}"
    if outputs:
        prompt += "\n\n## 其他专家已提供的信息（可参考，勿重复）\n" + "\n\n".join(
            f"[{k}]\n{v}" for k, v in outputs.items()
        )[:4000]

    if llm is None:
        return _mock_expert_answer(title, query, context), None, 0

    messages = [SystemMessage(content=prompt), HumanMessage(content=query)]

    if tools:
        # 工具型专家（如数据分析师）走快速模型：思考模型不支持 function calling
        fast = get_router_llm() or llm
        bound = fast.bind_tools(tools)
        for _ in range(_MAX_TOOL_ROUNDS):
            resp = bound.invoke(messages)
            if not getattr(resp, "tool_calls", None):
                return resp.content, getattr(resp, "reasoning_content", None), 0
            messages.append(resp)
            for tc in resp.tool_calls:
                tool_obj = next((t for t in tools if t.name == tc["name"]), None)
                try:
                    result = tool_obj.invoke(tc["args"]) if tool_obj else f"未知工具: {tc['name']}"
                except Exception as e:
                    result = f"工具执行失败: {e}"
                messages.append(ToolMessage(content=str(result), tool_call_id=tc.get("id") or "tool"))
        messages.append(HumanMessage(content="请基于以上工具结果给出最终回答，不要再调用工具。"))
        resp = fast.invoke(messages)
        return resp.content, getattr(resp, "reasoning_content", None), 0

    # 思考型专家：deepseek-reasoner 深度推理，捕获思维链
    resp = llm.invoke(messages)
    seconds = getattr(resp, "seconds", 0)
    return resp.content, getattr(resp, "reasoning_content", None), seconds
