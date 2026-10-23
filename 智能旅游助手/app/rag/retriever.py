"""知识库检索：懒加载 FAISS 索引，提供相似度检索

两个性能/安全设计点
--------------------
1. **按 query 缓存检索结果**：多专家协作时每个专家节点都会请求一次知识库，
   而 query 完全相同。不缓存就要把同一句话重复编码 N 次（BGE 编码在 CPU 上
   单次约 10~30ms，看似不多，但这是纯浪费，且随专家数量线性增长）。
2. **chunks 用 JSON 而不是 pickle**：pickle 反序列化等价于执行任意代码，
   知识库文件一旦被替换（管理员导入站外攻略、挂载卷被写入）就是远程代码执行。
   纯数据没有理由用 pickle。旧版 `chunks.pkl` 仍可读，并在首次加载时自动转成 JSON。
"""

import json
import logging
import threading
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.rag import coverage

logger = logging.getLogger("travel.rag")

_lock = threading.Lock()
_index = None
_chunks = None
_model = None
_gram_idf: dict[str, float] = {}
# 检索链路是否真的可用（不是「索引文件存在」，而是「模型和索引都加载成功」）。
# 这两个状态必须分开：重型依赖是延迟导入的，容器里 torch 装失败时进程照样起得来，
# 索引文件也照样在，于是 /health 报 index_ready=true，而实际每次检索都抛异常。
_ready = False
_last_error: str | None = None


def _chunks_path() -> Path:
    return settings.index_dir / "chunks.json"


def _legacy_chunks_path() -> Path:
    return settings.index_dir / "chunks.pkl"


def index_ready() -> bool:
    """索引**文件**是否齐备。注意这不代表检索可用，见 ready()。"""
    has_chunks = _chunks_path().exists() or _legacy_chunks_path().exists()
    return (settings.index_dir / "faiss.index").exists() and has_chunks


def ready() -> bool:
    """检索链路是否真的可用（模型 + 索引都加载成功过一次）。"""
    return _ready


def last_error() -> str | None:
    """最近一次加载/检索失败的原因，供 /health 与运营排查使用。"""
    return _last_error


def state() -> str:
    """检索链路状态：absent / warming / ready / failed。

    单看布尔值分不清「还在预热」和「真的坏了」——刚启动时健康检查就会误报失败，
    运维反而会去查一个不存在的问题。
    """
    if _ready:
        return "ready"
    if _last_error:
        return "failed"
    return "warming" if index_ready() else "absent"


def reset():
    """索引重建后调用，清除进程内缓存"""
    global _index, _chunks, _model, _gram_idf, _ready, _last_error
    with _lock:
        _index = None
        _chunks = None
        _model = None
        _gram_idf = {}
        _ready = False
        _last_error = None
    _search_cached.cache_clear()
    # 知识库文档变了，覆盖城市清单也跟着变（新增「哈尔滨.md」即自动纳入覆盖范围）
    coverage.reset_cache()


def _read_chunks() -> list[dict]:
    """读 chunks：优先 JSON，兼容旧的 pickle 并顺手迁移"""
    path = _chunks_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    legacy = _legacy_chunks_path()
    if not legacy.exists():
        raise FileNotFoundError(
            "知识库索引不存在，请先运行 python scripts/build_kb.py 或调用 POST /api/knowledge/rebuild"
        )
    # 只信任本进程生成的旧文件；迁移后删除 pkl，避免长期留着这个反序列化入口
    import pickle

    with legacy.open("rb") as fh:
        chunks = pickle.load(fh)
    path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    legacy.unlink(missing_ok=True)
    logger.info("已把旧版 chunks.pkl 迁移为 chunks.json（%d 块）", len(chunks))
    return chunks


def _err_chain(e: BaseException, depth: int = 5) -> str:
    """把异常链压成一行。

    外层异常经常只说「无法导入 PreTrainedModel，请开 DEBUG 看原始错误」——
    真正的根因（缺包、版本冲突）藏在 `__cause__` / `__context__` 里。
    不把它挖出来，线上排查就只能靠猜。
    """
    parts: list[str] = []
    cur: BaseException | None = e
    while cur is not None and len(parts) < depth:
        parts.append(f"{type(cur).__name__}: {cur}")
        cur = cur.__cause__ or cur.__context__
    return " <- ".join(parts)


