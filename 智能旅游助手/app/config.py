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
    # 相关度下限：低于此值的块直接丢弃。
    # 实测噪声查询（「你好」「帮我订个机票」）最高分在 0.40~0.51，
    # 而真实查询普遍在 0.68 以上，0.55 是能干净分开两者的分界。
    retrieval_min_score: float = 0.55

    # ===== Agent =====
    max_agent_steps: int = 4  # 单次提问最多路由的专家次数

    # ===== LLM 成本估算 =====
    # 单价（元 / 百万 tokens），仅用于运营看板的量级估算，请以服务商当期价目为准。
    # 双模型架构下两档单价差 2~4 倍：路由与工具调用走 deepseek-chat，
    # 专家与汇总走 deepseek-reasoner。用一个统一价会把路由调用按推理模型计价，
    # 运营看板上的成本会明显偏高 —— 所以按模型分开估。
    llm_price_input_per_mtok: float = 4.0  # reasoner 输入
    llm_price_output_per_mtok: float = 16.0  # reasoner 输出
    llm_price_chat_input_per_mtok: float = 2.0  # chat 输入
    llm_price_chat_output_per_mtok: float = 8.0  # chat 输出

    # ===== 认证 =====
    admin_username: str = "admin"
    admin_password: str = "admin123"
    # 登录态有效期（秒）。默认 7 天；过期后需重新登录。
    # 早期实现里 token 是「永久有效」的 —— 泄露后无法自行失效，属于真实安全问题。
    token_ttl_seconds: int = 7 * 24 * 3600
    # 公网部署默认关闭开放注册：新账号由管理员在「管理后台」创建，
    # 否则任何人都能注册账号白嫖真实的 LLM 额度。本地开发可设为 true。
    allow_registration: bool = False

    # ===== 限流（保护已公开部署的 LLM 额度）=====
    rate_limit_enabled: bool = True
    rate_limit_anonymous_per_minute: int = 2  # 匿名访客：每个 IP 每分钟
    rate_limit_per_minute: int = 6  # 登录用户：每个 IP 每分钟
    rate_limit_global_per_minute: int = 20  # 全局硬上限（伪造 XFF 也绕不过）
    auth_rate_limit_per_minute: int = 10  # 登录/注册：每个 IP 每分钟
    trust_proxy_headers: bool = True  # 反代后从 X-Forwarded-For 取真实 IP

    # ===== 高德地图（Web 端 JS API）=====
    # 这两个值**本来就会发送到浏览器**（JS API 2.0 要求在建图前把 jscode 注入
    # window._AMapSecurityConfig），所以它们不是传统意义的服务端密钥，
    # 真正的访问控制靠高德控制台的「域名白名单」。
    # 这里仍然做成可配置：自部署者应该换成自己的 Key，别蹭项目的额度。
    # 前端通过 GET /api/config 读取，源码里不再硬编码。
    amap_key: str = "88db79732b445f23505ffa0e5acba520"
    amap_security_js_code: str = "9b91cb0707f38ec51dedd85a0a982fe3"

    @property
    def is_mock(self) -> bool:
        return self.llm_provider.lower() == "mock"

    @property
    def index_dir(self) -> Path:
        return Path(self.data_dir) / "index"


settings = Settings()
