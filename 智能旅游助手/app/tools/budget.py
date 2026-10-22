"""旅行预算估算工具：基于城市消费水平估算每日开销与总预算"""

from langchain_core.tools import tool

# 每日人均消费（元/人/天）: {城市: {档次: [住宿, 餐饮, 市内交通, 门票娱乐, 杂项]}}
_BASE_COST = {
    "北京": {
        "经济": [160, 80, 30, 40, 30],
        "舒适": [380, 150, 60, 100, 60],
        "豪华": [900, 400, 150, 250, 150],
    },
    "上海": {
        "经济": [170, 85, 35, 40, 30],
        "舒适": [400, 160, 60, 100, 60],
        "豪华": [950, 420, 150, 260, 160],
    },
    "成都": {
        "经济": [130, 70, 25, 30, 25],
        "舒适": [300, 130, 50, 80, 50],
        "豪华": [800, 350, 120, 220, 130],
    },
    "杭州": {
        "经济": [150, 75, 30, 35, 25],
        "舒适": [350, 140, 50, 90, 50],
        "豪华": [850, 380, 130, 240, 150],
    },
    "西安": {
        "经济": [120, 65, 25, 30, 25],
        "舒适": [280, 120, 45, 80, 50],
        "豪华": [750, 340, 110, 210, 130],
    },
    "重庆": {
        "经济": [125, 70, 25, 30, 25],
        "舒适": [290, 125, 45, 80, 50],
        "豪华": [780, 350, 120, 220, 130],
    },
}
_STYLE_DESC = {
    "经济": "青旅/经济连锁酒店 + 本地小馆 + 公共交通",
    "舒适": "三四星/精品酒店 + 特色餐厅 + 打车地铁结合",
    "豪华": "五星/奢华酒店 + 高档餐厅 + 包车出行",
}
_INTERCITY = {"经济": 800, "舒适": 1500, "豪华": 3000}  # 往返大交通估算（元/人）


@tool
def estimate_budget(city: str, days: int, style: str = "舒适") -> str:
    """估算旅行总预算。city: 城市名；days: 旅行天数；style: 消费档次，可选 经济/舒适/豪华。"""
    key = next((c for c in _BASE_COST if c in city), None)
    if key is None:
        return f"暂不支持「{city}」的预算估算，目前支持：{'、'.join(_BASE_COST)}"

    style = style if style in _BASE_COST[key] else "舒适"
    d = max(1, min(int(days), 30))
    costs = _BASE_COST[key][style]
    items = ["住宿", "餐饮", "市内交通", "门票娱乐", "杂项"]

    lines = [
        f"💰 {key} {d} 天旅行预算估算（{style}型: {_STYLE_DESC[style]}）",
        "",
        "| 项目 | 每日/人 | 小计/人 |",
        "| --- | --- | --- |",
    ]
    total = 0
    for name, per_day in zip(items, costs, strict=True):
        subtotal = per_day * d
        total += subtotal
        lines.append(f"| {name} | ¥{per_day} | ¥{subtotal:,} |")
    intercity = _INTERCITY[style]
    total += intercity
    lines.append(f"| 往返大交通 | — | ¥{intercity:,}（估算） |")
    lines += [
        "",
        f"**总计（不含购物）: 约 ¥{total:,}/人**",
        "提示: 节假日价格上浮 30%-100%，建议提前 1 个月预订机票酒店。",
    ]
    return "\n".join(lines)
