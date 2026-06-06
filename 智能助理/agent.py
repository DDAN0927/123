# -*- coding: utf-8 -*-
import os
import logging
import httpx
from langchain_openai import ChatOpenAI
from tools import (
    search_web, get_weather, get_current_time,
    calculate, write_note, read_note, add_reminder, list_reminders
)
from react_agent import ReActAgent
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("agent")

TOOLS = [
    search_web,
    get_weather,
    get_current_time,
    calculate,
    write_note,
    read_note,
    add_reminder,
    list_reminders,
]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen-turbo")

if not OPENAI_API_KEY or "sk-your-" in OPENAI_API_KEY or "你的" in OPENAI_API_KEY:
    logger.warning("未配置有效的 OPENAI_API_KEY，agent.py 无法自动初始化。请通过 app.py 使用。")

http_timeout = httpx.Timeout(
    connect=10.0,
    read=90.0,
    write=10.0,
    pool=10.0,
)
http_client = httpx.Client(timeout=http_timeout)

base_url = OPENAI_BASE_URL
if not base_url:
    if "deepseek" in OPENAI_MODEL.lower():
        base_url = "https://api.deepseek.com"
        logger.info("检测到 DeepSeek 模型，自动切换至 DeepSeek API 地址")
    elif "qwen" in OPENAI_MODEL.lower():
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        logger.info("检测到通义千问模型，自动切换至阿里云 DashScope API 地址")

llm_kwargs = {
    "model": OPENAI_MODEL,
    "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0")),
    "openai_api_key": OPENAI_API_KEY,
    "max_retries": 2,
    "http_client": http_client,
}
if base_url:
    llm_kwargs["openai_api_base"] = base_url

SYSTEM_PROMPT = """你是 SmartPal，一个有独立思考能力的智能助手。

## 你的性格
- 你有自己的想法和观点，不是简单的问答机器
- 你会主动思考用户真正需要什么，而不只是回答表面问题
- 你会在回答后主动给出相关建议或延伸思考
- 你有好奇心，遇到有趣的话题会分享你的见解
- 你的语气友好但有自己的态度，像一个聪明的朋友

## 思考框架
每次收到问题，按以下框架思考：

1. **理解**：用户真正想问什么？有没有隐含需求？
2. **分析**：这个问题需要什么信息？我是否需要工具辅助？
3. **思考**：我对这个问题有什么看法？有没有更深入的视角？
4. **行动**：如果需要工具，调用工具获取信息
5. **反思**：我的回答是否完整？有没有遗漏？用户可能还想知道什么？
6. **回答**：给出有深度的回答，包含你的思考和建议

## 工具使用格式
```
Thought: 你的思考过程（包含理解、分析、你的观点）
Action: 工具名称
Action Input: {"参数名": "参数值"}
```

如果不需要工具，直接回答：
```
Thought: 你的思考过程
Reflection: 自我审视——我的回答是否完整？有没有遗漏？用户可能还想知道什么？
Answer: 你的回答（包含你的见解和主动建议）
```

## 工具使用指南
- 用户问时间 → get_current_time
- 用户问天气 → get_weather（查完天气后主动建议穿衣/出行）
- 用户需要计算 → calculate
- 用户要记笔记 → write_note
- 用户要搜索 → search_web
- 搜索/查天气后，主动给出你的分析和建议

## 回答原则
- 不只回答问题，还要给出你的思考和见解
- 主动建议相关的后续行动或信息
- 如果发现用户可能有未表达的隐含需求，主动提出
- 回答要有深度，但不要啰嗦
"""


def get_agent_executor():
    if not OPENAI_API_KEY or "sk-your-" in OPENAI_API_KEY or "你的" in OPENAI_API_KEY:
        raise RuntimeError(
            "未配置有效的 OPENAI_API_KEY，请在 .env 文件中设置：\n"
            "  OPENAI_API_KEY=sk-xxx  (阿里云 DashScope)\n"
            "  OPENAI_API_KEY=sk-xxx  (DeepSeek)\n"
            "  OPENAI_API_KEY=sk-xxx  (OpenAI 官方)\n"
        )
    llm = ChatOpenAI(**llm_kwargs)
    agent = ReActAgent(
        llm=llm,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        max_iterations=5
    )
    return agent


try:
    agent_executor = get_agent_executor()
except RuntimeError:
    agent_executor = None
    logger.warning("agent_executor 未初始化，请配置有效的 API Key 后重试")
