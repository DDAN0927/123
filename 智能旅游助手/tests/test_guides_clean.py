"""导览档正文洁净度：攻略文档是要直接念给用户看的，不能带 wiki 标记。

为什么单独一组
--------------
导览档是从维基导游 dump 自动生成的 171 篇文档，清洗逻辑有十几个正则，任何一个
漏掉都不会让程序报错 —— 索引照建、检索照跑、评估指标一分不掉，只有**人眼**
读回答时才看到「[https://westlake.hangzhou.gov.cn/… 杭州西湖文化景观]」这种东西。

已经踩过两次：
  * 小节标题原样进正文 → 杭州出现一长串官方外链 + `<nowiki>` 残片；
  * 脚注编号没洗 → 大连「…等著名景点[4]。」。

所以这里对**生成结果**做静态扫描，而不是只测清洗函数：函数改对了但某条路径没走
清洗，照样会被抓住。
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "knowledge_base" / "guides"
SPOTS = ROOT / "knowledge_base" / "spots"

# 标记 → 说明（正则会命中任何一篇就算失败）
RESIDUE = {
    "裸链接": (r"https?://", "正文里露出了 URL"),
    "方括号": (r"[\[\]]", "残留 wiki 链接括号"),
    "花括号": (r"[{}]", "残留模板标记"),
    "nowiki": (r"(?i)nowiki", "残留 <nowiki> 标签"),
    "脚注编号": (r"\[\d{1,3}\]", "残留维基脚注 [4]"),
}


def _docs():
    out = []
    for d in (GUIDES, SPOTS):
        if d.is_dir():
            out += sorted(d.glob("*.md"))
    return out


def test_guides_exist():
    """没生成过导览档时，下面的扫描会「空跑通过」。"""
    assert GUIDES.is_dir(), "缺少 knowledge_base/guides/，先跑 scripts/gen_city_guides.py"
    assert len(list(GUIDES.glob("*.md"))) >= 150, "导览档数量异常，生成可能没跑完"


@pytest.mark.parametrize("label,pattern,why", [(k, v[0], v[1]) for k, v in RESIDUE.items()])
def test_no_wiki_residue(label, pattern, why):
    """所有自动生成的攻略文档里都不该出现 wiki 标记。"""
    bad = []
    for p in _docs():
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(pattern, text):
            bad.append(p.stem)
    assert not bad, f"{label}（{why}）出现在 {len(bad)} 篇：{bad[:8]}"


def test_section_names_are_short():
    """分组名（`**古城**` 这种粗体行）必须像地名，不能是一整句话或一串链接。"""
    bad = []
    for p in GUIDES.glob("*.md") if GUIDES.is_dir() else []:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("**") and line.endswith("**") and len(line) > 4:
                name = line[2:-2]
                if len(name) > 24 or "http" in name.lower():
                    bad.append(f"{p.stem}:{name[:40]}")
    assert not bad, f"{len(bad)} 处分组名不像地名：{bad[:5]}"
