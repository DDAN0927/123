"""🍜 美食顾问"""

from app.agents.base import run_expert
from app.agents.prompts import FOOD_PROMPT
from app.tools.rag_tool import search_knowledge

NAME = "food"
TITLE = "美食顾问"
ICON = "🍜"
DESCRIPTION = "当地美食、餐厅推荐与特色小吃"
TOOLS = [search_knowledge]


def run(query: str, context: str, outputs: dict, history: list | None = None) -> str:
    return run_expert(NAME, TITLE, FOOD_PROMPT, query, context, outputs, TOOLS, history=history)
