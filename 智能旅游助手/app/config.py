"""全局配置：从 .env 加载，支持环境变量覆盖"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# HuggingFace 模型下载默认走国内镜像（已设置 HF_ENDPOINT 环境变量时不覆盖）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 若项目内置了向量模型缓存（发布包会把 BGE 模型一并打包），则离线使用它，
# 避免运行时下载模型导致的首次查询超时。
_LOCAL_HF_CACHE = BASE_DIR / "hf_cache"
if (_LOCAL_HF_CACHE / "hub").is_dir():
    os.environ.setdefault("HF_HOME", str(_LOCAL_HF_CACHE))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ===== LLM =====
    # deepseek: DeepSeek 官方 API（reasoner 深度思考 + chat 快速路由）
    # openai: 任意 OpenAI 兼容接口（vLLM/智谱 等）；mock: 无模型演示模式
    llm_provider: str = "openai"
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_temperature: float = 0.7
    # 快速模型：调度路由 / 工具调用（思考模型不支持 function calling，需单独配置）
    llm_router_model: str = ""

    # ===== Embedding / RAG =====
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    kb_dir: str = str(BASE_DIR / "knowledge_base")
    data_dir: str = str(BASE_DIR / "data")
    chunk_size: int = 500
    chunk_overlap: int = 80
    retrieval_top_k: int = 4

    # ===== Agent =====
    max_agent_steps: int = 4  # 单次提问最多路由的专家次数

    # ===== 认证 =====
    admin_username: str = "admin"
    admin_password: str = "admin123"
    # 公网部署默认关闭开放注册：新账号由管理员在「管理后台」创建，
    # 否则任何人都能注册账号白嫖真实的 LLM 额度。本地开发可设为 true。
    allow_registration: bool = False

    # ===== 限流（保护已公开部署的 LLM 额度）=====
    rate_limit_enabled: bool = True
    rate_limit_anonymous_per_minute: int = 2   # 匿名访客：每个 IP 每分钟
    rate_limit_per_minute: int = 6             # 登录用户：每个 IP 每分钟
    rate_limit_global_per_minute: int = 20     # 全局硬上限（伪造 XFF 也绕不过）
    auth_rate_limit_per_minute: int = 10       # 登录/注册：每个 IP 每分钟
    trust_proxy_headers: bool = True           # 反代后从 X-Forwarded-For 取真实 IP

    @property
    def is_mock(self) -> bool:
        return self.llm_provider.lower() == "mock"

    @property
    def index_dir(self) -> Path:
        return Path(self.data_dir) / "index"


settings = Settings()