def load_embedding_model(name: str):
    """加载 BGE 向量模型：**先本地缓存，后联网下载**。

    反过来（默认行为）会在每次进程启动时向 HF 探一次版本，网络不通就直接抛错。
    实测镜像 hf-mirror.com 偶发 502 时，整个检索链路在启动阶段就废掉，
    而模型其实早已在本地缓存里 —— 白白等了 100 秒然后失败。
    """
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(name, local_files_only=True)
    except Exception:
        logger.info("本地未命中 embedding 模型缓存，尝试联网下载: %s", name)
        return SentenceTransformer(name)


def probe_imports() -> dict[str, str]:
    """逐个真 import 关键包，返回 ok 或异常链。

    `find_spec` 只能回答「包装没装」，装上了却 import 失败（版本冲突、缺子依赖）
    它查不出来 —— 这次线上就是这种情况：四个包全都在，`PreTrainedModel` 却导不进来。
    只在检索不可用时才调用，避免拖慢正常路径的健康检查。
    """
    out: dict[str, str] = {}
    for mod in ("torch", "transformers", "sentence_transformers"):
        try:
            __import__(mod)
            out[mod] = "ok"
        except Exception as e:
            out[mod] = _err_chain(e, 3)
    return out


def _ensure_loaded():
    global _index, _chunks, _model, _gram_idf, _ready, _last_error
    if _index is not None and _model is not None:
        return
    with _lock:
        if _index is not None and _model is not None:
            return
        try:
            import faiss

            index_file = settings.index_dir / "faiss.index"
            if not index_file.exists():
                raise FileNotFoundError(
                    "知识库索引不存在，请先运行 python scripts/build_kb.py 或调用 POST /api/knowledge/rebuild"
                )
            # 先全部建成局部变量，**成功后才发布**到模块级状态。
            # 此前是先赋 _index 再加载模型：一旦模型加载失败（首次下载超时、
            # 镜像 502），_index 已被置位，后续每次检索都会跳过加载直接拿 None 去
            # encode，表现为「首次报 502，之后永久报 'NoneType' object has no
            # attribute 'encode'」，只能重启进程才能恢复。
            chunks = _read_chunks()
            index = faiss.read_index(str(index_file))
            gram_idf = _build_gram_idf(chunks)
            model = load_embedding_model(settings.embedding_model)
        except Exception as e:
            # 把原因记下来给 /health 看：容器里 torch 装失败时进程照样起得来
            # （重型依赖延迟导入），如果只报 index_ready=true，运维会以为一切正常。
            _last_error = _err_chain(e)
            logger.warning("检索链路加载失败: %s", _last_error)
            raise

        _chunks, _index, _gram_idf, _model = chunks, index, gram_idf, model
        _ready = True
        _last_error = None


def _build_gram_idf(chunks: list[dict]) -> dict[str, float]:
    """统计所有文本块的 2-gram 文档频率，得到每个 gram 的 IDF。

    这是重排的关键：在旅游语料里「门票」「开放时间」几乎每个城市的段落都有，
    而「故宫」「宽窄巷子」只出现在特定段落。不区分稀有度的话，词法信号会把
    「预算参考」这种通用段落推到正确景点段落前面（实测确实如此）。
    """
    import math

    df: dict[str, int] = {}
    for c in chunks:
        text = c.get("text", "")
        seen = {text[i : i + 2] for i in range(len(text) - 1)}
        for g in seen:
            df[g] = df.get(g, 0) + 1
    n = max(len(chunks), 1)
    return {g: math.log((n + 1) / (d + 0.5)) for g, d in df.items()}


def warmup() -> bool:
    """预热：提前加载 FAISS 索引 + BGE 模型，避免第一个真实用户承担冷启动。

    在 lifespan 里以后台线程调用，失败只记日志、不影响启动。
    """
    global _ready, _last_error
    try:
        _ensure_loaded()
        if _chunks:
            _search_cached("预热", 1)  # 真正跑一次编码，把 BGE 的图与权重都拉进内存
        logger.info("知识库检索已预热（%d 个文本块）", len(_chunks or []))
        return True
    except Exception as e:
        # 加载成功但编码失败也算不可用：/health 不能因为「模型对象存在」就报 ready。
        # 同时把已加载状态整体清掉，否则下次 search() 会走 `_ensure_loaded` 的
        # 早退分支，`_ready` 永远停在 False —— 检索其实恢复了，健康检查却一直说挂了。
        reset()
        _last_error = _err_chain(e)
        logger.warning("知识库预热失败（首个请求会慢一些）: %s", e)
        return False


_LEXICAL_WEIGHT = 0.3


