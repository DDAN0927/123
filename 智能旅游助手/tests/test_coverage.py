"""知识库覆盖边界的测试。

系统里的城市数据分三档：地图 355 城（只有坐标）、景点清单档 349 城（景点名+类型）、
完整攻略档 6 城（门票/开放时间/交通）。这组用例钉死四件事：
1. 城市识别不能误判（「长白山」不是「白山」，「马鞍山」不是「鞍山」）；
2. 两档必须真的分开，不能把清单档当完整攻略对外声称；
3. 问到完全没有资料的城市时，**不能拿别的城市的段落顶包**；
4. 覆盖声明必须真的进到专家提示词里，而不是只写在前端文案上。
"""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from app.agents.base import build_prompt, coverage_scope
from app.config import settings
from app.rag import coverage
from app.rag import retriever as R

REPO = Path(__file__).resolve().parents[1]
REPO_KB = REPO / "knowledge_base"
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


def test_full_tier_is_six(monkeypatch):
    """完整攻略档就是人工精编的 6 城 —— 这一档决定「能不能说门票多少钱」。"""
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    assert set(coverage.full_cities()) == SIX_CITIES


def test_list_tier_covers_the_rest(monkeypatch):
    """清单档 + 导览档补齐剩下的城市，三档并集正好等于地图城市数。"""
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    listed = set(coverage.list_cities())
    guided = set(coverage.guided_cities())
    assert listed and guided, "两档都要有城市，否则分档形同虚设"
    assert not (listed & SIX_CITIES), "精编城市不该再出现在清单档里"
    assert not (guided & SIX_CITIES), "精编城市不该再出现在导览档里"
    assert not (listed & guided), "三档不能重叠，否则同一城市会有两份文档"
    assert set(coverage.kb_cities()) == set(coverage.map_cities())


def test_guided_tier_is_between_full_and_listed(monkeypatch):
    """导览档来自维基导游：有介绍与部分门票，但不是人工精编。

    钉死它的规模，避免某天快照被清空、171 城悄悄退回清单档而没人发现。
    """
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    guided = coverage.guided_cities()
    assert 100 <= len(guided) <= 300, f"导览档城市数异常：{len(guided)}"
    assert "绍兴" in guided, "绍兴在维基导游里有 48 条景点，不该缺席"
    sample = REPO_KB / "guides" / "绍兴.md"
    text = sample.read_text(encoding="utf-8")
    assert "CC BY-SA" in text, "维基导游是 CC BY-SA，派生文档必须保留署名"
    assert "门票" in text or "开放" in text


