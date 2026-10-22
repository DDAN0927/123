"""轻量内存限流：保护公网部署下真实的 LLM 额度不被刷。

设计要点
--------
两级滑动窗口（都基于单调时钟，不受系统时间调整影响）：

* **单 IP 级**：拦住单个访客的高频刷取；匿名访客阈值更低，登录用户更宽松。
* **全局限级**：即使攻击者伪造 ``X-Forwarded-For`` 绕过 IP 维度，总量仍有硬上限——
  这是真正兜底的保险丝。

单进程内存实现（uvicorn 默认单 worker），进程重启即清零；零第三方依赖。
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import settings

# 定期清理的触发阈值：命中数超过该值时顺手回收过期 key
_SWEEP_THRESHOLD = 512


class SlidingWindow:
    """滑动窗口计数器：窗口内命中次数达到 limit 即拒绝。"""

    def __init__(self, limit: int, window: float = 60.0):
        self.limit = max(0, int(limit))
        self.window = float(window)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, int]:
        """记录一次命中。返回 (是否放行, 建议的 Retry-After 秒数)。"""
        if self.limit <= 0:  # limit<=0 视为不限制
            return True, 0
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.limit:
                retry = max(1, int(self.window - (now - q[0])) + 1)
                return False, retry
            q.append(now)
            if len(self._hits) > _SWEEP_THRESHOLD:
                self._sweep_locked(cutoff)
            return True, 0

    def _sweep_locked(self, cutoff: float):
        """回收整窗过期的 key（调用方需已持锁）。"""
        for k in [k for k, q in self._hits.items() if not q or q[-1] < cutoff]:
            self._hits.pop(k, None)

    def reset(self):
        with self._lock:
            self._hits.clear()


# 对话类接口：匿名更严、登录更宽松，外加全局保险丝
_llm_anon = SlidingWindow(settings.rate_limit_anonymous_per_minute)
_llm_user = SlidingWindow(settings.rate_limit_per_minute)
_llm_global = SlidingWindow(settings.rate_limit_global_per_minute)
# 登录 / 注册：防暴力破解
_auth_ip = SlidingWindow(settings.auth_rate_limit_per_minute)


def client_ip(request: Request) -> str:
    """解析真实客户端 IP。

    公网部署时请求会先经过反向代理，``request.client.host`` 是代理地址；
    此时真实 IP 在 ``X-Forwarded-For`` 首段（或 ``X-Real-IP``）。
    这些头可被伪造，所以全局窗口才是兜底——单 IP 窗口只用来拦「老老实实刷」的访客。
    """
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        real = request.headers.get("x-real-ip", "").strip()
        if real:
            return real
    return request.client.host if request.client else "unknown"


def _enforce(window: SlidingWindow, key: str, message: str):
    if not settings.rate_limit_enabled:
        return
    allowed, retry = window.hit(key)
    if not allowed:
        raise HTTPException(429, message, headers={"Retry-After": str(retry)})


def llm_rate_limit(request: Request):
    """对话接口限流依赖：全局 → 单 IP（区分匿名/登录）。"""
    _enforce(_llm_global, "__global__", "服务器当前请求较多，请稍后再试")
    ip = client_ip(request)
    username = _resolve_username(request)
    if username:
        _enforce(_llm_user, ip, "请求过于频繁，请稍后再试")
    else:
        _enforce(_llm_anon, ip, "匿名体验次数已达上限，请稍后再试或登录后继续")


def auth_rate_limit(request: Request):
    """登录 / 注册限流依赖：按 IP 限制尝试次数。"""
    _enforce(_auth_ip, client_ip(request), "尝试过于频繁，请稍后再试")


def _resolve_username(request: Request) -> str | None:
    """尽力解析当前登录用户（失败不影响限流，退化为匿名阈值）。"""
    try:
        from app.api.auth import optional_username

        # 两种鉴权头都试：部分平台（如魔搭创空间）的边缘 WAF 会拦掉
        # Authorization: Bearer，此时前端改用 X-Auth-Token。
        return optional_username(request.headers.get("authorization"), request.headers.get("x-auth-token"))
    except Exception:
        return None


def snapshot() -> dict:
    """当前限流配置与窗口占用情况（供管理员排查）。"""
    return {
        "enabled": settings.rate_limit_enabled,
        "anonymous_per_minute": settings.rate_limit_anonymous_per_minute,
        "user_per_minute": settings.rate_limit_per_minute,
        "global_per_minute": settings.rate_limit_global_per_minute,
        "auth_per_minute": settings.auth_rate_limit_per_minute,
        "trust_proxy_headers": settings.trust_proxy_headers,
        "active_keys": {
            "anonymous": len(_llm_anon._hits),
            "user": len(_llm_user._hits),
            "global": len(_llm_global._hits),
            "auth": len(_auth_ip._hits),
        },
    }
