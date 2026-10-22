"""多 Agent 图的容错测试。

对应本轮修复的核心缺陷：**单个专家抛异常会击穿整条链路**。
修复前，任一专家失败都会让 `graph.stream()` 抛出，用户拿到 502，
且此前已成功完成的专家输出全部丢失（assistant 消息不落库）。
"""

from types import SimpleNamespace

import pytest

from app.agents import graph as G


def _fake_expert(answer: str = "已完成的回答"):
    def run(query, context, outputs):
        return answer, None, 0

    return SimpleNamespace(run=run, TITLE="测试专家", ICON="🧪")


def _boom_expert():
    def run(query, context, outputs):
        raise RuntimeError("模型服务不可用")

    return SimpleNamespace(run=run, TITLE="坏专家", ICON="💥")


def test_failed_expert_is_isolated(monkeypatch):
    monkeypatch.setitem(G.EXPERTS, "planner", _boom_expert())
    node = G._make_expert_node("planner")

    out = node({"query": "北京3天行程", "outputs": {}, "trace": [], "steps": 0})

    assert "planner" not in out.get("outputs", {})
    assert "模型服务不可用" in out["errors"]["planner"]
    # 失败也要留一条轨迹，运营看板才看得出「这次为什么没有行程」
    assert out["trace"][-1]["agent"] == "planner"


def test_successful_expert_still_records_output(monkeypatch):
    monkeypatch.setitem(G.EXPERTS, "planner", _fake_expert("第1天 故宫"))
    node = G._make_expert_node("planner")

    out = node({"query": "北京3天行程", "outputs": {}, "trace": [], "steps": 0})

    assert out["outputs"]["planner"] == "第1天 故宫"
    assert not out.get("errors")


def test_legacy_three_arg_expert_still_works(monkeypatch):
    """专家契约从三参扩到四参，老签名不能被当成「执行失败」静默降级。

    此前直接 `module.run(..., history=...)`，漏改的专家会抛 TypeError，
    被上层当成「模型服务不可用」——功能悄悄失效，日志里看不出真正原因。
    """
    seen = {}

    def run(query, context, outputs):  # 故意不接 history
        seen["called"] = True
        return "老签名专家回答"

    monkeypatch.setitem(G.EXPERTS, "planner", SimpleNamespace(run=run, TITLE="老专家", ICON="🧓"))
    out = G._make_expert_node("planner")({"query": "北京3天行程", "outputs": {}, "trace": [], "steps": 0})

    assert seen.get("called") is True
    assert out["outputs"]["planner"] == "老签名专家回答"
    assert not out.get("errors")


def test_four_arg_expert_receives_history(monkeypatch):
    """新契约：专家必须能拿到对话历史，否则「那第二天呢」这类追问会失效。"""
    got = {}

    def run(query, context, outputs, history=None):
        got["history"] = history
        return "ok"

    monkeypatch.setitem(G.EXPERTS, "planner", SimpleNamespace(run=run, TITLE="新专家", ICON="🆕"))
    hist = [{"role": "user", "content": "北京3天"}]
    G._make_expert_node("planner")(
        {"query": "那第二天呢", "outputs": {}, "trace": [], "steps": 0, "history": hist}
    )
    assert got["history"] == hist


def test_failed_expert_is_not_routed_twice(monkeypatch):
    """失败专家必须被算作「已处理」，否则会被反复路由到，直到耗尽轮次。"""
    from langgraph.types import Command

    monkeypatch.setitem(G.EXPERTS, "planner", _boom_expert())
    # mock 模式下走关键词路由：问题含「行程」会命中 planner
    cmd = G.supervisor_node(
        {
            "query": "北京3天行程怎么安排",
            "history": [],
            "outputs": {},
            "errors": {"planner": "boom"},
            "steps": 1,
        }
    )
    assert isinstance(cmd, Command)
    assert cmd.goto == "synthesize"


def test_synthesize_degrades_when_all_experts_fail():
    """全部失败时给用户可读的说明，而不是空回答。"""
    out = G.synthesize_node({"query": "北京3天行程", "outputs": {}, "errors": {"planner": "boom"}})
    assert "抱歉" in out["final_answer"]
    assert "重试" in out["final_answer"]


def test_synthesize_keeps_partial_output_with_warning(monkeypatch):
    """部分成功：保留成功内容，并显式告知哪一位没跑通。"""
    monkeypatch.setitem(G.EXPERTS, "planner", _fake_expert("第1天 故宫"))
    monkeypatch.setitem(G.EXPERTS, "food", _boom_expert())

    out = G.synthesize_node(
        {
            "query": "北京行程和美食",
            "outputs": {"planner": "第1天 故宫"},
            "errors": {"food": "boom"},
        }
    )
    assert "第1天 故宫" in out["final_answer"]
    assert "未能完成分析" in out["final_answer"]


@pytest.mark.parametrize("agent_count", [2, 3, 5])
def test_multi_expert_output_is_not_truncated_to_last_only(agent_count):
    """回归：多专家汇总曾对拼接结果整体 [:8000] 截断，
    导致排在最后的专家整块消失。现在按人数均分预算，每位专家都要留痕。"""
    names = list(G.EXPERTS)[:agent_count]
    outputs = {n: f"MARK-{n}-" + "内容" * 4000 for n in names}

    out = G.synthesize_node({"query": "综合问题", "outputs": outputs, "errors": {}})
    # mock 模式会走「直接拼接」分支，这里验证的是拼接逻辑本身不丢块
    for n in names:
        assert f"MARK-{n}" in out["final_answer"]
