"""RAG 切分与重排的纯逻辑测试（不加载向量模型，毫秒级）。

这些用例锁死的是本轮修复的三个真实缺陷：
1. 固定字数切分把「预算参考 + 行程 + 避坑」揉成一块，导致 top-1 检索错
2. 块首没有城市名，六个城市的同名小节在向量空间里混在一起
3. 词法重排未按稀有度加权，通用词「门票」压过了实体「故宫」
"""

from app.rag.indexer import split_document
from app.rag.retriever import _bigram_coverage

DOC = """# 北京旅游攻略

## 必游景点
### 故宫（紫禁城）
- 亮点: 世界现存规模最大的木结构宫殿建筑群
- 门票: 旺季 60 元，需提前实名预约

### 颐和园
- 亮点: 中国现存最完整的皇家园林

## 预算参考（每人每天）
- 经济型: 住宿160+餐饮80+交通30+门票40

## 经典3日行程
- 第1天: 天安门广场 → 故宫 → 景山公园
"""


def test_sections_are_split_by_heading():
    chunks = split_document("北京.md", DOC)
    texts = [c["text"] for c in chunks]

    # 预算与行程必须是两个独立块，不能揉在一起
    budget = next(t for t in texts if "预算参考" in t)
    itinerary = next(t for t in texts if "经典3日行程" in t)
    assert "经典3日行程" not in budget
    assert "预算参考" not in itinerary


def test_chunk_carries_city_prefix():
    """每个块都要带【城市】前缀，否则六个城市的「## 必游景点」无法区分。"""
    for c in split_document("北京.md", DOC):
        assert c["text"].startswith("【北京】")


def test_section_metadata_is_recorded():
    chunks = split_document("北京.md", DOC)
    headings = {c["section"] for c in chunks}
    assert "故宫（紫禁城）" in headings
    assert "预算参考（每人每天）" in headings


def test_short_sections_are_dropped():
    chunks = split_document("x.md", "## 空\n短\n")
    assert chunks == []


def test_long_section_is_recursively_split(monkeypatch):
    """超长小节必须继续切，不能整段塞进一个向量。"""
    from app.config import settings

    monkeypatch.setattr(settings, "chunk_size", 120)
    long_doc = "## 长小节\n" + "\n\n".join(f"第{i}段内容，讲述一段很长的景点介绍文字。" for i in range(20))
    chunks = split_document("长.md", long_doc)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 200 for c in chunks)


def test_bigram_coverage_prefers_exact_entity():
    """「故宫」出现在文本里时覆盖率应明显高于只含「门票」的文本。"""
    query = "故宫门票"
    exact = "故宫（紫禁城）门票 60 元"
    generic = "预算参考 门票 40 元"
    assert _bigram_coverage(query, exact) > _bigram_coverage(query, generic)


def test_bigram_coverage_is_bounded():
    assert _bigram_coverage("故宫", "完全没有关系的文本") == 0.0
    assert 0.0 <= _bigram_coverage("故宫", "故宫") <= 1.0
    assert _bigram_coverage("", "任意文本") == 0.0
    assert _bigram_coverage("单", "单") == 0.0  # 单字无法构成 bigram
