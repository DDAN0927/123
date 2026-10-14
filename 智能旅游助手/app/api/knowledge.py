"""知识库管理接口：文档列表/上传/删除与索引重建（仅管理员）"""
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.deps import require_admin
from app.config import settings
from app.rag import retriever
from app.schemas import DocumentInfo, RebuildResponse, SimpleResult

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

_MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2MB


def _safe_name(name: str) -> str:
    """规范化文件名：去路径、去特殊字符、保证 .md/.txt 后缀"""
    name = Path(name).name
    name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", name)
    # 防止 "." / ".." / ".md" 这类退化名
    if name.strip(".-") == "":
        name = "untitled"
    if not name.lower().endswith((".md", ".txt")):
        name += ".md"
    return name


@router.get("/documents", response_model=list[DocumentInfo])
def list_documents(_admin: str = Depends(require_admin)):
    """知识库文档列表（仅管理员）"""
    kb = Path(settings.kb_dir)
    kb.mkdir(parents=True, exist_ok=True)
    files = sorted([*kb.glob("*.md"), *kb.glob("*.txt")], key=lambda p: p.name)
    return [
        DocumentInfo(
            name=f.name,
            size_bytes=f.stat().st_size,
            modified=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime)),
        )
        for f in files
    ]


@router.post("/upload", response_model=SimpleResult)
async def upload(file: UploadFile, _admin: str = Depends(require_admin)):
    """上传攻略文档（.md/.txt，UTF-8，≤2MB，仅管理员）"""
    # 前置校验：优先用声明大小拦截，避免把超大文件读进内存
    if file.size is not None and file.size > _MAX_UPLOAD_BYTES:
        raise HTTPException(400, "文件过大（限制 2MB）")

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(400, "文件过大（限制 2MB）")
    content = raw.decode("utf-8", errors="ignore")
    if not content.strip():
        raise HTTPException(400, "文件内容为空")

    name = _safe_name(file.filename or "untitled.md")
    dest = Path(settings.kb_dir) / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return SimpleResult(ok=True, message=f"已上传 {name}，请点击「重建索引」使其生效")


@router.delete("/documents/{name}", response_model=SimpleResult)
def delete_document(name: str, _admin: str = Depends(require_admin)):
    """删除知识库文档（仅管理员）"""
    name = _safe_name(name)
    f = Path(settings.kb_dir) / name
    if not f.exists():
        raise HTTPException(404, "文档不存在")
    f.unlink()
    return SimpleResult(ok=True, message=f"已删除 {name}，请重建索引使其生效")


@router.post("/rebuild", response_model=RebuildResponse)
def rebuild(_admin: str = Depends(require_admin)):
    """重建 FAISS 向量索引（上传/删除文档后调用，仅管理员）"""
    from app.rag.indexer import build_index  # 延迟导入：重型依赖不进启动路径

    try:
        stats = build_index()
        retriever.reset()
    except Exception as e:
        raise HTTPException(500, f"重建失败: {e}")
    return RebuildResponse(**stats)
