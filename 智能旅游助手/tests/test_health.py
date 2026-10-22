"""健康检查与静态资源：保证服务起来后基本可用。"""


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # index_ready 为布尔即可：临时 KB 目录为空，不强制要求已建索引
    assert isinstance(body["index_ready"], bool)


def test_index_page_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "旅游智能助手" in r.text


def test_admin_page_served(client):
    r = client.get("/admin.html")
    assert r.status_code == 200
    assert "运营管理" in r.text


def test_openapi_lists_notes_routes(client):
    """路由确实挂上了（新版 FastAPI 是懒加载 router，必须通过 openapi 校验）。"""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/api/notes" in paths
    assert "put" in paths["/api/notes/{nid}"]
    assert "/api/notes/export-to-kb" in paths


def test_unknown_api_returns_404(client):
    assert client.get("/api/definitely-not-exist").status_code == 404


def test_public_config_is_anonymous(client):
    """前端运行时配置：不需要登录，且只暴露本来就该给浏览器的值。"""
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"amap_key", "amap_security_js_code"}
    # 不能把 LLM Key 之类的服务端密钥顺手塞进来
    assert "llm_api_key" not in body
    assert "admin_password" not in body


def test_public_config_lists_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/config" in paths
