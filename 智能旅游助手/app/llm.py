"""LLM 工厂：DeepSeek 双模型架构
- deepseek-reasoner：深度思考模型（专家回答，完整保留思维链）
- deepseek-chat：快速模型（调度路由 / 结构化输出 / 工具调用）
"""

import time
from dataclasses import dataclass, field
from functools import lru_cache

from app.config import settings

# langchain 消息类型 -> OpenAI role
_ROLE_MAP = {"system": "system", "human": "user", "ai": "assistant"}


@dataclass
class ThinkingResponse:
    """思考模型响应：正文 + 思维链 + 思考耗时 + token 用量"""

    content: str = ""
    reasoning_content: str | None = None
    reasoning_tokens: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    tool_calls: list = field(default_factory=list)


def usage_of(resp) -> tuple[int, int, int]:
    """统一从各家响应对象里取 (prompt_tokens, completion_tokens, reasoning_tokens)。

    同时兼容三种形态：
    * 本文件自研的 `ThinkingResponse`（DeepSeek reasoner 原生 SDK）
    * LangChain 新式 `usage_metadata`
    * LangChain 旧式 `response_metadata["token_usage"]`
    """
    if isinstance(resp, ThinkingResponse):
        return resp.prompt_tokens, resp.completion_tokens, resp.reasoning_tokens or 0

    meta = getattr(resp, "usage_metadata", None)
    if meta:
        details = meta.get("output_token_details") or {}
        return (
            int(meta.get("input_tokens") or 0),
            int(meta.get("output_tokens") or 0),
            int(details.get("reasoning") or 0),
        )

    rmeta = getattr(resp, "response_metadata", None) or {}
    usage = rmeta.get("token_usage") or rmeta.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return (
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
        int(details.get("reasoning_tokens") or 0),
    )


class DeepSeekReasoner:
    """deepseek-reasoner 封装：原生 SDK 调用，完整捕获思维链"""

    def __init__(self):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=300,
            max_retries=1,
        )
        self.model = settings.llm_model

    @staticmethod
    def _to_oai_messages(messages):
        out = []
        for m in messages:
            role = _ROLE_MAP.get(getattr(m, "type", ""), "user")
            out.append({"role": role, "content": m.content})
        return out

    def invoke(self, messages) -> ThinkingResponse:
        t0 = time.time()
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=self._to_oai_messages(messages),
            stream=False,
        )
        msg = resp.choices[0].message
        usage = resp.usage
        details = getattr(usage, "completion_tokens_details", None) if usage else None
        return ThinkingResponse(
            content=msg.content or "",
            reasoning_content=getattr(msg, "reasoning_content", None),
            reasoning_tokens=getattr(details, "reasoning_tokens", None) if details else None,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0,
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0,
            seconds=round(time.time() - t0, 1),
        )


@lru_cache(maxsize=1)
def get_llm():
    """主推理模型：reasoner 思考模型 / OpenAI 兼容模型；Mock 模式返回 None"""
    if settings.is_mock:
        return None
    if "reasoner" in settings.llm_model.lower():
        return DeepSeekReasoner()
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=settings.llm_temperature,
        timeout=120,
        max_retries=1,
    )


@lru_cache(maxsize=1)
def get_router_llm():
    """快速模型：调度路由 / 结构化输出 / 工具调用（需 function calling 支持）"""
    if settings.is_mock:
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.llm_router_model or settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=0.1,
        timeout=60,
        max_retries=1,
    )
