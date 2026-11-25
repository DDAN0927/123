"""回答出站前的文字卫生：不许把提示词里的占位符漏给用户。

背景：清单档城市的提示词要教模型「别编门票价」，于是写了
「确需给出时写成『约 X 元 / 通常 X 点开放』」。实测模型会**原样抄进回答**，
用户看到的是「门票：约 X 元」—— 既没有信息量，又暴露了内部提示词。

两道防线：
1. 提示词改成不给占位符模板（改说量级）；
2. 出站统一清洗，模型再抄一次也不会漏出去。

第 2 道是兜底：模型的措辞不可控，不能只靠提示词。
"""

import pytest

from app.api.chat import _strip_placeholders


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 实测到的原文（三门峡问答）
        ("- 门票：约 X 元，请以官方渠道为准", "- 门票：以官方渠道为准"),
        # 没有后半句时也要能替换
        ("门票：约X元", "门票：以景区公告为准"),
        ("门票 X 块", "门票以景区公告为准"),
        # 时间
        ("- 开放时间：通常 X 点开放，请以官方渠道为准", "- 开放时间：以官方渠道为准"),
        ("一般 X 点开门", "以景区公告为准"),
        # 时长（行程表模板里的占位符）
        (
            "- 上午(9:00-12:00): 故宫 — 中轴线（约X小时）",
            "- 上午(9:00-12:00): 故宫 — 中轴线（视行程节奏而定）",
        ),
        ("游玩约 X 小时", "游玩视行程节奏而定"),
    ],
)
def test_placeholder_is_rewritten(raw, expected):
    assert _strip_placeholders(raw) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "故宫门票 60 元，学生半价。",
        "预算约 ¥1200/人",
        "北京 · 上海 · 成都",  # 中文正文里没有字母 X
        "matrix 不是占位符",  # 有 x 但后面不跟单位，不能误伤
        "开放时间 8:30-17:00",
    ],
)
def test_normal_text_untouched(text):
    assert _strip_placeholders(text) == text


def test_coverage_prompt_does_not_hand_model_a_placeholder_template():
    """提示词本身不能再把「约 X 元」当成**推荐写法**递给模型。"""
    from app.agents.base import _coverage_block

    block = _coverage_block({"listed": ["三门峡"], "guided": [], "uncovered": [], "full_cities": ["北京"]})
    assert "绝对不要输出" in block
    assert "量级" in block  # 改成「只给量级」而不是给占位符模板
