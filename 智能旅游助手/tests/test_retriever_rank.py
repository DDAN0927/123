"""检索排序逻辑的测试：不加载 BGE 模型，用假索引把「排序决策」单独测出来。

为什么要单独测
--------------
`scripts/eval_rag.py` 会真的加载模型跑 33 条 query，但那需要 30s 且只能在本地跑。
真正容易写错的不是模型，而是**我们自己写的那层逻辑**：相关度下限、城市硬约束、
IDF 加权重排、缓存失效。这些用假索引几毫秒就能钉死。
"""

import numpy as np
import pytest

from app.config import settings
from app.rag import retriever as R

CHUNKS = [
    {"doc": "北京.md", "section": "故宫", "text": "【北京】故宫 门票 60 元，需提前实名预约"},
    {"doc": "北京.md", "section": "预算参考", "text": "【北京】预算参考 门票 40 元 住宿 160 元"},
    {"doc": "上海.md", "section": "交通", "text": "【上海】去苏州可乘高铁，约 30 分钟"},
    {"doc": "成都.md", "section": "火锅", "text": "【成都】火锅 推荐 蜀大侠、小龙坎"},
]


class FakeIndex:
    """按预设顺序返回 (score, id)，模拟 FAISS 的向量召回结果。"""

    def __init__(self, pairs):
        self.pairs = pairs

    def search(self, _qv, k):
        pairs = self.pairs[:k]
        return (
            np.asarray([[p[0] for p in pairs]], dtype="float32"),
            np.asarray([[p[1] for p in pairs]], dtype="int64"),
        )


class FakeModel:
    def encode(self, _texts, normalize_embeddings=True):
        return np.zeros((1, 8), dtype="float32")


@pytest.fixture
def fake(monkeypatch):
    def _install(pairs):
        monkeypatch.setattr(R, "_chunks", CHUNKS)
        monkeypatch.setattr(R, "_index", FakeIndex(pairs))
        monkeypatch.setattr(R, "_model", FakeModel())
        monkeypatch.setattr(R, "_gram_idf", R._build_gram_idf(CHUNKS))
        R._search_cached.cache_clear()

    yield _install
    R._search_cached.cache_clear()


def test_low_score_is_filtered_by_min_score(fake):
    """相关度低于阈值的块必须丢弃 —— 宁缺毋滥，否则噪声会污染 prompt。"""
    fake([(0.30, 3), (0.20, 1)])
    assert R.search("机票怎么买", 3) == []


def test_city_constraint_excludes_other_cities(fake):
    """查询点名了城市，就只能在该城市文档里取块。

    不设这条约束时，「上海去苏州怎么走」的 top-1 会落到北京的段落，
    因为向量被「怎么走」这种通用短语带偏，而城市在旅游场景里是硬约束。
    """
    fake([(0.80, 3), (0.75, 2)])  # 召回顺序里成都火锅在前
    hits = R.search("上海去苏州怎么走", 3)
    assert hits and all(h["doc"] == "上海.md" for h in hits)


def test_entity_coverage_beats_raw_cosine(fake):
    """词法重排：命中实体「故宫」的块应压过只命中通用词「门票」的块。"""
    # 预算块向量分更高（0.70），但只命中「门票」；故宫块 0.66，命中「故宫」+「门票」
    fake([(0.70, 1), (0.66, 0)])
    hits = R.search("故宫门票多少钱", 2)
    assert hits[0]["doc"] == "北京.md"
    assert "故宫" in hits[0]["text"]


def test_no_city_mention_searches_all_docs(fake):
    fake([(0.80, 0), (0.70, 3)])
    hits = R.search("火锅推荐", 2)
    assert {h["doc"] for h in hits} == {"北京.md", "成都.md"}


def test_results_are_sorted_by_fused_score(fake):
    fake([(0.60, 1), (0.90, 0)])
    hits = R.search("北京故宫", 2)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_same_query_is_cached(fake, monkeypatch):
    """多专家协作时同一句话会被检索 N 次，缓存后只编码一次。"""
    counter = {"n": 0}

    class CountingModel(FakeModel):
        def encode(self, texts, normalize_embeddings=True):
            counter["n"] += 1
            return super().encode(texts, normalize_embeddings)

    fake([(0.80, 0)])
    monkeypatch.setattr(R, "_model", CountingModel())

    first = R.search("故宫门票", 1)
    second = R.search("故宫门票", 1)

    assert first == second
    assert counter["n"] == 1  # 第二次命中缓存，没有重新编码


def test_reset_clears_cache(fake):
    fake([(0.80, 0)])
    R.search("故宫门票", 1)
    R.reset()
    assert R._search_cached.cache_info().currsize == 0


def test_top_k_is_bounded_by_chunk_count(fake):
    fake([(0.90, 0)])
    assert len(R.search("北京", 99)) <= len(CHUNKS)


def test_zero_top_k_returns_empty(fake):
    fake([(0.90, 0)])
    assert R.search("北京", 0) == []


def test_min_score_setting_is_respected(fake, monkeypatch):
    fake([(0.60, 0)])
    assert R.search("故宫", 1)
    monkeypatch.setattr(settings, "retrieval_min_score", 0.95)
    R._search_cached.cache_clear()
    assert R.search("故宫", 1) == []


def test_err_chain_surfaces_root_cause():
    """外层异常只说「无法导入 PreTrainedModel」，根因在 __cause__ 里。

    线上真实遇到：四个包 find_spec 全是 True，import 却失败，
    /health 只报一句「请开 DEBUG 看原始错误」——等于让人去猜。
    """
    try:
        try:
            raise ModuleNotFoundError("No module named 'safetensors'")
        except Exception as inner:
            raise ImportError("Could not import module 'PreTrainedModel'") from inner
    except ImportError as e:
        chain = R._err_chain(e)

    assert "PreTrainedModel" in chain
    assert "safetensors" in chain


def test_load_failure_is_reported_not_hidden(tmp_path, monkeypatch):
    """索引文件存在但模型加载失败时，/health 必须能看出「检索其实不可用」。

    真实事故：容器里 torch 装失败，进程照样起得来（重型依赖延迟导入），
    `/health` 只报 `index_ready: true`，于是线上「看起来一切正常」，
    实际每次问答都在走「知识库暂不可用」的降级分支。
    """
    import json

    import faiss
    import numpy as np

    index_dir = tmp_path / "index"
    index_dir.mkdir()
    idx = faiss.IndexFlatIP(4)
    idx.add(np.eye(4, dtype="float32"))
    faiss.write_index(idx, str(index_dir / "faiss.index"))
    (index_dir / "chunks.json").write_text(
        json.dumps([{"doc": "北京.md", "text": "【北京】故宫"}], ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    def boom(_name):
        raise ImportError("No module named 'torch'")

    monkeypatch.setattr(R, "load_embedding_model", boom)
    R.reset()

    assert R.index_ready() is True  # 文件齐备
    with pytest.raises(ImportError):
        R.search("故宫", 1)
    assert R.ready() is False
    assert "torch" in (R.last_error() or "")

    R.reset()
