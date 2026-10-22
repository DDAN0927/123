"""旅游智能助手 — FastAPI 入口"""

import importlib.util
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, chat, favorites, knowledge, notes
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
            # 静态文件不存在时统一回 404；不需要把底层 OSError 链暴露给客户端
            raise HTTPException(status_code=404, detail="Not Found") from None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：目录就绪；若索引缺失且知识库有文档，自动构建（首次需下载BGE模型，较慢）
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.kb_dir).mkdir(parents=True, exist_ok=True)

    # SQLite 就绪 + 旧 JSON/JSONL 数据一次性迁移（幂等）
    from app import db

    migrated = db.init()
    if migrated.get("migrated"):
        logger.info(
            "SQLite 已就绪，旧数据迁移完成：用户 %s / 收藏 %s / 会话 %s / 消息 %s",
            migrated.get("users"),
            migrated.get("favorites"),
            migrated.get("sessions"),
            migrated.get("messages"),
        )
    logger.info("数据库文件：%s", db.db_path())

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

    # 后台预热检索链路（加载 FAISS + BGE 模型 + 跑一次编码）。
    # 不预热的话，第一个真实用户要独自承担 3~10s 的模型加载开销。
    if retriever.index_ready():
        threading.Thread(target=retriever.warmup, name="rag-warmup", daemon=True).start()

    yield


app = FastAPI(title="旅游智能助手 Travel Copilot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(notes.router)
app.include_router(auth.router)


@app.get("/health")
def health():
    """健康检查与系统状态。

    `index_ready` 只说明索引文件在；`rag_ready` 才说明模型与索引真的加载成功过。
    两者分开是因为重型依赖是延迟导入的：容器里 torch 装失败时进程照样起得来，
    只看 index_ready 会得出「一切正常」的错误结论（实际每次检索都在抛异常）。
    `rag_deps` 进一步指出到底是哪个包没装上，省得靠猜。
    """
    payload = {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "index_ready": retriever.index_ready(),
        "rag_ready": retriever.ready(),
        "rag_state": retriever.state(),
        "rag_error": retriever.last_error(),
        "rag_deps": {
            name: _has_module(name) for name in ("faiss", "torch", "transformers", "sentence_transformers")
        },
    }
    # 只在坏了的时候才真 import 一遍，把根因挖出来（正常路径不付这个代价）
    if payload["rag_state"] == "failed":
        payload["rag_imports"] = retriever.probe_imports()
    return payload


def _has_module(name: str) -> bool:
    """包是否可被导入（只查元数据，不真的 import，避免拖慢健康检查）。"""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


@app.get("/api/config")
def public_config():
    """前端运行时配置（无需登录）。

    只放**本来就要下发到浏览器**的公开值：高德 JS API 的 key 与安全密钥
    是必须暴露给客户端的（JS API 2.0 强制要求），真正的访问控制靠高德控制台的
    域名白名单。把它放在这里而不是写死在前端源码里，是为了让自部署者
    能用自己的 Key 覆盖，而不是共用项目的额度。
    """
    return {
        "amap_key": settings.amap_key,
        "amap_security_js_code": settings.amap_security_js_code,
    }


# 品牌官网（静态站点）托管于根路径；API 路由与 /health 优先级更高
_static_dir = Path(__file__).resolve().parent.parent / "frontend" / "static"
if _static_dir.is_dir():
    app.mount("/", SafeStaticFiles(directory=str(_static_dir), html=True), name="site")
