"""外部内容库接口：导入 / 检索 / 删除站外攻略，并可导出到知识库参与 RAG 检索。

权限划分
--------
* **读**（列表 / 详情 / 概览）：登录用户即可，方便前端做攻略浏览与检索；
* **写**（新增 / 删除 / 导出到知识库）：仅管理员，避免匿名用户往库里灌内容。
"""

from fastapi import APIRouter, Depends, HTTPException, Response

from app import notes as notes_store
from app.api.deps import require_admin, require_user
from app.schemas import (
    NoteCreateRequest,
    NoteExportResponse,
    NoteItem,
    NoteStats,
    NoteUpdateRequest,
    SimpleResult,
)

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=list[NoteItem])
def list_notes(
    response: Response,
    city: str = "",
    q: str = "",
    source: str = "",
    limit: int = 50,
    offset: int = 0,
    _user: str = Depends(require_user),
):
    """列出内容库，支持按城市 / 来源 / 关键词过滤与分页。

    返回体仍是数组（保持向后兼容）；**分页总数放在 `X-Total-Count` 响应头里**，
    这样既不用改返回结构，前端也能正确渲染分页器。
    """
    items = notes_store.list_notes(
        limit=limit, offset=offset, city=city or None, keyword=q or None, source=source or None
    )
    total = notes_store.count_notes(city=city or None, keyword=q or None, source=source or None)
    response.headers["X-Total-Count"] = str(total)
    return [NoteItem(**n) for n in items]


@router.get("/stats", response_model=NoteStats)
def stats(_user: str = Depends(require_user)):
    """内容库概览：总量、按来源分布、覆盖城市数"""
    return NoteStats(**notes_store.note_stats())


@router.post("", response_model=NoteItem)
def create(req: NoteCreateRequest, admin: str = Depends(require_admin)):
    """导入一条站外攻略内容（仅管理员）"""
    try:
        n = notes_store.add_note(
            source=req.source,
            title=req.title,
            content=req.content,
            city=req.city,
            tags=req.tags,
            url=req.url,
            author=req.author,
            imported_by=admin,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return NoteItem(**n)


@router.post("/export-to-kb", response_model=NoteExportResponse)
def export_to_kb(_admin: str = Depends(require_admin)):
    """把内容库按城市导出成知识库文档并重建索引（仅管理员）。

    重建索引会加载 BGE 向量模型，首次执行较慢；若运行环境未安装
    sentence-transformers / faiss，这里会明确报错，而不是静默失败。
    """
    from app.rag import retriever  # 延迟导入：重型依赖不进启动路径

    try:
        r = notes_store.export_to_kb()
    except Exception as e:
        raise HTTPException(500, f"导出知识库文档失败: {e}") from e

    if r["notes"] == 0:
        return NoteExportResponse(ok=True, files=0, notes=0, message="内容库为空，已清空上一次导出的文档")

    try:
        from app.rag.indexer import build_index

        built = build_index()
        retriever.reset()
    except Exception as e:
        raise HTTPException(
            500, f"已导出 {r['files']} 个文档，但重建索引失败: {e}（内容已保存，可稍后重试）"
        ) from e

    return NoteExportResponse(
        ok=True,
        files=r["files"],
        notes=r["notes"],
        message=(
            f"已导出 {r['files']} 个文档、{r['notes']} 条内容，"
            f"索引重建完成（{built.get('chunks', 0)} 个文本块）"
        ),
    )


@router.get("/{nid}", response_model=NoteItem)
def detail(nid: str, _user: str = Depends(require_user)):
    n = notes_store.get_note(nid)
    if n is None:
        raise HTTPException(404, "内容不存在")
    return NoteItem(**n)


@router.put("/{nid}", response_model=NoteItem)
def update(nid: str, req: NoteUpdateRequest, _admin: str = Depends(require_admin)):
    """编辑一条内容（仅管理员）。只传需要修改的字段。"""
    try:
        n = notes_store.update_note(nid, **req.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if n is None:
        raise HTTPException(404, "内容不存在")
    return NoteItem(**n)


@router.delete("/{nid}", response_model=SimpleResult)
def remove(nid: str, _admin: str = Depends(require_admin)):
    """删除一条内容（仅管理员）"""
    if not notes_store.delete_note(nid):
        raise HTTPException(404, "内容不存在")
    return SimpleResult(ok=True, message="已删除")
