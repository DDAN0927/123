"""🏛️ 景点顾问"""

from app.agents.base import run_expert
from app.agents.prompts import ATTRACTIONS_PROMPT
from app.tools.rag_tool import search_knowledge
from app.tools.weather import query_weather

NAME = "attractions"
TITLE = "景点顾问"
ICON = "🏛️"
DESCRIPTION = "景点介绍、门票、开放时间与玩法推荐"
TOOLS = [search_knowledge, query_weather]


def run(query: str, context: str, outputs: dict, history: list | None = None) -> str:
    return run_expert(NAME, TITLE, ATTRACTIONS_PROMPT, query, context, outputs, TOOLS, history=history)
