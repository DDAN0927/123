"""API 数据模型（Pydantic Schema）"""
from pydantic import BaseModel, Field


# ---------- 对话 ----------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: str | None = Field(None, description="会话ID，为空则新建会话")


class TraceItem(BaseModel):
    agent: str
    reason: str = ""


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    trace: list[TraceItem] = []
    outputs: dict[str, str] = {}
    agent_calls: int = 0
    elapsed_ms: int = 0


class FeedbackRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    message_index: int = Field(..., ge=0, description="助手消息在会话中的序号")
    rating: str = Field(..., pattern="^(like|dislike)$", description="评价：like / dislike")


class MessageItem(BaseModel):
    role: str
    content: str
    ts: float = 0.0


class UserSessionItem(BaseModel):
    id: str
    title: str = ""
    message_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageItem] = []


# ---------- Agent 团队 ----------
class AgentInfo(BaseModel):
    name: str
    title: str
    icon: str
    description: str
    tools: list[str] = []


class TeamResponse(BaseModel):
    supervisor: dict
    experts: list[AgentInfo]


# ---------- 运营管理 ----------
class SessionSummary(BaseModel):
    id: str
    message_count: int
    created_at: float
    updated_at: float
    preview: str
    username: str = ""


class StatsResponse(BaseModel):
    total_sessions: int
    total_messages: int
    agent_calls: dict[str, int]
    likes: int = 0
    dislikes: int = 0
    index_ready: bool
    llm_provider: str
    llm_model: str


# ---------- 知识库 ----------
class DocumentInfo(BaseModel):
    name: str
    size_bytes: int
    modified: str


class RebuildResponse(BaseModel):
    documents: int
    chunks: int
    dimension: int


class SimpleResult(BaseModel):
    ok: bool
    message: str = ""


# ---------- 认证 ----------
# 用户名字符白名单：字母 / 数字 / 下划线 / 连字符 / 点 / @ / 中文。
# 目的是挡掉 <>"'/ 这类会污染 HTML 的字符——用户名会出现在导航栏和运营看板上，
# 只靠前端转义是单点防御，服务端也必须拦住。
USERNAME_PATTERN = r"^[\w\u4e00-\u9fff.@-]+$"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32, pattern=USERNAME_PATTERN,
                          description="用户名（字母/数字/下划线/点/@/连字符/中文）")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class AdminCreateUserRequest(BaseModel):
    """管理员创建账号（公网部署关闭开放注册后，新账号由此入口开通）"""
    username: str = Field(..., min_length=1, max_length=32, pattern=USERNAME_PATTERN,
                          description="用户名（字母/数字/下划线/点/@/连字符/中文）")
    password: str = Field(..., min_length=6, max_length=128, description="密码（至少 6 位）")
    role: str = Field("user", description="角色：user / admin")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=1, max_length=128, description="新密码")


class AuthResponse(BaseModel):
    token: str
    username: str
    role: str


class UserInfo(BaseModel):
    username: str
    role: str
