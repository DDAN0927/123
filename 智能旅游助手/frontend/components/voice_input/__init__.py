"""语音输入组件：浏览器 Web Speech API 中文语音识别（双向 Streamlit 组件）"""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component("voice_input", path=str(Path(__file__).parent))


def voice_input(key: str = None, height: int = 52):
    """返回 {"text": "识别结果"} 或 None"""
    return _component(key=key, height=height, default=None)
