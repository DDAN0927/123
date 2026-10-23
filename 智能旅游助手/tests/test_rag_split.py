"""RAG 切分与重排的纯逻辑测试（不加载向量模型，毫秒级）。

这些用例锁死的是本轮修复的三个真实缺陷：
1. 固定字数切分把「预算参考 + 行程 + 避坑」揉成一块，导致 top-1 检索错
2. 块首没有城市名，六个城市的同名小节在向量空间里混在一起
3. 词法重排未按稀有度加权，通用词「门票」压过了实体「故宫」
"""

import json
import os

from app.rag.indexer import doc_signature, index_stale, split_document
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


# ------------------------------------------------------------ 索引过期检测
# 容器把攻略库放在持久化卷上，镜像里的 knowledge_base/ 更新后旧索引仍在。
# 只判断「索引文件在」会让线上一直用旧攻略回答，本地却一切正常。


def test_index_is_stale_without_meta(tmp_path, monkeypatch):
    """旧版本索引没有 meta.json，无法确认内容，必须按「过期」处理。"""
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    assert index_stale() is True


def test_index_is_fresh_when_signature_matches(tmp_path, monkeypatch):
    from app.config import settings

    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "北京.md").write_text("## 必游景点\n故宫\n", encoding="utf-8")
    monkeypatch.setattr(settings, "kb_dir", str(kb))
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    idx = settings.index_dir
    idx.mkdir(parents=True, exist_ok=True)
    meta = {"built_at": 1.0, "documents": 1, "chunks": 1, "dimension": 512, "docs": doc_signature()}
    (idx / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    assert index_stale() is False


def test_index_goes_stale_after_doc_edit(tmp_path, monkeypatch):
    """改名不算变化，改内容才算 —— 这次补「住宿建议」正是改内容不改文件名。"""
    from app.config import settings

    kb = tmp_path / "kb"
    kb.mkdir()
    doc = kb / "北京.md"
    doc.write_text("## 必游景点\n故宫\n", encoding="utf-8")
    monkeypatch.setattr(settings, "kb_dir", str(kb))
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    idx = settings.index_dir
    idx.mkdir(parents=True, exist_ok=True)
    (idx / "meta.json").write_text(json.dumps({"docs": doc_signature()}), encoding="utf-8")
    assert index_stale() is False

    doc.write_text("## 住宿建议\n王府井一带\n", encoding="utf-8")
    os.utime(doc, (1, 1))  # 显式改 mtime，避免文件系统时间精度导致漏判
    assert index_stale() is True
