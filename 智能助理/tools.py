# -*- coding: utf-8 -*-
from langchain.tools import tool
import requests
import os
from datetime import datetime, timedelta
import json
from urllib.parse import quote

@tool
def search_web(query: str) -> str:
    """当需要实时信息或你不知道答案时，用此工具搜索互联网。"""
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    if not serpapi_key:
        return "搜索功能暂不可用：未配置 SERPAPI_API_KEY。"
    try:
        url = "https://serpapi.com/search"
        params = {"q": query, "api_key": serpapi_key}
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        snippets = [r["snippet"] for r in data.get("organic_results", [])[:3]]
        return "\n".join(snippets) if snippets else "未找到结果"
    except requests.RequestException:
        return "搜索请求失败，请稍后重试。"
    except (KeyError, ValueError):
        return "搜索结果解析失败，请稍后重试。"

@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气情况。"""
    try:
        encoded_city = quote(city)
        url = f"https://wttr.in/{encoded_city}?format=j1"
        res = requests.get(url, timeout=10, headers={"Accept-Language": "zh-CN,zh;q=0.9"})
        res.raise_for_status()
        data = res.json()
        current = data["current_condition"][0]
        temp = current["temp_C"]
        feels_like = current["FeelsLikeC"]
        humidity = current["humidity"]
        desc = current["weatherDesc"][0]["value"]
        wind_speed = current["windspeedKmph"]
        wind_dir = current["winddir16Point"]
        return (
            f"{city} 当前天气：{desc}，"
            f"气温 {temp}°C（体感 {feels_like}°C），"
            f"湿度 {humidity}%，"
            f"风速 {wind_speed}km/h，风向 {wind_dir}。"
        )
    except requests.RequestException:
        return f"抱歉，无法获取 {city} 的天气信息，请稍后重试。"
    except (KeyError, IndexError):
        return f"抱歉，{city} 的天气数据格式异常，请稍后重试。"

@tool
def get_current_time() -> str:
    """获取当前日期和时间。"""
    now = datetime.now()
    return f"当前时间是：{now.strftime('%Y年%m月%d日 %H:%M:%S')}，星期{['一', '二', '三', '四', '五', '六', '日'][now.weekday()]}。"

@tool
def calculate(expression: str) -> str:
    """进行数学计算。支持加减乘除等基本运算。"""
    try:
        # 安全的表达式计算
        allowed_chars = set('0123456789+-*/(). ')
        if not all(c in allowed_chars for c in expression):
            return "表达式包含不允许的字符，仅支持数字和 +-*/() 运算符。"
        result = eval(expression, {"__builtins__": None}, {})
        return f"计算结果：{result}"
    except Exception as e:
        return f"计算错误：{str(e)}"

@tool
def write_note(content: str, filename: str = "notes.txt") -> str:
    """保存笔记到本地文件。"""
    try:
        mode = 'a' if os.path.exists(filename) else 'w'
        with open(filename, mode, encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{timestamp}]\n{content}\n")
        return f"笔记已保存到 {filename}"
    except Exception as e:
        return f"保存笔记失败：{str(e)}"

@tool
def read_note(filename: str = "notes.txt") -> str:
    """读取本地保存的笔记。"""
    try:
        if not os.path.exists(filename):
            return f"文件 {filename} 不存在。"
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"笔记内容：\n{content}"
    except Exception as e:
        return f"读取笔记失败：{str(e)}"

@tool
def add_reminder(title: str, minutes: int = 0, hours: int = 0, days: int = 0) -> str:
    """添加提醒事项。"""
    try:
        reminder_time = datetime.now() + timedelta(days=days, hours=hours, minutes=minutes)
        reminder_file = "reminders.json"
        
        reminders = []
        if os.path.exists(reminder_file):
            with open(reminder_file, 'r', encoding='utf-8') as f:
                reminders = json.load(f)
        
        reminders.append({
            "title": title,
            "created_at": datetime.now().isoformat(),
            "remind_at": reminder_time.isoformat()
        })
        
        with open(reminder_file, 'w', encoding='utf-8') as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
        
        return f"已添加提醒：{title}，将于 {reminder_time.strftime('%Y-%m-%d %H:%M')} 提醒。"
    except Exception as e:
        return f"添加提醒失败：{str(e)}"

@tool
def list_reminders() -> str:
    """列出所有待办提醒。"""
    try:
        reminder_file = "reminders.json"
        if not os.path.exists(reminder_file):
            return "暂无提醒。"
        
        with open(reminder_file, 'r', encoding='utf-8') as f:
            reminders = json.load(f)
        
        if not reminders:
            return "暂无提醒。"
        
        result = "当前提醒列表：\n"
        for i, r in enumerate(reminders, 1):
            remind_at = datetime.fromisoformat(r["remind_at"])
            result += f"{i}. {r['title']} - {remind_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        return result
    except Exception as e:
        return f"获取提醒列表失败：{str(e)}"
