"""功能宫格/导航条组件：彩色可点击卡片，点击返回目标页 key（双向 Streamlit 组件）

layout="grid"：主页大卡片宫格；layout="bar"：每页顶部紧凑导航条（current 高亮当前页）
"""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component("feature_cards_v6", path=str(Path(__file__).parent))


def feature_cards(cards: list, key: str = None, height: int = 180,
                  layout: str = "grid", current: str = ""):
    """cards: [{"key","icon","title","desc","color"}]；返回 {"page": key} 或 None"""
    return _component(cards=cards, key=key, default=None, height=height,
                      layout=layout, current=current)
