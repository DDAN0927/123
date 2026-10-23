"""知识库索引构建：文档加载 → 切分 → BGE 向量化 → FAISS 入库

注意：重型依赖（faiss / sentence-transformers / numpy）一律延迟到函数内部导入，
这样即使某个依赖缺失或与运行环境不兼容，也不会在应用启动时直接把整站拖垮，
最多只影响索引构建这一条链路。
"""

import json
import re
import time
from pathlib import Path

from app.config import settings

# 按 Markdown 标题边界切分（## / ### 起头的行）
_SECTION_RE = re.compile(r"(?m)^(?=#{1,4} )")


def load_documents() -> list[tuple[str, str]]:
    """加载知识库目录下全部 .md/.txt 文档，返回 (文件名, 正文) 列表"""
    kb = Path(settings.kb_dir)
    docs = []
    for f in sorted(kb.glob("**/*")):
        if f.suffix.lower() not in (".md", ".txt"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore").strip()
        if text:
            docs.append((f.name, text))
    return docs


def _heading_of(section: str) -> str:
    first = section.split("\n", 1)[0].strip()
    return first.lstrip("# ").strip() if first.startswith("#") else ""


def split_document(name: str, text: str) -> list[dict]:
    """把一篇文档切成「语义小节」块。

    为什么按标题切而不是按固定字数切
    --------------------------------
    早期用 `RecursiveCharacterTextSplitter(chunk_size=500)` 硬切，结果
    「预算参考 + 经典3日行程 + 避坑提示」三节被揉进同一个块里。后果是
    问「故宫门票多少钱」时，这块因为同时含「故宫」和「门票」而排到
    「故宫（紫禁城）」那一节前面 —— 检索看起来「有结果」，但 top-1 是错的。
    知识库本来就是结构化 Markdown，标题就是天然的语义边界，按它切最省事也最准。
    只有超长小节才退回到递归字符切分。
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    stem = Path(name).stem
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " "],
    )

    sections = [s.strip() for s in _SECTION_RE.split(text) if s.strip()]
    chunks: list[dict] = []
    for sec in sections:
        heading = _heading_of(sec)
        pieces = [sec] if len(sec) <= settings.chunk_size else splitter.split_text(sec)
        for piece in pieces:
            piece = piece.strip()
            if len(piece) < 20:
                continue
            # 前置城市名：单看「## 必游景点」无法判断是哪个城市，
            # 向量化时会把六个城市的同名小节混在一起。
            chunks.append({"doc": name, "section": heading, "text": f"【{stem}】{piece}"})
    return chunks


def doc_signature() -> dict[str, float]:
    """知识库文档签名：{文件名: mtime}。

    用它判断「索引是不是旧的」比比对文件数可靠得多 —— 改内容不改文件名
    （这次给 6 城补「住宿建议」「特色体验项目」就是这种情况）文件数不变，
    但 mtime 一定变。
    """
    kb = Path(settings.kb_dir)
    sig: dict[str, float] = {}
    for f in sorted(kb.glob("**/*")):
        if f.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            sig[f.name] = round(f.stat().st_mtime, 3)
        except OSError:
            continue
    return sig


def index_stale() -> bool:
    """索引与当前知识库是否已经不同步（需要重建）。

    没有 `meta.json` 的是旧版本索引（那时不记签名），无法确认内容是否最新，
    一律按「过期」处理 —— 重建一次的代价远小于线上一直用旧攻略回答。
    """
    meta_path = settings.index_dir / "meta.json"
    if not meta_path.exists():
        return True
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return meta.get("docs") != doc_signature()


def build_index() -> dict:
    """构建 FAISS 向量索引，返回 {documents, chunks, dimension}"""
    import faiss
    import numpy as np

    from app.rag.retriever import load_embedding_model

    docs = load_documents()
    if not docs:
        raise RuntimeError(f"知识库目录 {settings.kb_dir} 下没有 .md/.txt 文档")

    chunks: list[dict] = []
    for name, text in docs:
        chunks.extend(split_document(name, text))
    if not chunks:
        raise RuntimeError("切分后没有有效文本块，请检查知识库内容")

    # BGE 向量化（归一化后用内积等价余弦相似度）
    model = load_embedding_model(settings.embedding_model)
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    out = settings.index_dir
    out.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out / "faiss.index"))
    # 纯数据用 JSON，不用 pickle：反序列化 pickle 等价于执行任意代码
    (out / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    (out / "chunks.pkl").unlink(missing_ok=True)  # 清掉历史遗留的 pickle 入口

    # 记下构建时的文档签名，供 index_stale() 判断索引是否已经落后于知识库
    meta = {
        "built_at": round(time.time(), 3),
        "documents": len(docs),
        "chunks": len(chunks),
        "dimension": int(embeddings.shape[1]),
        "docs": doc_signature(),
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"documents": len(docs), "chunks": len(chunks), "dimension": int(embeddings.shape[1])}
