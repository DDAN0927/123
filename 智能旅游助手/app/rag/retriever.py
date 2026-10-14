"""知识库检索：懒加载 FAISS 索引，提供相似度检索"""
import pickle
import threading

from app.config import settings

_lock = threading.Lock()
_index = None
_chunks = None
_model = None


def index_ready() -> bool:
    return (settings.index_dir / "faiss.index").exists() and (settings.index_dir / "chunks.pkl").exists()


def reset():
    """索引重建后调用，清除进程内缓存"""
    global _index, _chunks, _model
    with _lock:
        _index = None
        _chunks = None
        _model = None


def _ensure_loaded():
    global _index, _chunks, _model
    if _index is not None:
        return
    with _lock:
        if _index is not None:
            return
        import faiss

        index_file = settings.index_dir / "faiss.index"
        chunks_file = settings.index_dir / "chunks.pkl"
        if not index_file.exists() or not chunks_file.exists():
            raise FileNotFoundError(
                "知识库索引不存在，请先运行 python scripts/build_kb.py 或调用 POST /api/knowledge/rebuild"
            )
        _index = faiss.read_index(str(index_file))
        _chunks = pickle.loads(chunks_file.read_bytes())

        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.embedding_model)


def search(query: str, top_k: int | None = None) -> list[dict]:
    """检索最相似的 top_k 个文本块，返回 [{doc, text, score}]"""
    _ensure_loaded()
    import numpy as np

    k = min(top_k or settings.retrieval_top_k, len(_chunks))
    if k <= 0:
        return []
    qv = _model.encode([query], normalize_embeddings=True)
    scores, ids = _index.search(np.asarray(qv, dtype="float32"), k)
    return [
        {"doc": _chunks[i]["doc"], "text": _chunks[i]["text"], "score": float(s)}
        for s, i in zip(scores[0], ids[0])
        if i >= 0 and s > 0.15  # 过滤无相似度的结果
    ]
