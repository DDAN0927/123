"""天气工具对远端脏数据的容错（回归 #7）。

open-meteo 在「超出预报范围」或「该天数据缺失」时会给 `null`。
早期 `_query_real()` 只把 `requests.get` 包进 try，取值循环里直接
`round(d["temperature_2m_min"][i])` → `TypeError`，异常逃出工具函数，
analyst 专家整条失败，用户少一整块回答。

`forecast()` 早就用 `_at()` + `continue` 修好了，`_query_real()` 是漏修的那一条。
这组用例把两条路径都钉住，避免下次又只修一条。
"""

import app.tools.weather as weather


class _Resp:
    """最小 requests.Response 替身：只要 raise_for_status / json 两个方法。"""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _stub(monkeypatch, payload: dict) -> None:
    """让 open-meteo 返回给定 payload（conftest 的断网夹具会被这里覆盖）。"""
    monkeypatch.setattr(weather.requests, "get", lambda *a, **k: _Resp(payload))


def test_query_real_skips_null_temperature(monkeypatch):
    """某天温度为 null → 跳过该天，其余天照常输出，不抛异常。"""
    _stub(
        monkeypatch,
        {
            "daily": {
                "time": ["2026-11-21", "2026-11-22"],
                "weather_code": [0, 61],
                "temperature_2m_min": [None, 8],
                "temperature_2m_max": [None, 15],
                "precipitation_probability_max": [None, 70],
                "wind_speed_10m_max": [None, 12],
            }
        },
    )

    text = weather.query_weather.invoke({"city": "北京", "days": 2})

    assert "11月22日" in text, "有数据的那天必须照常输出"
    assert "11月21日" not in text, "null 温度的那天应被跳过"
    assert "0~0℃" not in text, "null 不能被渲染成 0℃（会得出「需要羽绒」的错误建议）"


def test_query_real_survives_missing_fields(monkeypatch):
    """weather_code / 风速 / 降水概率整列缺失 → 不抛 KeyError。"""
    _stub(
        monkeypatch,
        {
            "daily": {
                "time": ["2026-11-21"],
                "temperature_2m_min": [5],
                "temperature_2m_max": [12],
            }
        },
    )

    text = weather.query_weather.invoke({"city": "北京", "days": 1})

    assert "11月21日" in text
    assert "未知天气" in text, "缺 weather_code 时应降级为「未知天气」而不是崩"
    assert "5~12℃" in text


def test_query_real_falls_back_when_all_days_null(monkeypatch):
    """所有天都取不到 → 交给演示数据兜底，而不是只回一个标题。"""
    _stub(
        monkeypatch,
        {
            "daily": {
                "time": ["2026-11-21"],
                "weather_code": [None],
                "temperature_2m_min": [None],
                "temperature_2m_max": [None],
                "precipitation_probability_max": [None],
                "wind_speed_10m_max": [None],
            }
        },
    )

    text = weather.query_weather.invoke({"city": "北京", "days": 1})

    assert "演示数据" in text


def test_forecast_skips_null_temperature(monkeypatch):
    """同一条不变式在结构化预报上也要成立（防止只修一条路径的历史重演）。"""
    _stub(
        monkeypatch,
        {
            "daily": {
                "time": ["2026-11-21", "2026-11-22"],
                "weather_code": [0, 61],
                "temperature_2m_min": [None, 8],
                "temperature_2m_max": [None, 15],
                "precipitation_probability_max": [None, 70],
                "wind_speed_10m_max": [None, 12],
            }
        },
    )

    rows = weather.forecast("北京", days=2)

    assert rows is not None
    assert [r["date"] for r in rows] == ["2026-11-22"]
    assert (rows[0]["tmin"], rows[0]["tmax"]) == (8, 15)