def test_spots_docs_match_geo_data():
    """清单档必须与地图数据同步。

    349 篇文档是脚本生成的，改地图数据（加城市、改景点名）后忘了重跑脚本，
    线上就会出现「地图上有这个景点、攻略库里没有」的静默不一致。
    """
    spec = importlib.util.spec_from_file_location("gen_city_spots", REPO / "scripts" / "gen_city_spots.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    wanted = mod.plan()
    spots_dir = REPO_KB / "spots"
    stale = [n for n, body in wanted.items() if (spots_dir / n).read_bytes() != body.encode("utf-8")]
    extra = sorted(p.name for p in spots_dir.glob("*.md") if p.name not in wanted)
    assert not stale, f"{len(stale)} 篇清单档与地图数据不一致，请重跑 scripts/gen_city_spots.py"
    assert not extra, f"多余清单档（地图里已没有该城市）：{extra[:5]}"


def test_kb_cities_ignores_non_city_filenames(tmp_path, monkeypatch):
    """「外部攻略-小红书.md」参与检索，但不应让系统声称覆盖了某个城市。"""
    (tmp_path / "北京.md").write_text("# 北京", encoding="utf-8")
    (tmp_path / "外部攻略-小红书.md").write_text("# 攻略", encoding="utf-8")
    monkeypatch.setattr(settings, "kb_dir", str(tmp_path))
    monkeypatch.setattr(R, "_chunks", [])
    assert coverage.kb_cities() == ("北京",)


def test_same_city_in_both_dirs_upgrades_to_full(tmp_path, monkeypatch):
    """两档都有同名城市时按完整攻略算，清单档不能把它降级。"""
    (tmp_path / "北京.md").write_text("# 北京攻略", encoding="utf-8")
    (tmp_path / "spots").mkdir()
    (tmp_path / "spots" / "北京.md").write_text("# 北京清单", encoding="utf-8")
    (tmp_path / "spots" / "哈尔滨.md").write_text("# 哈尔滨清单", encoding="utf-8")
    monkeypatch.setattr(settings, "kb_dir", str(tmp_path))
    monkeypatch.setattr(R, "_chunks", [])
    assert coverage.full_cities() == ("北京",)
    assert coverage.list_cities() == ("哈尔滨",)


# ---------------------------------------------------------------- 城市识别


@pytest.mark.parametrize(
    ("text", "asked", "listed", "uncovered"),
    [
        ("帮我规划北京3天行程", ("北京",), (), ()),
        # 184 城只有清单档：不再算「未收录」，但必须算进「仅清单」
        ("七台河有什么好玩的", ("七台河",), ("七台河",), ()),
        ("北京到七台河怎么走", None, ("七台河",), ()),
        # 地图里也没有的城市：asked 为空，由模型走通用知识
        ("冰岛极光什么时候看", (), (), ()),
        ("三天行程怎么安排", (), (), ()),
        ("今天天气怎么样", (), (), ()),
    ],
)
def test_detect_basic(monkeypatch, text, asked, listed, uncovered):
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect(text)
    if asked is not None:
        assert set(cov.asked) == set(asked)
    assert set(cov.listed) == set(listed)
    assert set(cov.uncovered) == set(uncovered)


def test_alias_maps_to_real_city(monkeypatch):
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect("蓉城火锅哪家强")
    assert cov.asked == ("成都",)
    assert cov.covered == ("成都",)
    assert cov.listed == ()


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


def test_city_without_any_doc_returns_nothing(fake_index):
    """问连清单档都没有的城市，宁可返回空，也不能拿北京/上海的段落冒充。

    这是升级前的真实缺陷：向量相似度被「有什么好玩的」这种通用短语带偏，
    北京段落能过 0.55 阈值，模型于是拿北京资料回答哈尔滨。
    （349 城补了清单档之后，真实的哈尔滨已经能检到自己的清单；这里用空 KB
    目录模拟「地图里有、攻略库里一个档都没有」的极端情况。）
    """
    assert R.search("哈尔滨有什么好玩的", 3) == []


def test_covered_city_still_works(fake_index):
    hits = R.search("北京故宫门票", 2)
    assert hits and hits[0]["doc"] == "北京.md"


def test_mixed_cities_keep_covered_part(fake_index):
    """「北京到哈尔滨怎么走」里北京有资料，不能因为哈尔滨没覆盖就整体丢弃。"""
    hits = R.search("北京到哈尔滨怎么走", 2)
    assert hits and all(h["doc"] == "北京.md" for h in hits)


def test_spots_doc_is_recognised_as_city():
    """清单档的 `spots/哈尔滨.md` 必须被当成「哈尔滨」，否则城市硬约束失效。

    踩过的坑：原来用 `doc.rsplit(".", 1)[0]` 取城市名，分目录后变成
    「spots/哈尔滨」，既匹配不上 query 里的「哈尔滨」，也不在地图城市清单里，
    过滤条件 `stem not in city_docs` 恒为真 —— 约束静默失效，什么都能过。
    """
    assert R._doc_stem("spots/哈尔滨.md") == "哈尔滨"
    assert R._doc_stem("北京.md") == "北京"


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


def test_listed_city_gets_list_tier_block(monkeypatch):
    """只有清单档的城市，提示词必须说「有景点名但没有门票/时间」。

    一刀切说「没有资料」会让模型连景点名都不敢给，反而比清单档本身更差；
    只说「有资料」又会让它顺口编门票价。三档必须分开写。
    """
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect("七台河有什么好玩的").to_dict()
    assert cov["listed"] == ["七台河"]
    assert cov["guided"] == []
    assert cov["uncovered"] == []
    with coverage_scope(cov):
        prompt = build_prompt("你是景点顾问。", context="(资料)")
    assert "景点清单档" in prompt
    assert "七台河" in prompt
    assert "不要编造" in prompt
    # 不能把它当成「完全没收录」——那是补清单档之前的措辞
    assert "未收录" not in prompt


def test_guided_city_gets_guide_tier_block(monkeypatch):
    """有导览档的城市：可以引用门票，但必须声明可能过时、以景区公告为准。"""
    monkeypatch.setattr(settings, "kb_dir", str(REPO_KB))
    cov = coverage.detect("绍兴有什么好玩的").to_dict()
    assert cov["guided"] == ["绍兴"]
    assert cov["listed"] == []
    assert cov["uncovered"] == []
    with coverage_scope(cov):
        prompt = build_prompt("你是景点顾问。", context="(资料)")
    assert "景点导览档" in prompt
    assert "绍兴" in prompt
    assert "以景区最新公告为准" in prompt
    # 导览档不是清单档：不能对它用「只有景点名」的措辞
    assert "景点清单档" not in prompt
    assert "未收录" not in prompt


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
    # 三档要分别对外暴露，前端才能说「6 城精编 + N 城导览 + M 城清单」
    for key in ("full_cities", "full_count", "guided_count", "list_count", "count"):
        assert key in data
    assert data["count"] == data["full_count"] + data["guided_count"] + data["list_count"]


def test_chat_response_carries_coverage(client, admin_headers):
    """同步接口要把覆盖判定带出去，调用方才能判断「这段是攻略库内容还是通用建议」。"""
    r = client.post("/api/chat", json={"message": "北京故宫门票多少钱"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    cov = r.json()["coverage"]
    assert "北京" in cov["asked"]
    assert cov["uncovered"] == []


# ---------------------------------------------------------------- 档位排序


def test_tier_weight_prefers_full_guide():
    """精编攻略权重 1.0，清单档打折 —— 清单档只有景点名，证据强度更低。"""
    assert R._tier_weight("上海.md") == 1.0
    assert R._tier_weight("spots/苏州.md") < 1.0


def test_spots_tier_loses_tie_to_full_guide(monkeypatch):
    """同分时精编攻略必须排前面。

    真实表现（349 城补清单档之后）：「上海去苏州怎么走」的 top-1 变成
    `spots/苏州.md`（0.713）而不是 `上海.md` 的交通指南（0.695）——
    苏州的清单档通篇都是「苏州」所以向量更近，可它根本没有交通信息。
    """
    chunks = [
        {"doc": "spots/苏州.md", "section": "清单", "text": "【苏州】同一条测试文本，内容完全一致"},
        {"doc": "上海.md", "section": "交通", "text": "【上海】同一条测试文本，内容完全一致"},
    ]

    class _EqualIndex:
        def search(self, _qv, k):
            pairs = [(0.70, 0), (0.70, 1)][:k]
            return (
                np.asarray([[p[0] for p in pairs]], dtype="float32"),
                np.asarray([[p[1] for p in pairs]], dtype="int64"),
            )

    monkeypatch.setattr(R, "_chunks", chunks)
    monkeypatch.setattr(R, "_index", _EqualIndex())
    monkeypatch.setattr(R, "_model", _FakeModel())
    monkeypatch.setattr(R, "_gram_idf", R._build_gram_idf(chunks))
    R._search_cached.cache_clear()
    try:
        hits = R.search("同一条测试文本", 2)
    finally:
        R._search_cached.cache_clear()
    assert [h["doc"] for h in hits] == ["上海.md", "spots/苏州.md"]
