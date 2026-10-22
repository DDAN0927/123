"""pytest 公共夹具。

关键点：**环境变量必须在 import app 之前设置**。
`app.config.Settings` 在模块导入时就把 `.env` 与环境变量读进实例，
之后再改 os.environ 不会生效（pydantic-settings 的实例已固化）。
pytest 会先加载 conftest.py，所以这里的赋值时机是对的。
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="tc-pytest-"))
_DATA = _TMP / "data"
_KB = _TMP / "kb"
_DATA.mkdir(parents=True, exist_ok=True)
_KB.mkdir(parents=True, exist_ok=True)

# 全部离线、零成本：不调真实大模型，不污染项目里的 data/
os.environ.update(
    DATA_DIR=str(_DATA),
    KB_DIR=str(_KB),
    LLM_PROVIDER="mock",
    ADMIN_USERNAME="admin",
    ADMIN_PASSWORD="admin123",
    ALLOW_REGISTRATION="true",
    RATE_LIMIT_ENABLED="false",  # 用例之间不应互相触发 429
    TOKEN_TTL_SECONDS="604800",
)

# 注意：这两行必须写在上面 os.environ.update() 之后。
# ruff 的 E402（import 不在文件顶部）默认未启用，所以不需要 noqa。
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """整个会话共用一个 TestClient（会触发 lifespan：建库 + 创建默认管理员）。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client) -> str:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def admin_headers(admin_token) -> dict:
    """管理员请求头。用 X-Auth-Token：线上平台 WAF 会拦 Authorization: Bearer。"""
    return {"X-Auth-Token": admin_token}


@pytest.fixture
def new_user(client):
    """注册一个全新普通用户，返回 (username, token, headers)。

    每个用例用独立账号，避免共享状态互相干扰。
    """
    username = f"u{uuid.uuid4().hex[:10]}"
    password = "pw123456"
    r = client.post("/api/auth/register", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    data = r.json()
    return {
        "username": username,
        "password": password,
        "token": data["token"],
        "headers": {"X-Auth-Token": data["token"]},
    }
