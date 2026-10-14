"""📊 数据分析师"""
from app.agents.base import run_expert
from app.agents.prompts import ANALYST_PROMPT
from app.tools.budget import estimate_budget
from app.tools.rag_tool import search_knowledge
from app.tools.weather import query_weather

NAME = "analyst"
TITLE = "数据分析师"
ICON = "📊"
DESCRIPTION = "天气分析、预算估算与出行决策支持"
TOOLS = [query_weather, estimate_budget, search_knowledge]


def run(query: str, context: str, outputs: dict) -> str:
    return run_expert(NAME, TITLE, ANALYST_PROMPT, query, context, outputs, TOOLS)
