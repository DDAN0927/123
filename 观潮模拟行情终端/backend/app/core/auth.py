"""可选 Bearer 鉴权。

为什么现在才做：QuantFlow Pro 的 `/api/config/settings` 缺 Authorization 直接
401 `{"detail":"缺少 Authorization 请求头"}`；观潮此前所有接口裸奔，README 的
"待办"里写着"对外暴露前必须加"。这条待办不解决，"部署"就只是把数据送上网。

设计取舍（每条都有理由，不要随手改）：

1. **可选而非强制。** 由环境变量 `ACCESS_TOKEN` 决定。未设置 → 开发模式放行。
   本机开发、探针、CI 都不需要每次造 token；但 `/api/health` 会明说
   `auth.mode="off"`，不假装自己是安全的。
2. **白名单只放 /api/health。** 前端靠它判断"后端在不在"，它是探活端点；
   返回体只有版本、provider 名、标的数量，没有敏感信息。
   `/docs`、`/openapi.json`、`/` 也不拦：前两个是静态文档壳，`/` 是前端页面本身
   —— 拦了页面就白屏，用户连"没有权限"这句话都看不到。
3. **OPTIONS 放行。** 浏览器 CORS 预检不带 Authorization 头，
   拦了会让跨域（file:// 打开 + ?api=on）直接失败成"后端不可用"，
   这是最难排查的一类假故障。
4. **比较用 `hmac.compare_digest`。** 普通 `==` 会在首个不同字节处提前返回，
   时间差可被用来逐字节猜 token。虽然本地场景不敏感，但这是零成本的习惯。
5. **错误文案区分"没带"和"带错"。** 只报状态码不报原因，调试时只能靠猜。
   注意不把期望 token 的任何片段写进响应。
"""

from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

ENV_TOKEN = "ACCESS_TOKEN"
# 探活端点：故意开放，理由见模块文档第 2 条
OPEN_PATHS = frozenset({"/api/health"})
HEADER_BEARER = "authorization"
HEADER_ALT = "x-api-token"


def expected_token() -> str:
    return (os.getenv(ENV_TOKEN) or "").strip()


def mode() -> str:
    return "bearer" if expected_token() else "off"


def describe() -> dict:
    """给 /api/health 用的自描述。让下游一眼看出"这服务现在要不要 token"。"""
    if not expected_token():
        return {
            "mode": "off",
            "note": "未设置 ACCESS_TOKEN：接口无鉴权，仅适合本机/内网，禁止直接暴露公网",
        }
    return {
        "mode": "bearer",
        "header": "Authorization: Bearer <token>",
        "open_paths": sorted(OPEN_PATHS),
        "note": "已启用鉴权；/api/health 保持开放用于探活，其余 /api/* 需带 token",
    }


def _presented(request: Request) -> str:
    raw = request.headers.get(HEADER_BEARER) or ""
    if raw[:7].lower() == "bearer ":
        return raw[7:].strip()
    # 备用头：给不方便改 Authorization 的客户端（如某些 MCP 客户端）
    return (request.headers.get(HEADER_ALT) or "").strip()


async def guard(request: Request) -> JSONResponse | None:
    """返回 None 表示放行；返回 JSONResponse 表示拦下。"""
    want = expected_token()
    if not want:
        return None                       # 开发模式
    if request.method == "OPTIONS":
        return None                       # CORS 预检
    path = request.url.path
    if not path.startswith("/api/"):
        return None                       # /、/docs、/openapi.json
    if path in OPEN_PATHS:
        return None

    got = _presented(request)
    if got and hmac.compare_digest(got.encode("utf-8"), want.encode("utf-8")):
        return None

    detail = "缺少 Authorization 请求头" if not got else "token 不正确"
    return JSONResponse(
        status_code=401,
        content={"detail": detail, "auth": {"mode": "bearer", "open_paths": sorted(OPEN_PATHS)}},
        headers={"WWW-Authenticate": "Bearer"},
    )
