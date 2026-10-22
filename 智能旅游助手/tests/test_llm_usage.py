"""LLM 用量采集的测试：token 统计是成本治理的基础，不能静默失效。"""

from types import SimpleNamespace

from app.llm import ThinkingResponse, usage_of
from app.store import get_stats, record_llm_usage


def test_usage_of_thinking_response():
    resp = ThinkingResponse(content="hi", prompt_tokens=120, completion_tokens=340, reasoning_tokens=200)
    assert usage_of(resp) == (120, 340, 200)


def test_usage_of_langchain_usage_metadata():
    """新版 LangChain 把用量放在 usage_metadata 里。"""
    resp = SimpleNamespace(
        usage_metadata={"input_tokens": 10, "output_tokens": 20, "output_token_details": {"reasoning": 5}}
    )
    assert usage_of(resp) == (10, 20, 5)


def test_usage_of_legacy_response_metadata():
    """老式 OpenAI 兼容返回走 response_metadata["token_usage"]。"""
    resp = SimpleNamespace(
        response_metadata={
            "token_usage": {
                "prompt_tokens": 7,
                "completion_tokens": 9,
                "completion_tokens_details": {"reasoning_tokens": 3},
            }
        }
    )
    assert usage_of(resp) == (7, 9, 3)


def test_usage_of_unknown_shape_is_zero():
    """拿不到用量时返回 0，而不是抛异常打断主链路。"""
    assert usage_of(SimpleNamespace()) == (0, 0, 0)


def test_record_llm_usage_shows_up_in_stats():
    before = get_stats()["llm_usage"]["total_tokens"]
    record_llm_usage("deepseek-reasoner", 1000, 2000, 500, agent="planner")
    usage = get_stats()["llm_usage"]

    assert usage["total_tokens"] == before + 3000
    assert usage["reasoning_tokens"] >= 500
    assert usage["by_agent"]["planner"]["prompt_tokens"] >= 1000
    assert usage["estimated_cost_cny"] > 0


def test_record_llm_usage_ignores_empty_usage():
    """没有 token 的调用不写库，避免污染统计。"""
    before = get_stats()["llm_usage"]["calls"]
    record_llm_usage("m", 0, 0)
    assert get_stats()["llm_usage"]["calls"] == before


def test_cost_is_priced_per_model():
    """双模型单价差 2~4 倍：成本必须按模型分组累加，不能拿总量乘单一单价。

    deepseek-chat     : 输入 2 元/M，输出 8 元/M  -> 1M+1M = 10 元
    deepseek-reasoner : 输入 4 元/M，输出 16 元/M -> 1M+1M = 20 元
    """
    before = get_stats()["llm_usage"]
    record_llm_usage("deepseek-chat", 1_000_000, 1_000_000, agent="supervisor")
    record_llm_usage("deepseek-reasoner", 1_000_000, 1_000_000, agent="planner")

    usage = get_stats()["llm_usage"]

    def cost_of(model: str) -> float:
        return usage["by_model"].get(model, {}).get("estimated_cost_cny", 0.0) - before["by_model"].get(
            model, {}
        ).get("estimated_cost_cny", 0.0)

    assert abs((usage["estimated_cost_cny"] - before["estimated_cost_cny"]) - 30.0) < 1e-6
    assert abs(cost_of("deepseek-chat") - 10.0) < 1e-6
    assert abs(cost_of("deepseek-reasoner") - 20.0) < 1e-6


def test_unknown_model_falls_back_to_reasoner_price():
    """模型名拿不到时按贵的档位估：宁可高估，不可低估。"""
    from app.store import _price_of

    assert _price_of("unknown") == _price_of("deepseek-reasoner")
    assert _price_of("deepseek-chat")[0] < _price_of("deepseek-reasoner")[0]
