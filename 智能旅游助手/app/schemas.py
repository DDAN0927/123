"""API 数据模型（Pydantic Schema）"""

from pydantic import BaseModel, Field


# ---------- 对话 ----------
class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户消息",
    )
    session_id: str | None = Field(None, description="会话ID，为空则新建会话")


class TraceItem(BaseModel):
    agent: str
    reason: str = ""


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    trace: list[TraceItem] = []
    outputs: dict[str, str] = {}
    # 专家级降级信息 {专家名: 失败原因}。同步接口此前把它丢掉，
    # 调用方只看到「回答变短了」，完全无法判断是不是有专家挂了。
    errors: dict[str, str] = {}
    # 知识库城市覆盖判定：{asked, covered, uncovered, kb_cities, map_cities}。
    # 调用方据此判断「这段回答是攻略库内容还是通用建议」，不再只能靠猜。
    coverage: dict = {}
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
    # token 用量与成本估算（AI 应用最核心的运行指标）
    llm_usage: dict = Field(default_factory=dict)


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

# 密码最小长度：注册 / 管理员建号 / 改密三处必须一致。
# 放在一处定义，避免再出现「某条路径忘了校验」的不一致。
MIN_PASSWORD_LENGTH = 6


class RegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=USERNAME_PATTERN,
        description="用户名（字母/数字/下划线/点/@/连字符/中文）",
    )
    # 与 AdminCreateUserRequest / ChangePasswordRequest 保持一致。
    # 早期这里只校验 min_length=1，导致「注册接口能设 1 位密码」——
    # 前端拦了 6 位但后端没拦，属于典型的「只做客户端校验」。
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=128,
        description=f"密码（至少 {MIN_PASSWORD_LENGTH} 位）",
    )


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class AdminCreateUserRequest(BaseModel):
    """管理员创建账号（公网部署关闭开放注册后，新账号由此入口开通）"""

    username: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=USERNAME_PATTERN,
        description="用户名（字母/数字/下划线/点/@/连字符/中文）",
    )
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=128,
        description=f"密码（至少 {MIN_PASSWORD_LENGTH} 位）",
    )
    role: str = Field("user", description="角色：user / admin")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, description="旧密码")
    # 改密同样要走长度策略，否则「注册 6 位、改密 1 位」等于绕过策略
    new_password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=128,
        description=f"新密码（至少 {MIN_PASSWORD_LENGTH} 位）",
    )


class AuthResponse(BaseModel):
    token: str
    username: str
    role: str


class UserInfo(BaseModel):
    username: str
    role: str


# ---------- 外部内容库（小红书 / 抖音 / 手工录入） ----------
# 说明：小红书与抖音均未向第三方开放通用的旅游内容接口（需企业资质，且只给
# 订单/商品/授权用户数据），所以这里不做抓取，只提供「管理员导入 + 落库检索」的通道。
NOTE_SOURCES = ("xiaohongshu", "douyin", "manual", "other")


class NoteItem(BaseModel):
    id: str
    source: str = "manual"
    title: str = ""
    content: str = ""
    city: str = ""
    tags: str = ""
    url: str = ""
    author: str = ""
    imported_by: str = ""
    created_at: float = 0.0


class NoteCreateRequest(BaseModel):
    source: str = Field("manual", description="来源：xiaohongshu / douyin / manual / other")
    title: str = Field("", max_length=80, description="标题，留空则取正文前 40 字")
    content: str = Field(..., min_length=1, max_length=20000, description="攻略正文")
    city: str = Field("", max_length=20, description="关联城市，导出知识库时按城市分组")
    tags: str = Field("", max_length=120, description="标签，逗号分隔")
    url: str = Field("", max_length=300, description="原文链接")
    author: str = Field("", max_length=40, description="原作者")


class NoteUpdateRequest(BaseModel):
    """局部更新：只传需要改的字段，未传（None）的保持原值。"""

    source: str | None = Field(None, description="来源：xiaohongshu / douyin / manual / other")
    title: str | None = Field(None, max_length=80)
    content: str | None = Field(None, min_length=1, max_length=20000)
    city: str | None = Field(None, max_length=20)
    tags: str | None = Field(None, max_length=120)
    url: str | None = Field(None, max_length=300)
    author: str | None = Field(None, max_length=40)


class NoteCity(BaseModel):
    city: str
    count: int = 0


class NoteStats(BaseModel):
    total: int = 0
    by_source: dict[str, int] = {}
    city_count: int = 0
    cities: list[NoteCity] = []


class NoteExportResponse(BaseModel):
    ok: bool
    files: int = 0
    notes: int = 0
    message: str = ""
