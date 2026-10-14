"""天气查询工具：优先调用 open-meteo 真实天气 API（免费无Key），失败时回退演示数据"""
import datetime
import random

import requests
from langchain_core.tools import tool

# 常用城市坐标（纬度, 经度）
_CITY_COORD = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737),
    "成都": (30.5728, 104.0668), "杭州": (30.2741, 120.1551),
    "西安": (34.3416, 108.9398), "重庆": (29.5630, 106.5516),
    "广州": (23.1291, 113.2644), "深圳": (22.5431, 114.0579),
    "三亚": (18.2528, 109.5119), "昆明": (24.8801, 102.8329),
    "南京": (32.0603, 118.7969), "厦门": (24.4798, 118.0894),
    "武汉": (30.5928, 114.3055), "长沙": (28.2282, 112.9388),
    "青岛": (36.0671, 120.3826), "大连": (38.9140, 121.6147),
    "哈尔滨": (45.8038, 126.5350), "拉萨": (29.6520, 91.1721),
    "乌鲁木齐": (43.8256, 87.6168), "桂林": (25.2736, 110.2900),
}

# 各城市气温基线（演示数据用，摄氏度）
# 必须与 _CITY_COORD 一一对应：真实 API 不可用时会走 _query_mock，
# 表里少一个城市就是一次 KeyError（此前只有 12 城，另外 8 城一断网就崩）。
_CITY_TEMP = {
    "北京": (10, 22), "上海": (14, 24), "成都": (15, 23), "杭州": (14, 24),
    "西安": (11, 22), "重庆": (17, 25), "广州": (20, 28), "深圳": (20, 28),
    "三亚": (24, 30), "昆明": (13, 23), "南京": (12, 22), "厦门": (18, 26),
    "武汉": (14, 24), "长沙": (15, 25), "青岛": (12, 20), "大连": (10, 19),
    "哈尔滨": (5, 17), "拉萨": (8, 20), "乌鲁木齐": (9, 21), "桂林": (18, 26),
}
# 兜底基线：万一以后又新增了城市却忘了补表，宁可给个中庸值也别把工具调崩
_DEFAULT_TEMP = (12, 22)

# WMO 天气代码 → (中文描述, 出行建议)
_WMO = {
    0: ("晴", "紫外线较强，注意防晒补水"),
    1: ("大致晴朗", "天气不错，适合户外游览"),
    2: ("多云", "天气舒适，适合户外游览"),
    3: ("阴", "体感凉爽，建议带一件薄外套"),
    45: ("有雾", "能见度较低，出行注意安全"),
    48: ("雾凇", "路面湿滑，注意防滑"),
    51: ("小毛毛雨", "建议携带雨具"),
    53: ("毛毛雨", "建议携带雨具"),
    55: ("大毛毛雨", "建议携带雨具"),
    61: ("小雨", "建议携带雨具，室内景点更合适"),
    63: ("中雨", "建议携带雨具，室内景点更合适"),
    65: ("大雨", "不建议户外行程，可调整为室内景点"),
    66: ("冻雨", "路面结冰，出行注意安全"),
    67: ("强冻雨", "天气恶劣，建议调整行程"),
    71: ("小雪", "注意保暖防滑"),
    73: ("中雪", "注意保暖防滑"),
    75: ("大雪", "天气恶劣，建议调整行程"),
    77: ("雪粒", "注意保暖防滑"),
    80: ("小阵雨", "随身带伞，行程留出弹性"),
    81: ("阵雨", "随身带伞，行程留出弹性"),
    82: ("强阵雨", "尽量安排室内景点"),
    85: ("小阵雪", "注意保暖防滑"),
    86: ("阵雪", "注意保暖防滑"),
    95: ("雷阵雨", "避免户外活动，注意安全"),
    96: ("雷阵雨伴冰雹", "避免户外活动，注意安全"),
    99: ("强雷阵雨伴冰雹", "尽量避免出行"),
}

_WEATHER = ["晴", "多云", "阴", "小雨", "阵雨", "晴转多云", "多云转晴"]
_ADVICE = {
    "晴": "紫外线较强，注意防晒补水",
    "多云": "天气舒适，适合户外游览",
    "阴": "体感凉爽，建议带一件薄外套",
    "小雨": "建议携带雨具，室内景点更合适",
    "阵雨": "随身带伞，行程留出弹性",
}


def _city_key(city: str) -> str | None:
    for c in _CITY_COORD:
        if c in city:
            return c
    return None


def _query_real(key: str, days: int) -> str | None:
    """调用 open-meteo 真实天气 API，失败返回 None"""
    lat, lon = _CITY_COORD[key]
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                         "precipitation_probability_max,wind_speed_10m_max",
                "timezone": "auto", "forecast_days": days,
            },
            timeout=8,
        )
        r.raise_for_status()
        d = r.json()["daily"]
    except Exception:
        return None

    lines = [f"📍 {key} 未来 {days} 天天气预报（open-meteo 实时数据）:"]
    for i, date_str in enumerate(d["time"]):
        code = d["weather_code"][i]
        cond, advice = _WMO.get(code, ("未知天气", ""))
        t_lo = round(d["temperature_2m_min"][i])
        t_hi = round(d["temperature_2m_max"][i])
        wind = round(d["wind_speed_10m_max"][i])
        pop = d["precipitation_probability_max"][i]
        pop_str = f"，降水概率 {pop}%" if pop is not None else ""
        date = datetime.date.fromisoformat(date_str)
        lines.append(
            f"  {date.month}月{date.day}日: {cond}，{t_lo}~{t_hi}℃"
            f"，最大风速 {wind}km/h{pop_str}。{advice}")
    return "\n".join(lines)


def _query_mock(key: str, days: int) -> str:
    """演示数据（确定性模拟，作为真实 API 不可用时的兜底）"""
    today = datetime.date.today()
    lo, hi = _CITY_TEMP.get(key, _DEFAULT_TEMP)
    rng = random.Random(f"{key}-{today.isoformat()}-{days}")
    lines = [f"📍 {key} 未来 {days} 天天气（演示数据）:"]
    for i in range(days):
        d = today + datetime.timedelta(days=i)
        cond = _WEATHER[rng.randrange(len(_WEATHER))]
        t_lo = lo + rng.randint(-3, 2)
        t_hi = hi + rng.randint(-1, 4)
        wind = rng.choice(["微风", "3-4级", "1-2级"])
        advice = _ADVICE.get(cond.split("转")[0], "")
        lines.append(f"  {d.month}月{d.day}日: {cond}, {t_lo}~{t_hi}℃, {wind}。{advice}")
    lines.append("提示: 实时天气服务暂时不可用，以上为演示数据")
    return "\n".join(lines)


@tool
def query_weather(city: str, days: int = 3) -> str:
    """查询指定城市未来几天的天气预报（open-meteo 实时数据）。city: 城市名；days: 查询天数，1-7。"""
    city = city.strip()
    days = max(1, min(int(days), 7))
    key = _city_key(city)
    if key is None:
        supported = "、".join(_CITY_COORD)
        return f"暂不支持「{city}」的天气查询，目前支持：{supported}"

    result = _query_real(key, days)
    if result:
        return result
    return _query_mock(key, days)
