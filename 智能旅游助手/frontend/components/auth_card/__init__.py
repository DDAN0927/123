"""登录 / 注册卡片组件（仿「扇贝」风格：左侧插画 + 右侧表单）

提交时通过 setComponentValue 回传表单数据，流式后端逻辑在 Python 侧（服务端
调用 FastAPI），避免浏览器跨域直连后端：
返回 {"mode": "login"|"register", "username", "password", "password2"} 或 None。
"""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component("auth_card_v1", path=str(Path(__file__).parent))


def auth_card(error: str = "", key: str = "auth_card", height: int = 640):
    return _component(error=error, key=key, default=None, height=height)