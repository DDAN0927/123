"""旅游智能助手 — FastAPI 入口"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, chat, favorites, knowledge
from app.config import settings
from app.rag import retriever
from app.store import ensure_default_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("travel")


class SafeStaticFiles(StaticFiles):
    """静态文件容错包装。

    Windows 下若请求路径含文件名非法字符（* ? " < > | : 等），
    starlette 内部 os.stat 会抛 OSError(WinError 123)，导致 500 并把
    服务器绝对路径写进日志（可被匿名请求反复触发刷日志）。
    这里统一降级为 404。
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except OSError:
            raise HTTPException(status_code=404, detail="Not Found")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：目录就绪；若索引缺失且知识库有文档，自动构建（首次需下载BGE模型，较慢）
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.kb_dir).mkdir(parents=True, exist_ok=True)
    ensure_default_admin()
    if not retriever.index_ready():
        try:
            from app.rag.indexer import build_index, load_documents
            if load_documents():
                logger.info("未发现知识库索引，开始自动构建（首次需下载 BGE 模型，请耐心等待）...")
                stats = build_index()
                logger.info(f"知识库索引构建完成: {stats}")
        except Exception as e:
            logger.warning(f"索引自动构建失败（可稍后运行 python scripts/build_kb.py）: {e}")
    yield


app = FastAPI(title="旅游智能助手 Travel Copilot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底异常处理：返回结构化 JSON，不把堆栈与内部路径暴露给客户端"""
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(knowledge.router)
app.include_router(favorites.router)
app.include_router(auth.router)


@app.get("/health")
def health():
    """健康检查与系统状态"""
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "index_ready": retriever.index_ready(),
    }


# 品牌官网（静态站点）托管于根路径；API 路由与 /health 优先级更高
_static_dir = Path(__file__).resolve().parent.parent / "frontend" / "static"
if _static_dir.is_dir():
    app.mount("/", SafeStaticFiles(directory=str(_static_dir), html=True), name="site")

