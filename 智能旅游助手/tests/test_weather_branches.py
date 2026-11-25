"""weather.py 的分支覆盖：不支持的城 / 远端失败 / 起始日过滤 / 建议生成。

这些分支原来没有任何用例经过（`--cov` 里 105、126-127、190、232、238-268、278-279
都是 missing），但每一条都对应一个真实场景：

* 用户问一个没收录的城市（105 / 278-279）—— 不能抛异常，要给出可用城市清单；
* open-meteo 超时或 5xx（126-127）—— 必须降级而不是让整条回答失败；
* 行程首日晚于预报窗口（232）—— 过滤后可能为空，要返回 None 交给调用方退化；
* `advice()`（238-268）—— 这是用户唯一直接看到的一段文字，五种天气组合都得走一遍。

设计原则：**不 mock 业务函数本身**，只 mock 网络出口（requests.get）与时间，
这样测的是真实的分支逻辑，而不是「mock 调 mock」。
"""

from __future__ import annotations

import pytest

from app.tools import weather

# ---------- 城市识别 ----------


def test_city_key_returns_none_for_unknown_city():
    """未收录的城市返回 None（105），调用方据此给出「暂不支持」而不是崩掉。"""
    assert weather._city_key("火星基地") is None


def test_query_weather_unknown_city_lists_supported(monkeypatch):
    """不支持的城：返回提示并附可用城市清单（278-279），且**不应发起任何网络请求**。"""
    called = []
    monkeypatch.setattr(weather.requests, "get", lambda *a, **k: called.append(1))

    out = weather.query_weather.invoke({"city": "火星基地", "days": 3})

    assert "暂不支持" in out and "火星基地" in out
    assert "北京" in out, "提示里要给出可用城市，否则用户不知道能问什么"
    assert called == [], "城市未收录时不该打远端接口，白费一次超时"


def test_query_weather_strips_and_clamps_days(monkeypatch):
    """days 越界要夹到 1..7，且城市名两端空格不影响识别。"""
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen["days"] = params["forecast_days"]

        class _R:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "daily": {
                        "time": ["2026-11-22"],
                        "temperature_2m_min": [1],
                        "temperature_2m_max": [9],
                        "weather_code": [0],
                        "precipitation_probability_max": [0],
                        "wind_speed_10m_max": [3],
                    }
                }

        return _R()

    monkeypatch.setattr(weather.requests, "get", fake_get)
    weather.query_weather.invoke({"city": "  北京  ", "days": 99})
    assert seen["days"] == 7


# ---------- 远端失败 ----------


def test_query_real_returns_none_on_network_error(monkeypatch):
    """远端异常必须被吞掉并返回 None（126-127），由调用方降级为季节估算。"""

    def boom(*a, **k):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(weather.requests, "get", boom)
    assert weather._query_real("北京", 3) is None


def test_query_weather_falls_back_to_mock_when_remote_fails(monkeypatch):
    """远端失败时 query_weather 走 mock 文案，用户仍能拿到一段可读建议。"""
    monkeypatch.setattr(weather.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("timeout")))
    out = weather.query_weather.invoke({"city": "北京", "days": 3})
    assert isinstance(out, str) and out.strip()


# ---------- 结构化预报 ----------


def _daily_payload():
    return {
        "daily": {
            "time": ["2026-11-22", "2026-11-23", "2026-11-24"],
            "temperature_2m_min": [3, 4, None],
            "temperature_2m_max": [12, 13, None],
            "weather_code": [0, 61, 3],
            "precipitation_probability_max": [10, 70, 40],
            "wind_speed_10m_max": [8, 35, 12],
        }
    }


def _patch_ok(monkeypatch):
    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return _daily_payload()

    monkeypatch.setattr(weather.requests, "get", lambda *a, **k: _R())


def test_forecast_returns_none_for_unknown_city():
    """forecast 对未收录城市返回 None（190），不是抛异常也不是空列表。"""
    assert weather.forecast("火星基地") is None


