"""知识库索引构建：文档加载 → 切分 → BGE 向量化 → FAISS 入库

注意：重型依赖（faiss / sentence-transformers / numpy）一律延迟到函数内部导入，
这样即使某个依赖缺失或与运行环境不兼容，也不会在应用启动时直接把整站拖垮，
最多只影响索引构建这一条链路。
"""
import pickle
from pathlib import Path

from app.config import settings


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


def build_index() -> dict:
    """构建 FAISS 向量索引，返回 {documents, chunks, dimension}"""
    import faiss
    import numpy as np
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from sentence_transformers import SentenceTransformer

    docs = load_documents()
    if not docs:
        raise RuntimeError(f"知识库目录 {settings.kb_dir} 下没有 .md/.txt 文档")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；", "，", " "],
    )
    chunks = []
    for name, text in docs:
        for piece in splitter.split_text(text):
            piece = piece.strip()
            if len(piece) >= 20:
                chunks.append({"doc": name, "text": piece})
    if not chunks:
        raise RuntimeError("切分后没有有效文本块，请检查知识库内容")

    # BGE 向量化（归一化后用内积等价余弦相似度）
    model = SentenceTransformer(settings.embedding_model)
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True,
    )
    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    out = settings.index_dir
    out.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out / "faiss.index"))
    with (out / "chunks.pkl").open("wb") as fh:
        pickle.dump(chunks, fh)

    return {"documents": len(docs), "chunks": len(chunks), "dimension": int(embeddings.shape[1])}
