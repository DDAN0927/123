"""知识库覆盖边界的测试。

系统里有两套城市数据：地图 355 城（只有坐标）、攻略库 6 城（有门票/开放时间）。
这组用例钉死三件事：
1. 城市识别不能误判（「长白山」不是「白山」，「马鞍山」不是「鞍山」）；
2. 问到没有攻略库的城市时，**不能拿别的城市的段落顶包**；
3. 覆盖声明必须真的进到专家提示词里，而不是只写在前端文案上。
"""

from pathlib import Path

import numpy as np
import pytest

from app.agents.base import build_prompt, coverage_scope
from app.config import settings
from app.rag import coverage
from app.rag import retriever as R

REPO_KB = Path(__file__).resolve().parents[1] / "knowledge_base"
SIX_CITIES = {"上海", "北京", "成都", "杭州", "西安", "重庆"}


@pytest.fixture(autouse=True)
def _fresh_cache():
    coverage.reset_cache()
    yield
    coverage.reset_cache()


# ---------------------------------------------------------------- 城市数据


def test_map_data_is_intact():
    """地图数据解析结果必须与对外文案一致（355 城 / 1558 景点）。"""
    assert len(coverage.map_cities()) == 355
    assert coverage.map_spot_count() == 1558


def test_kb_cities_are_six(monkeypatch):
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    assert set(coverage.kb_cities()) == SIX_CITIES


def test_kb_cities_ignores_non_city_filenames(tmp_path, monkeypatch):
    """「外部攻略-小红书.md」参与检索，但不应让系统声称覆盖了某个城市。"""
    (tmp_path / "北京.md").write_text("# 北京", encoding="utf-8")
    (tmp_path / "外部攻略-小红书.md").write_text("# 攻略", encoding="utf-8")
    monkeypatch.setattr(settings, "kb_dir", str(tmp_path))
    monkeypatch.setattr(R, "_chunks", [])
    assert coverage.kb_cities() == ("北京",)


# ---------------------------------------------------------------- 城市识别


@pytest.mark.parametrize(
    ("text", "asked", "uncovered"),
    [
        ("帮我规划北京3天行程", ("北京",), ()),
        ("哈尔滨有什么好玩的", ("哈尔滨",), ("哈尔滨",)),
        ("北京到哈尔滨怎么走", None, ("哈尔滨",)),  # 两个城市，只断言未覆盖集合
        ("三天行程怎么安排", (), ()),
        ("今天天气怎么样", (), ()),
    ],
)
def test_detect_basic(monkeypatch, text, asked, uncovered):
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect(text)
    if asked is not None:
        assert set(cov.asked) == set(asked)
    assert set(cov.uncovered) == set(uncovered)


def test_alias_maps_to_real_city(monkeypatch):
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect("蓉城火锅哪家强")
    assert cov.asked == ("成都",)
    assert cov.uncovered == ()


@pytest.mark.parametrize("text", ["长白山怎么去", "峨眉山值得去吗"])
def test_longer_place_names_do_not_trigger_city(monkeypatch, text):
    """「长白山」不能算作吉林白山市，「峨眉山」不能算作四川眉山市。"""
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect(text)
    assert "白山" not in cov.asked
    assert "眉山" not in cov.asked


def test_longest_match_wins(monkeypatch):
    """「马鞍山」是城市，「鞍山」也是城市，不能因为短名包含关系把两者混为一谈。"""
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect("马鞍山有什么景点")
    assert cov.asked == ("马鞍山",)


# ---------------------------------------------------------------- 检索边界


CHUNKS = [
    {"doc": "北京.md", "section": "故宫", "text": "【北京】故宫 门票 60 元，需提前实名预约"},
    {"doc": "上海.md", "section": "交通", "text": "【上海】去苏州可乘高铁，约 30 分钟"},
]


class _FakeIndex:
    def search(self, _qv, k):
        pairs = [(0.85, 0), (0.80, 1)][:k]
        return (
            np.asarray([[p[0] for p in pairs]], dtype="float32"),
            np.asarray([[p[1] for p in pairs]], dtype="int64"),
        )


class _FakeModel:
    def encode(self, _texts, normalize_embeddings=True):
        return np.zeros((1, 8), dtype="float32")


@pytest.fixture
def fake_index(monkeypatch):
    monkeypatch.setattr(R, "_chunks", CHUNKS)
    monkeypatch.setattr(R, "_index", _FakeIndex())
    monkeypatch.setattr(R, "_model", _FakeModel())
    monkeypatch.setattr(R, "_gram_idf", R._build_gram_idf(CHUNKS))
    R._search_cached.cache_clear()
    yield
    R._search_cached.cache_clear()


def test_uncovered_city_returns_nothing(fake_index):
    """问没有攻略库的城市，宁可返回空，也不能拿北京/上海的段落冒充。

    这是升级前的真实缺陷：向量相似度被「有什么好玩的」这种通用短语带偏，
    北京段落能过 0.55 阈值，模型于是拿北京资料回答哈尔滨。
    """
    assert R.search("哈尔滨有什么好玩的", 3) == []


def test_covered_city_still_works(fake_index):
    hits = R.search("北京故宫门票", 2)
    assert hits and hits[0]["doc"] == "北京.md"


def test_mixed_cities_keep_covered_part(fake_index):
    """「北京到哈尔滨怎么走」里北京有资料，不能因为哈尔滨没覆盖就整体丢弃。"""
    hits = R.search("北京到哈尔滨怎么走", 2)
    assert hits and all(h["doc"] == "北京.md" for h in hits)


# ---------------------------------------------------------------- 提示词注入


def test_coverage_note_is_injected(monkeypatch):
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect("哈尔滨有什么好玩的").to_dict()
    with coverage_scope(cov):
        prompt = build_prompt("你是景点顾问。", context="(知识库未收录)")
    assert "知识库覆盖边界" in prompt
    assert "哈尔滨" in prompt
    # 边界说明必须在被围栏的资料**之前**，否则会被当成附注忽略
    assert prompt.index("知识库覆盖边界") < prompt.index("<<<资料开始>>>")


def test_no_note_when_covered(monkeypatch):
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect("北京3天行程").to_dict()
    with coverage_scope(cov):
        prompt = build_prompt("你是景点顾问。", context="资料")
    assert "知识库覆盖边界" not in prompt


def test_scope_does_not_leak():
    """with 块结束后必须复位，否则下一个请求会被上一个请求的城市污染。"""
    with coverage_scope({"uncovered": ["哈尔滨"], "kb_cities": ["北京"]}):
        assert build_prompt("x") != "x"
    assert "知识库覆盖边界" not in build_prompt("x")


# ---------------------------------------------------------------- 对外接口


def test_coverage_endpoint_is_public(client):
    r = client.get("/api/knowledge/coverage")
    assert r.status_code == 200
    data = r.json()
    assert data["map_cities"] == 355
    assert data["map_spots"] == 1558
    assert isinstance(data["cities"], list)


def test_chat_response_carries_coverage(client, admin_headers):
    """同步接口要把覆盖判定带出去，调用方才能判断「这段是攻略库内容还是通用建议」。"""
    r = client.post("/api/chat", json={"message": "北京故宫门票多少钱"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    cov = r.json()["coverage"]
    assert "北京" in cov["asked"]
    assert cov["uncovered"] == []
