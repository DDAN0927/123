"""外部内容库：CRUD、分页、过滤、权限。

用例之间用唯一标记 MARK 隔离：每条数据都带 MARK，
查询时用 `?q=MARK` 过滤，避免与其它用例或历史数据互相干扰。
"""

import uuid

import pytest

MARK = uuid.uuid4().hex[:8]
CITY = f"城{MARK}"


@pytest.fixture
def seeded(client, admin_headers):
    """建 5 条带唯一标记的内容，用例结束后清理。"""
    ids = []
    for i in range(5):
        r = client.post(
            "/api/notes",
            headers=admin_headers,
            json={
                "source": "manual",
                "title": f"标题{MARK}-{i}",
                "content": f"正文{MARK}-{i} 的内容",
                "city": CITY,
                "tags": f"tag{MARK}",
                "author": f"作者{i}",
            },
        )
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    yield ids
    for nid in ids:
        client.delete(f"/api/notes/{nid}", headers=admin_headers)


# ---------------------------------------------------------------- 权限
def test_anonymous_cannot_list(client):
    assert client.get("/api/notes").status_code == 401


def test_normal_user_can_read(client, new_user):
    assert client.get("/api/notes", headers=new_user["headers"]).status_code == 200


def test_normal_user_cannot_create(client, new_user):
    r = client.post("/api/notes", headers=new_user["headers"], json={"source": "manual", "content": "x"})
    assert r.status_code == 403


def test_normal_user_cannot_update(client, new_user, seeded):
    r = client.put(f"/api/notes/{seeded[0]}", headers=new_user["headers"], json={"title": "hacked"})
    assert r.status_code == 403


def test_normal_user_cannot_delete(client, new_user, seeded):
    assert client.delete(f"/api/notes/{seeded[0]}", headers=new_user["headers"]).status_code == 403


# ---------------------------------------------------------------- 导入
def test_create_and_detail(client, admin_headers):
    r = client.post(
        "/api/notes",
        headers=admin_headers,
        json={
            "source": "xiaohongshu",
            "title": f"详情{MARK}",
            "content": f"详情正文{MARK}",
            "city": CITY,
            "tags": "咖啡",
        },
    )
    assert r.status_code == 200, r.text
    nid = r.json()["id"]

    r = client.get(f"/api/notes/{nid}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["title"] == f"详情{MARK}"
    assert r.json()["source"] == "xiaohongshu"

    client.delete(f"/api/notes/{nid}", headers=admin_headers)


def test_create_empty_content_rejected(client, admin_headers):
    r = client.post("/api/notes", headers=admin_headers, json={"source": "manual", "content": "   "})
    assert r.status_code == 400


def test_create_too_long_content_rejected(client, admin_headers):
    r = client.post("/api/notes", headers=admin_headers, json={"source": "manual", "content": "x" * 20001})
    assert r.status_code in (400, 422)


def test_unknown_source_falls_back_to_other(client, admin_headers):
    r = client.post(
        "/api/notes", headers=admin_headers, json={"source": "weibo", "content": f"来源兜底{MARK}"}
    )
    assert r.status_code == 200
    assert r.json()["source"] == "other"
    client.delete(f"/api/notes/{r.json()['id']}", headers=admin_headers)


# ---------------------------------------------------------------- 分页
def test_pagination_total_header(client, admin_headers, seeded):
    r = client.get("/api/notes", params={"q": MARK, "limit": 2, "offset": 0}, headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2
    # 返回体是数组（向后兼容），总数在响应头里
    assert r.headers["X-Total-Count"] == "5"


def test_pagination_pages_do_not_overlap(client, admin_headers, seeded):
    p1 = client.get("/api/notes", params={"q": MARK, "limit": 2, "offset": 0}, headers=admin_headers).json()
    p2 = client.get("/api/notes", params={"q": MARK, "limit": 2, "offset": 2}, headers=admin_headers).json()
    assert {n["id"] for n in p1}.isdisjoint({n["id"] for n in p2})


def test_pagination_offset_beyond_end(client, admin_headers, seeded):
    r = client.get("/api/notes", params={"q": MARK, "limit": 10, "offset": 999}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []
    assert r.headers["X-Total-Count"] == "5"


# ---------------------------------------------------------------- 过滤
def test_filter_by_city(client, admin_headers, seeded):
    r = client.get("/api/notes", params={"city": CITY}, headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 5
    assert all(n["city"] == CITY for n in r.json())


def test_filter_by_source(client, admin_headers, seeded):
    r = client.get("/api/notes", params={"q": MARK, "source": "manual"}, headers=admin_headers)
    assert len(r.json()) == 5

    r = client.get("/api/notes", params={"q": MARK, "source": "douyin"}, headers=admin_headers)
    assert r.json() == []


def test_filter_by_keyword_hits_title(client, admin_headers, seeded):
    r = client.get("/api/notes", params={"q": f"标题{MARK}-3"}, headers=admin_headers)
    assert len(r.json()) == 1


def test_filter_no_match_returns_empty(client, admin_headers, seeded):
    r = client.get("/api/notes", params={"q": f"绝对不存在的词{uuid.uuid4().hex}"}, headers=admin_headers)
    assert r.json() == []


# ---------------------------------------------------------------- 概览
def test_stats_contains_city_breakdown(client, admin_headers, seeded):
    r = client.get("/api/notes/stats", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 5
    assert any(c["city"] == CITY for c in body["cities"])


# ---------------------------------------------------------------- 编辑
def test_update_is_partial(client, admin_headers, seeded):
    nid = seeded[0]
    before = client.get(f"/api/notes/{nid}", headers=admin_headers).json()

    r = client.put(f"/api/notes/{nid}", headers=admin_headers, json={"title": "改后标题"})
    assert r.status_code == 200
    after = r.json()

    assert after["title"] == "改后标题"
    # 未传的字段必须保持原值
    assert after["content"] == before["content"]
    assert after["city"] == before["city"]
    assert after["tags"] == before["tags"]


def test_update_empty_content_rejected(client, admin_headers, seeded):
    r = client.put(f"/api/notes/{seeded[0]}", headers=admin_headers, json={"content": "   "})
    assert r.status_code == 400


def test_update_unknown_id_returns_404(client, admin_headers):
    r = client.put("/api/notes/no-such-id", headers=admin_headers, json={"title": "x"})
    assert r.status_code == 404


# ---------------------------------------------------------------- 删除
def test_delete_then_404(client, admin_headers):
    r = client.post(
        "/api/notes", headers=admin_headers, json={"source": "manual", "content": f"待删除{MARK}"}
    )
    nid = r.json()["id"]

    assert client.delete(f"/api/notes/{nid}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/notes/{nid}", headers=admin_headers).status_code == 404
    assert client.delete(f"/api/notes/{nid}", headers=admin_headers).status_code == 404