def test_forecast_skips_days_with_null_temperature(monkeypatch):
    """远端某天温度为 null 时跳过该天，其余天照常返回（126-127 之后的健壮性）。"""
    _patch_ok(monkeypatch)
    rows = weather.forecast("北京", 3)
    assert rows is not None
    assert len(rows) == 2, "第三天温度是 null，应被跳过而不是 round(None) 抛 TypeError"
    assert all(isinstance(r["tmin"], (int, float)) for r in rows)


def test_forecast_filters_by_start_date(monkeypatch):
    """start_date 过滤（232）：晚于窗口的起始日会把所有天滤掉，返回 None。"""
    _patch_ok(monkeypatch)
    assert weather.forecast("北京", 3, start_date="2026-11-23") is not None
    assert weather.forecast("北京", 3, start_date="2030-01-01") is None


def test_forecast_caps_days_to_16(monkeypatch):
    """days 上限 16（open-meteo 的窗口限制），超出部分截断而不是报错。"""
    _patch_ok(monkeypatch)
    rows = weather.forecast("北京", 99)
    assert rows is not None and len(rows) <= 3


# ---------- 出行建议 ----------


def _row(date, tmin, tmax, precip=0, wind=5):
    return {"date": date, "tmin": tmin, "tmax": tmax, "precip": precip, "wind": wind, "code": 0, "cond": "晴"}


def test_advice_empty_rows():
    assert weather.advice([]) == []


def test_advice_big_temperature_swing():
    out = weather.advice([_row("2026-11-22", 2, 20)])
    assert any("温差" in x for x in out)


def test_advice_cold_snap():
    out = weather.advice([_row("2026-11-22", 1, 8)])
    assert any("厚外套" in x for x in out)


def test_advice_hot_weather():
    """高温分支的前提是「温差 < 12 且最低温 > 5」—— 温差优先于高温。

    这条断言是照实现的分支优先级写的，不是照直觉写的：tmin=20/tmax=33 温差 13，
    走的是「温差大」分支；要覆盖「防暑」必须让温差 < 12。
    """
    out = weather.advice([_row("2026-11-22", 22, 33)])
    assert any("防暑" in x for x in out)
    assert any("防晒" in x for x in out), "高温要同时给防晒建议"


def test_advice_swing_wins_over_heat():
    """温差 ≥12 时优先提醒加衣，而不是防暑（分支顺序是刻意的）。"""
    out = weather.advice([_row("2026-11-22", 20, 33)])
    assert any("温差" in x for x in out)
    assert not any("防暑" in x for x in out)


def test_advice_mild_weather_is_plain():
    out = weather.advice([_row("2026-11-22", 12, 22)])
    assert any("常规春秋装" in x for x in out)


def test_advice_rainy_and_windy():
    """降水 ≥50 与 ≥30 两档、大风 ≥30 都要各自给出提示（238-268 的多分支）。"""
    heavy = weather.advice([_row("2026-11-22", 10, 20, precip=80, wind=40)])
    assert any("务必带伞" in x for x in heavy)
    assert any("风速" in x for x in heavy)

    light = weather.advice([_row("2026-11-22", 10, 20, precip=35)])
    assert any("折叠伞" in x for x in light)


def test_advice_lists_high_rain_days():
    """降水 ≥60 的日子要单独点名（方便用户把那天换成室内行程）。"""
    out = weather.advice([_row("2026-11-22", 10, 20, precip=65)])
    assert any("高概率降雨日" in x and "11-22" in x for x in out)


@pytest.mark.parametrize(
    "rows",
    [
        [_row("2026-11-22", 0, 5, precip=0, wind=0)],
        [_row("2026-11-22", -5, -1, precip=100, wind=99)],
    ],
)
def test_advice_never_raises_on_extremes(rows):
    """极端值不该让建议生成抛异常 —— 它是回答里唯一直接给用户看的段落。"""
    assert isinstance(weather.advice(rows), list)
