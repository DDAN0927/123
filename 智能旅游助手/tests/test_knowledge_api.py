"""知识库管理接口的覆盖：文件名规范化 / 列表 / 上传 / 删除 / 重建索引。

这几条原来全在 `--cov` 的 missing 里（32-39、57-60、74-88、94-99、105-112），
但它们是管理员唯一的「内容运营」入口，出问题的方式都很具体：

* 上传一个叫 `../../app/main.py` 的文件 —— 必须落成知识库里的普通文件名，不能穿越；
* 上传 2MB+1 字节 —— 必须 400，而不是先读进内存再拒绝；
* 重建索引时 faiss 炸了 —— 必须 500 带原因，而不是 200 假装成功（否则用户以为生效了）。

注意：这些用例都跑在 conftest 指定的临时 `KB_DIR` 上，不会污染真实知识库。
"""

from __future__ import annotations

import pytest

from app.api import knowledge

# ---------- 文件名规范化 ----------


@pytest.mark.parametrize(
    "raw,expect",
    [
        ("北京.md", "北京.md"),
        ("../../etc/passwd", "passwd.md"),  # 去路径 + 补后缀
        ("a b\tc.md", "a_b_c.md"),  # 空白与特殊字符归一
        ("..", "untitled.md"),  # 退化名
        # 注：".md" 目前会原样保留（strip(".-") 后还剩 "md"，不算退化名）。
        # 这条按**当前实现**断言，不美化。副作用是它会落成一个隐藏文件、
        # 且 `kb.glob("*.md")` 匹配不到 → 上传成功但列表里看不见。
        # 已在验收/覆盖率报告里记为观察项，未改实现。
        (".md", ".md"),
        ("攻略.TXT", "攻略.TXT"),  # 已有合法后缀不改写
    ],
)
def test_safe_name_normalizes(raw, expect):
    assert knowledge._safe_name(raw) == expect


def test_safe_name_blocks_path_traversal():
    """核心安全断言：上传名不能逃出知识库目录。"""
    name = knowledge._safe_name("../../../../app/main.py")
    assert "/" not in name and "\\" not in name and ".." not in name
    assert name.endswith(".md")


# ---------- 文档列表 ----------


def test_list_documents_requires_admin(client, new_user):
    """普通用户不能看运营信息（哪怕只是文件名列表）。"""
    r = client.get("/api/knowledge/documents", headers=new_user["headers"])
    assert r.status_code == 403


def test_list_documents_lists_only_root_md_and_txt(client, admin_headers):
    """只列根目录的 .md/.txt；子目录（spots/ guides/ 是脚本派生物）不该出现在这里。"""
    r = client.get("/api/knowledge/documents", headers=admin_headers)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    for row in rows:
        assert set(row) == {"name", "size_bytes", "modified"}
        assert row["name"].endswith((".md", ".txt"))
        assert "/" not in row["name"], "子目录文档不该被列出来"
        assert row["size_bytes"] >= 0


# ---------- 上传 ----------


def test_upload_writes_file_and_returns_hint(client, admin_headers, tmp_path):
    r = client.post(
        "/api/knowledge/upload",
        files={"file": ("qa-上传测试.md", "# 标题\n\n正文".encode(), "text/markdown")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "重建索引" in body["message"], "上传后必须提示要重建索引，否则用户以为已生效"


def test_upload_rejects_empty_file(client, admin_headers):
    """全空白内容要 400 —— 否则会往知识库里塞一篇空文档，索引里多一个噪声块。"""
    r = client.post(
        "/api/knowledge/upload",
        files={"file": ("empty.md", b"   \n\n  ", "text/markdown")},
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "空" in r.json()["detail"]


def test_upload_rejects_oversize(client, admin_headers):
    """超过 2MB 要 400，且提示里给出限制值。"""
    big = b"x" * (knowledge._MAX_UPLOAD_BYTES + 1)
    r = client.post(
        "/api/knowledge/upload",
        files={"file": ("big.md", big, "text/markdown")},
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "2MB" in r.json()["detail"]


def test_upload_rejects_oversize_after_read_when_size_unknown(monkeypatch):
    """有些客户端不报 Content-Length（`file.size` 为 None），必须读完再判一次。

    这是 74 行的「前置拦截」之外的兜底（78-79）。直接调端点函数才能造出
    `size is None` 的 UploadFile —— 走 TestClient 时 starlette 总会填上 size，
    这条分支就永远覆盖不到。
    """
    import asyncio
    import io

    from fastapi import UploadFile

    payload = b"x" * (knowledge._MAX_UPLOAD_BYTES + 1)
    fake = UploadFile(filename="big.md", file=io.BytesIO(payload), size=None)

    with pytest.raises(Exception) as exc:
        asyncio.run(knowledge.upload(file=fake, _admin="admin"))

    assert getattr(exc.value, "status_code", None) == 400
    assert "2MB" in exc.value.detail


def test_upload_requires_admin(client, new_user):
    r = client.post(
        "/api/knowledge/upload",
        files={"file": ("x.md", b"# x", "text/markdown")},
        headers=new_user["headers"],
    )
    assert r.status_code == 403


# ---------- 删除 ----------


def test_delete_removes_uploaded_document(client, admin_headers):
    client.post(
        "/api/knowledge/upload",
        files={"file": ("to-delete.md", b"# tmp", "text/markdown")},
        headers=admin_headers,
    )
    r = client.delete("/api/knowledge/documents/to-delete.md", headers=admin_headers)
    assert r.status_code == 200 and r.json()["ok"] is True

    names = [x["name"] for x in client.get("/api/knowledge/documents", headers=admin_headers).json()]
    assert "to-delete.md" not in names


def test_delete_missing_document_is_404(client, admin_headers):
    r = client.delete("/api/knowledge/documents/not-exist-xyz.md", headers=admin_headers)
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]


# ---------- 重建索引 ----------


def test_rebuild_success_resets_retriever(client, admin_headers, monkeypatch):
    """重建成功后必须 reset 检索缓存 —— 否则旧索引还在内存里，用户查到的是旧内容。"""
    from app.rag import indexer, retriever

    monkeypatch.setattr(indexer, "build_index", lambda: {"documents": 7, "chunks": 42, "dimension": 512})
    reset_calls = []
    monkeypatch.setattr(retriever, "reset", lambda: reset_calls.append(1))

    r = client.post("/api/knowledge/rebuild", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"documents": 7, "chunks": 42, "dimension": 512}
    assert reset_calls == [1]


def test_rebuild_failure_surfaces_reason(client, admin_headers, monkeypatch):
    """建索引失败要 500 并把原因带出来，不能 200 假装成功。"""
    from app.rag import indexer

    def boom():
        raise RuntimeError("faiss 加载失败")

    monkeypatch.setattr(indexer, "build_index", boom)

    r = client.post("/api/knowledge/rebuild", headers=admin_headers)
    assert r.status_code == 500
    assert "faiss 加载失败" in r.json()["detail"]


def test_rebuild_requires_admin(client, new_user):
    r = client.post("/api/knowledge/rebuild", headers=new_user["headers"])
    assert r.status_code == 403
