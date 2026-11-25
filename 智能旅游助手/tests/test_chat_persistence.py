"""断流时仍持久化已产出的问答（回归 #8）。

`_run_pipeline` 是生成器，SSE 会把事件逐个写出去。用户在回答过程中关掉页面，
生成器在某个 `yield` 处被 `close()`，抛的是 `GeneratorExit` —— 它**不是**
`Exception`。早期写法把 `append_message` 放在 `try/except Exception` 之后，
于是整段被跳过：这一轮问答在历史里彻底消失，用户明明问过，刷新后什么都没有。

但只把落库挪进 `finally` 还不够：**断流若发生在同步 LLM 调用内部**，生成器
根本没展开到 yield 点，`close()` 会抛 `ValueError: generator already
executing`，`finally` 不保证执行（验收实测 6 个样本丢 1 次）。所以用户消息改成
在 pipeline 之前落库，回答仍留在 finally。

这组用例用 `gen.close()` 与假 graph 精确模拟两种断开时机，不依赖网络时序。
"""

from app.api import chat as chat_mod
from app.api.chat import _run_pipeline
from app.schemas import ChatRequest
from app.store import get_or_create_session, get_session


def test_disconnect_right_after_first_event_still_persists_user_message():
    """收到第一个事件就断开 —— 提问必须留下，且不能凭空补一条回答。"""
    gen = _run_pipeline(ChatRequest(message="北京三日游怎么安排"))
    first = next(gen)
    assert first["type"] == "session"
    sid = first["session_id"]

    gen.close()  # 模拟客户端关页

    session = get_session(sid)
    assert session is not None
    assert [m["role"] for m in session["messages"]] == ["user"], (
        "断流后至少要留下用户提问；此时还没有回答，不应凭空补一条 assistant"
    )
    assert session["messages"][0]["content"] == "北京三日游怎么安排"


def test_disconnect_after_answer_keeps_produced_answer():
    """回答已经产出后再断开 —— 用户提问与已产出的回答都要落库。"""
    gen = _run_pipeline(ChatRequest(message="上海周末去哪"))
    sid = None
    answer = None
    for evt in gen:
        if evt["type"] == "session":
            sid = evt["session_id"]
        elif evt["type"] == "answer":
            answer = evt["content"]
            break
    assert sid, "必须下发 session_id"
    assert answer, "mock 流水线应产出回答"

    gen.close()

    session = get_session(sid)
    assert [m["role"] for m in session["messages"]] == ["user", "assistant"]
    assert session["messages"][1]["content"] == answer


def test_normal_completion_persists_both_sides():
    """正常跑完时行为不变（防止 finally 重构把 happy path 弄坏）。"""
    events = list(_run_pipeline(ChatRequest(message="成都三天怎么玩")))
    sid = events[0]["session_id"]
    assert events[-1]["type"] == "done"

    session = get_session(sid)
    assert [m["role"] for m in session["messages"]] == ["user", "assistant"]


def test_user_message_is_persisted_before_pipeline_runs(monkeypatch):
    """进入 pipeline 的那一刻，用户消息必须已经在库里。

    这是「同步调用期间断开」场景的唯一保证：那种断流下 finally 可能不执行，
    所以不能等 pipeline 跑完（或跑到一半）再落库。
    """
    sid = get_or_create_session(None)["id"]
    seen = {}

    class FakeGraph:
        def stream(self, state, stream_mode=None):
            seen["roles"] = [m["role"] for m in get_session(sid)["messages"]]
            return iter([])

    monkeypatch.setattr(chat_mod, "get_graph", lambda: FakeGraph())

    events = list(_run_pipeline(ChatRequest(message="北京三日游怎么安排", session_id=sid)))

    assert seen["roles"] == ["user"], "pipeline 开始时用户消息必须已经落库"
    assert events[-1]["type"] == "done"


def test_persist_failure_aborts_before_pipeline(monkeypatch):
    """用户消息写不进去就直接报错返回，不要继续跑（跑完也存不下来，白烧 token）。"""
    called = {"stream": False}

    class FakeGraph:
        def stream(self, state, stream_mode=None):
            called["stream"] = True
            return iter([])

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(chat_mod, "get_graph", lambda: FakeGraph())
    monkeypatch.setattr(chat_mod, "append_message", boom)

    events = list(_run_pipeline(ChatRequest(message="北京三日游怎么安排")))

    assert events[0]["type"] == "error"
    assert "存储" in events[0]["message"]
    assert called["stream"] is False, "写不进用户消息就不该继续跑 pipeline"
