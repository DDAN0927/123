"""调度中心的 LLM 路由分支覆盖。

为什么这块一直没覆盖：`conftest.py` 把 `LLM_PROVIDER` 固定成 `mock`，于是
`route_supervisor()` 永远在第 57 行就 `return _keyword_route(...)`，
**61-97 这 37 行真实生产路径一次都没执行过**——包括两条最要紧的硬保障：

* 「路由到已完成的专家 → 直接 FINISH」（防止同一专家被反复调度、白烧 token）；
* 「LLM 路由抛异常 → 降级关键词路由」（路由失败不该让整个请求失败）。

这里用 `monkeypatch` 造一个假 router，把 settings 换成桩（不改全局配置），
让真实分支跑起来。被测的是分支逻辑，不是 LangChain 的实现。
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from app.agents import supervisor
from app.agents.supervisor import RouteDecision, route_supervisor


class _StubSettings:
    """只提供 route_supervisor 用到的两个字段，避免动全局 settings。"""

    def __init__(self, is_mock=False, max_agent_steps=8):
        self.is_mock = is_mock
        self.max_agent_steps = max_agent_steps


class _FakeRaw:
    """模拟 AIMessage 的 usage_metadata，用于覆盖 token 计量那段。"""

    usage_metadata: ClassVar[dict] = {
        "input_tokens": 11,
        "output_tokens": 3,
        "output_token_details": {},
    }


class _FakeRouter:
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self._raises:
            raise self._raises
        return self._result


class _FakeLLM:
    model_name = "fake-router"

    def __init__(self, router):
        self._router = router
        self.kwargs = None

    def with_structured_output(self, schema, **kwargs):
        self.kwargs = kwargs
        return self._router


def _install(monkeypatch, router, **settings_kwargs):
    llm = _FakeLLM(router)
    monkeypatch.setattr(supervisor, "settings", _StubSettings(**settings_kwargs))
    monkeypatch.setattr(supervisor, "get_router_llm", lambda: llm)
    recorded = []
    monkeypatch.setattr(supervisor, "record_llm_usage", lambda *a, **k: recorded.append((a, k)))
    return llm, recorded


# ---------- 历史摘要 ----------


def test_history_digest_empty():
    assert supervisor._history_digest([]) == "(无)"


def test_history_digest_truncates_and_labels_roles():
    msgs = [
        {"role": "user", "content": "北京三天怎么玩" * 20},
        {"role": "assistant", "content": "推荐故宫"},
    ]
    out = supervisor._history_digest(msgs)
    assert "用户: " in out and "助手: " in out
    # 前缀「用户: 」4 个字符 + 正文截断 80 → 单行不超过 84
    assert all(len(line) <= 84 for line in out.splitlines()), "每条要截断到 80 字，否则提示词会被撑爆"


def test_history_digest_keeps_only_last_six():
    msgs = [{"role": "user", "content": f"第{i}句"} for i in range(10)]
    out = supervisor._history_digest(msgs)
    assert len(out.splitlines()) == 6
    assert "第9句" in out and "第0句" not in out


# ---------- 步数上限与 mock ----------


def test_step_limit_finishes_without_calling_llm(monkeypatch):
    """达到轮次上限直接 FINISH（56），且不该再去调模型。"""
    llm, _ = _install(monkeypatch, _FakeRouter())
    d = route_supervisor("随便问", [], {}, steps=8)
    assert d.next_agent == "FINISH" and "轮次" in d.reason
    assert llm.kwargs is None, "上限收敛时不该调 LLM"


def test_mock_mode_uses_keyword_route(monkeypatch):
    _install(monkeypatch, _FakeRouter(), is_mock=True)
    d = route_supervisor("北京有什么好吃的", [], {}, steps=0)
    assert d.next_agent == "food"


# ---------- LLM 路由正常路径 ----------


def test_llm_route_returns_parsed_decision(monkeypatch):
    """正常路径：返回模型给出的专家，并记录 token 用量（82-87）。"""
    router = _FakeRouter(
        {"raw": _FakeRaw(), "parsed": RouteDecision(next_agent="attractions", reason="问景点")}
    )
    llm, recorded = _install(monkeypatch, router)

    d = route_supervisor("故宫门票多少", [], {}, steps=0)

    assert d.next_agent == "attractions"
    assert llm.kwargs == {"method": "function_calling", "include_raw": True}, (
        "必须用 function_calling + include_raw，否则拿不到 token 用量"
    )
    assert recorded and recorded[0][1].get("agent") == "supervisor", "路由这一步的消耗不能隐形"
    assert recorded[0][0][1:3] == (11, 3)


def test_llm_route_without_raw_skips_usage_but_still_routes(monkeypatch):
    """模型没带 raw 时（老式返回）仍要能路由，只是不计量。"""
    router = _FakeRouter(RouteDecision(next_agent="planner", reason="问行程"))
    _llm, recorded = _install(monkeypatch, router)

    d = route_supervisor("帮我排三天", [], {}, steps=0)

    assert d.next_agent == "planner"
    assert recorded == []


# ---------- 硬保障：重复专家 ----------


def test_duplicate_agent_is_downgraded_to_finish(monkeypatch):
    """已经跑过的专家不许再跑（90-91）—— 否则同一专家反复调度，白烧 token。"""
    router = _FakeRouter({"raw": None, "parsed": RouteDecision(next_agent="food")})
    _install(monkeypatch, router)

    d = route_supervisor("再推荐点吃的", [], {"food": "已经给过推荐"}, steps=1)

    assert d.next_agent == "FINISH"
    assert "已完成" in d.reason


def test_empty_parsed_falls_back_to_keywords(monkeypatch):
    """模型返回 None/空决策时不能让调用方拿到 None，要退回关键词路由（88 的假分支）。"""
    router = _FakeRouter({"raw": None, "parsed": None})
    _install(monkeypatch, router)

    d = route_supervisor("预算大概多少", [], {}, steps=0)

    assert d.next_agent == "analyst"


# ---------- 降级路径 ----------


def test_llm_exception_falls_back_to_keyword(monkeypatch):
    """路由失败要降级而不是抛出去（93-97）—— 一次路由抖动不该让整轮回答失败。"""
    router = _FakeRouter(raises=RuntimeError("router down"))
    _install(monkeypatch, router)

    d = route_supervisor("北京三天行程怎么安排", [], {}, steps=0)

    assert d.next_agent == "planner"
    assert d.reason == "关键词匹配"


def test_llm_exception_with_no_keyword_hit_finishes(monkeypatch):
    """既失败又没命中关键词时，收敛到 FINISH 而不是死循环。"""
    router = _FakeRouter(raises=TimeoutError("slow"))
    _install(monkeypatch, router)

    d = route_supervisor("嗯", [], {}, steps=0)

    assert d.next_agent == "FINISH"


@pytest.mark.parametrize(
    "outputs,expected",
    [
        ({}, "planner"),
        ({"planner": "已排好"}, "attractions"),
        ({"planner": "已排好", "attractions": "已推荐"}, "food"),
        ({"planner": "x", "attractions": "x", "food": "x"}, "analyst"),
        ({"planner": "x", "attractions": "x", "food": "x", "analyst": "x"}, "FINISH"),
    ],
)
def test_keyword_route_skips_completed_experts(outputs, expected):
    """关键词路由按优先级推进，且跳过已完成的专家。"""
    d = supervisor._keyword_route("北京三天行程、景点门票、美食、预算", outputs)
    assert d.next_agent == expected
