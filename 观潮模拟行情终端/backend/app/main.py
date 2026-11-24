"""观潮·模拟行情终端 —— 后端入口。

定位（必须与前端文案一致，不可漂移）：
**本服务提供的是本地确定性模拟序列，不是真实行情。** /api/health 里逐项声明了
`data_is_simulated: true`。接真实行情时应新增 provider 实现并同步更新前端所有
"模拟数据"标注，而不是悄悄换数据源。

启动（项目根目录）:
    python -m uvicorn backend.app.main:app --reload --port 8000
    打开 http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .routers import health, market
from .version import APP_VERSION

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "index.html"

OPENAPI_TAGS = [
    {"name": "健康检查", "description": "服务可用性、provider 与标的注册表状态"},
    {"name": "行情", "description": "标的清单、快照、K 线（日/周/月聚合）。数据为本地模拟序列"},
]

app = FastAPI(
    title="观潮·模拟行情终端 API",
    description=(
        "单文件前端（index.html）的后端服务。\n\n"
        "**数据声明**：全部行情为本地确定性模拟序列，非真实市场数据，不构成投资建议。\n\n"
        "已完成：标的清单 / 快照 / K线（日周月聚合 + MA）。"
        "规划中：组合、纪律复盘、分散度、大盘温度计。"
    ),
    version=APP_VERSION,
    openapi_tags=OPENAPI_TAGS,
)

# 开发期放开：前端可能以 file:// 打开（Origin 为 null）或走本地静态服务。
# 生产部署时应改为具体来源白名单，不要长期保留通配。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(market.router)


@app.get("/", include_in_schema=False)
def root():
    """同源提供前端单文件，避免部署时前后端跨域。"""
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html")
    return JSONResponse(
        {"detail": "未找到 index.html，请从项目根目录启动，或直接访问 /docs"},
        status_code=404,
    )
