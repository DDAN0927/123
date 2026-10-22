"""限流：滑动窗口计数器的行为。

限流是本项目保护真实 LLM 额度的关键防线（公网部署时匿名访客每分钟只有 2 次），
所以它必须真的能拦住，而不是「看起来有」。
"""

import time

from app.ratelimit import SlidingWindow


def test_allows_up_to_limit_then_blocks():
    w = SlidingWindow(limit=3, window=60)
    assert [w.hit("ip-1")[0] for _ in range(3)] == [True, True, True]

    allowed, retry = w.hit("ip-1")
    assert allowed is False
    assert retry >= 1


def test_keys_are_isolated():
    w = SlidingWindow(limit=1, window=60)
    assert w.hit("ip-a")[0] is True
    assert w.hit("ip-a")[0] is False
    # 另一个 key 不受影响
    assert w.hit("ip-b")[0] is True


def test_limit_zero_means_unlimited():
    w = SlidingWindow(limit=0, window=60)
    assert all(w.hit("ip")[0] for _ in range(100))


def test_window_expiry_releases_quota():
    """窗口滑过之后应重新放行（用极短窗口，避免测试变慢）。"""
    w = SlidingWindow(limit=1, window=0.05)
    assert w.hit("ip")[0] is True
    assert w.hit("ip")[0] is False

    time.sleep(0.08)
    assert w.hit("ip")[0] is True


def test_reset_clears_all_state():
    w = SlidingWindow(limit=1, window=60)
    assert w.hit("ip")[0] is True
    assert w.hit("ip")[0] is False

    w.reset()
    assert w.hit("ip")[0] is True


def test_retry_after_is_within_window():
    w = SlidingWindow(limit=1, window=60)
    w.hit("ip")
    allowed, retry = w.hit("ip")
    assert allowed is False
    assert 1 <= retry <= 61
