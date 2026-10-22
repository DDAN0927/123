"""纯函数工具：预算估算。

这类「输入 → 输出」确定性逻辑最适合用单测锁死，
不依赖网络、不依赖模型，跑得还快。
"""

import pytest

from app.tools.budget import _BASE_COST, _INTERCITY, estimate_budget


def _run(city: str, days: int, style: str = "舒适") -> str:
    """@tool 包装后需要走 invoke，不能直接调用。"""
    return estimate_budget.invoke({"city": city, "days": days, "style": style})


def test_unsupported_city_lists_supported_ones():
    out = _run("拉萨", 3)
    assert "暂不支持" in out
    for city in _BASE_COST:
        assert city in out


def test_supported_city_mentions_city_and_days():
    out = _run("北京", 3)
    assert "北京" in out
    assert "3 天" in out


def test_total_equals_sum_of_daily_items_plus_intercity():
    days = 4
    style = "舒适"
    out = _run("成都", days, style)

    expected = sum(_BASE_COST["成都"][style]) * days + _INTERCITY[style]
    assert f"¥{expected:,}/人" in out


def test_each_style_produces_increasing_total():
    """豪华 > 舒适 > 经济 —— 防止配置表写反。"""
    totals = {}
    for style in ("经济", "舒适", "豪华"):
        out = _run("上海", 2, style)
        line = next(line for line in out.splitlines() if "总计" in line)
        totals[style] = int(line.split("¥")[1].split("/人")[0].replace(",", ""))

    assert totals["经济"] < totals["舒适"] < totals["豪华"]


def test_unknown_style_falls_back_to_comfort():
    out = _run("西安", 2, "超级豪华")
    assert "舒适型" in out


def test_days_are_clamped_to_1_and_30():
    assert "1 天" in _run("北京", 0)
    assert "1 天" in _run("北京", -5)
    assert "30 天" in _run("北京", 999)


def test_city_matched_by_substring():
    """「北京市」应命中「北京」的配置。"""
    assert "北京" in _run("北京市", 2)


def test_intercity_cost_is_included_for_every_style():
    for style in _INTERCITY:
        out = _run("重庆", 2, style)
        assert f"¥{_INTERCITY[style]:,}" in out


@pytest.mark.parametrize("city", list(_BASE_COST))
def test_every_configured_city_renders(city):
    out = _run(city, 2)
    assert "总计" in out
    assert "暂不支持" not in out
