"""💬 旅行咨询师"""

from app.agents.base import run_expert
from app.agents.prompts import CONSULTANT_PROMPT
from app.tools.rag_tool import search_knowledge

NAME = "consultant"
TITLE = "旅行咨询师"
ICON = "💬"
DESCRIPTION = "证件签证、交通住宿、装备与安全咨询"
TOOLS = [search_knowledge]


def run(query: str, context: str, outputs: dict, history: list | None = None) -> str:
    return run_expert(NAME, TITLE, CONSULTANT_PROMPT, query, context, outputs, TOOLS, history=history)
