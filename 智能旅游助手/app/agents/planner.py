"""🗓️ 行程规划师"""

from app.agents.base import run_expert
from app.agents.prompts import PLANNER_PROMPT

NAME = "planner"
TITLE = "行程规划师"
ICON = "🗓️"
DESCRIPTION = "制定多日行程、路线安排与时间规划"
TOOLS = []


def run(query: str, context: str, outputs: dict, history: list | None = None) -> str:
    return run_expert(NAME, TITLE, PLANNER_PROMPT, query, context, outputs, history=history)
