"""专家团队注册表"""
from app.agents import analyst, attractions, consultant, food, planner

EXPERTS = {m.NAME: m for m in (planner, attractions, food, analyst, consultant)}