@lru_cache(maxsize=256)
def _search_cached(query: str, k: int) -> tuple[tuple[str, str, float], ...]:
    """真正的检索（带缓存）：向量召回 → 词法重排 → 取 top_k。

    为什么要重排
    ------------
    bge-small-zh 是个小模型，对「故宫门票多少钱」这类问题会把「预算参考」
    段落排到「故宫」段落前面 —— 因为两者都含「门票」二字，而小模型抓不住
    「故宫」才是真正的实体。实测 top-1 是错的。
    这里先多召回 4 倍候选，再用 **2-gram 覆盖率** 做一次轻量词法重排：
    实体名（故宫、宽窄巷子、兵马俑）在中文里几乎必然逐字出现在正确段落中，
    这个信号比向量余弦更可靠，且零额外依赖、零额外延迟。
    """
    _ensure_loaded()
    import numpy as np

    fetch = min(max(k * 4, 12), len(_chunks))
    qv = _model.encode([query], normalize_embeddings=True)
    scores, ids = _index.search(np.asarray(qv, dtype="float32"), fetch)

    # 城市一致性：查询里点名的城市，只在该城市文档内检索。
    # 不做这一步时，「上海去苏州怎么走」的 top-1 会返回北京的颐和园 ——
    # 向量相似度被「怎么走」这种通用短语带偏，而旅游场景里城市是硬约束。
    #
    # 但「通用文档」（行前装备、证件、通用避坑）不是任何城市，必须放行：
    # 问「北京要带什么」时，装备知识在《行前准备与装备》里，而 北京.md 里没有 ——
    # 按城市一刀切会把它滤掉，等于城市约束把正确答案挡在门外。
    stems = {c["doc"].rsplit(".", 1)[0] for c in _chunks}
    mentioned = {s for s in stems if s in query}
    city_docs = set(coverage.map_cities())

    matched: list[tuple[str, str, float]] = []
    fallback: list[tuple[str, str, float]] = []
    for s, i in zip(scores[0], ids[0], strict=True):
        if i < 0 or s <= 0.15:  # 过滤无相似度的结果
            continue
        chunk = _chunks[i]
        fused = min(1.0, float(s) + _LEXICAL_WEIGHT * _bigram_coverage(query, chunk["text"]))
        if fused < settings.retrieval_min_score:  # 相关度下限：宁缺毋滥
            continue
        item = (chunk["doc"], chunk["text"], fused)
        fallback.append(item)
        stem = chunk["doc"].rsplit(".", 1)[0]
        if not mentioned or stem in mentioned or stem not in city_docs:
            matched.append(item)

    chosen = matched if mentioned else fallback
    chosen.sort(key=lambda x: -x[2])
    return tuple(chosen[:k])


def _bigram_coverage(query: str, text: str) -> float:
    """查询 2-gram 的 **IDF 加权** 覆盖率（0~1）。

    中文没有空格分词，2-gram 是最省事又足够有效的近似；按 IDF 加权后，
    命中「故宫」的段落会显著高于只命中「门票」的段落。
    """
    if len(query) < 2:
        return 0.0
    grams = {query[i : i + 2] for i in range(len(query) - 1)}
    if not grams:
        return 0.0
    total = 0.0
    hit = 0.0
    for g in grams:
        w = _gram_idf.get(g, 1.0)  # 语料里没出现过的 gram 视为高信息量
        total += w
        if g in text:
            hit += w
    return hit / total if total else 0.0


def search(query: str, top_k: int | None = None) -> list[dict]:
    """检索最相似的 top_k 个文本块，返回 [{doc, text, score}]"""
    _ensure_loaded()
    # 用 `is None` 而不是 `or`：`top_k=0` 是「不要结果」，`0 or 默认值` 会把它
    # 悄悄变成「按默认 top_k 取」，调用方以为空结果、实际拿到 4 条。
    k = min(settings.retrieval_top_k if top_k is None else top_k, len(_chunks))
    if k <= 0:
        return []
    # 用户点名的城市全都不在攻略库里 → 直接返回空，宁可「没查到」也不要拿
    # 别的城市的内容顶包。此前问「哈尔滨有什么好玩的」会返回北京的段落，
    # 分数还能过 0.55 的门槛（「有什么好玩的」这种通用短语贡献了大部分相似度），
    # 模型于是拿北京的资料回答哈尔滨 —— 比答不上来更糟。
    cov = coverage.detect(query)
    if cov.uncovered and not cov.covered:
        logger.info("查询城市无攻略库覆盖，跳过检索: %s", "、".join(cov.uncovered))
        return []
    return [{"doc": d, "text": t, "score": s} for d, t, s in _search_cached(query, k)]
