"""从中文维基导游（Wikivoyage）dump 提取景点资料，生成本地知识库的「导览档」。

用法
----
    .venv/Scripts/python.exe scripts/fetch_wikivoyage.py --probe     # 只统计，不写文件
    .venv/Scripts/python.exe scripts/fetch_wikivoyage.py             # 解析 dump → datasets/wikivoyage_spots.json
    .venv/Scripts/python.exe scripts/fetch_wikivoyage.py --download   # 先下载 dump 再解析

为什么用 dump 而不是 API
------------------------
`zh.wikivoyage.org/w/api.php` 在国内网络下超时，但 `dumps.wikimedia.org` 镜像可达。
dump 还能保证「同一份输入永远得到同一份输出」—— 可复现是评审时能说清的前提。

数据来源与许可
--------------
中文维基导游（https://zh.wikivoyage.org），正文许可 CC BY-SA 4.0。
派生文档必须保留署名，生成的 Markdown 里写明了来源与许可（见 render_doc）。

为什么只取「景点类小节」
------------------------
维基导游的城市条目里，`== 抵达 ==`、`== 气候 ==`、`== 住宿 ==` 这类小节也大量使用
listing 模板（哈尔滨把机场、火车站都写成了 listing）。全量抓会把交通枢纽当成景点，
检索「哈尔滨有什么好玩的」时第一个命中「哈尔滨西站」。因此按**所在小节标题**过滤，
而不是按模板名 —— 模板名在各城市的写法并不统一（绍兴用 `{{see}}`，哈尔滨用 `{{listing}}`）。
"""

from __future__ import annotations

import argparse
import bz2
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DUMP_URL = "https://dumps.wikimedia.org/zhwikivoyage/latest/zhwikivoyage-latest-pages-articles.xml.bz2"
CACHE_DIR = ROOT / "data" / "wikivoyage_cache"
DUMP_FILE = CACHE_DIR / "zhwikivoyage-latest-pages-articles.xml.bz2"
OUT_FILE = ROOT / "datasets" / "wikivoyage_spots.json"
GEO_FILE = ROOT / "frontend" / "static" / "assets" / "js" / "geo-data.js"

# 「一个地方/一项活动」的模板。字段结构相同：name / address / hours / price / content
LISTING_TEMPLATES = ("see", "do", "listing", "eat", "buy", "drink")

# 景点类小节。只要标题命中其中之一，这一节下的 listing 才算景点。
# 收得比较宽（含「公园」「广场」「故居」），因为维基导游的小节名很自由：
# 绍兴写成「古城 / 西郊 / 西南郊」，扬州直接写「观光」。
SIGHT_SECTION_KEYS = (
    "观光",
    "景点",
    "景区",
    "看",
    "游览",
    "名胜",
    "观光地",
    "风景",
    "公园",
    "古迹",
    "遗址",
    "博物馆",
    "活动",
    "体验",
    "游玩",
    "自然风光",
    "人文景点",
    "see",
    "do",
    "attraction",
)

# 明确要排除的小节（哪怕标题里含「景点」也不取）
SKIP_SECTION_KEYS = (
    "抵达",
    "到达",
    "交通",
    "住宿",
    "用餐",
    "购物",
    "夜生活",
    "安全",
    "医疗",
    "气候",
    "氣候",
    "历史",
    "歷史",
    "了解",
    "区划",
    "區域",
    "下一站",
    "通讯",
    "语言",
)

_NS = "{http://www.mediawiki.org/xml/export-0.11/}"


# ---------------------------------------------------------------- dump 读取


def download(force: bool = False) -> Path:
    """下载 dump（断点续传）。已存在且大小合理则跳过。"""
    import requests

    if DUMP_FILE.exists() and DUMP_FILE.stat().st_size > 10_000_000 and not force:
        print(f"dump 已存在：{DUMP_FILE.stat().st_size / 1048576:.1f} MB")
        return DUMP_FILE
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DUMP_FILE.with_suffix(".bz2.part")
    have = tmp.stat().st_size if tmp.exists() else 0
    headers = {"User-Agent": "travel-copilot-kb/1.0 (graduation project)"}
    if have:
        headers["Range"] = f"bytes={have}-"
        print(f"断点续传，起点 {have} B")
    t0 = time.time()
    with requests.get(DUMP_URL, headers=headers, timeout=300, stream=True) as r:
        if r.status_code == 416:
            tmp.replace(DUMP_FILE)
            return DUMP_FILE
        mode = "ab" if r.status_code == 206 else "wb"
        if mode == "wb":
            have = 0
        with open(tmp, mode) as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    tmp.replace(DUMP_FILE)
    print(f"下载完成 {DUMP_FILE.stat().st_size / 1048576:.1f} MB，{time.time() - t0:.0f}s")
    return DUMP_FILE


def our_cities() -> list[str]:
    """项目覆盖的 355 城（与地图、清单档同一份来源）。"""
    text = GEO_FILE.read_text(encoding="utf-8")
    block = re.search(r"var RAW\s*=\s*\[(.*?)\n\s*\];", text, re.S)
    if not block:
        raise SystemExit(f"无法解析 {GEO_FILE}")
    out: list[str] = []
    for item in re.findall(r'"([^"]*)"', block.group(1)):
        parts = item.split("|")
        if len(parts) >= 4 and parts[0] and parts[0] not in out:
            out.append(parts[0])
    return out


def iter_pages(dump: Path):
    """逐条产出 (标题, 是否重定向, 正文)。主命名空间才产出。"""
    with bz2.open(dump, "rb") as fh:
        for _, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag != _NS + "page":
                continue
            ns_el = elem.find(_NS + "ns")
            nsid = (ns_el.text or "").strip() if ns_el is not None else ""
            if nsid != "0":
                elem.clear()
                continue
            title_el = elem.find(_NS + "title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            redirect = elem.find(_NS + "redirect") is not None
            text_el = elem.find(_NS + "revision/" + _NS + "text")
            body = (text_el.text or "") if text_el is not None else ""
            elem.clear()
            if title:
                yield title, redirect, body


# ---------------------------------------------------------------- wikitext 清洗


def _find_templates(text: str) -> list[tuple[str, str, int]]:
    """扫出 listing 模板，返回 [(模板名, 内部文本, 起始偏移)]。

    用括号深度扫描而不是正则：content 里常嵌套 {{lang|en|...}}，
    正则的非贪婪匹配会在第一个 }} 处截断，把正文切掉一半。
    """
    out: list[tuple[str, str, int]] = []
    i, n = 0, len(text)
    while i < n - 1:
        if text[i] == "{" and text[i + 1] == "{":
            start = i
            depth = 0
            j = i
            while j < n - 1:
                if text[j : j + 2] == "{{":
                    depth += 1
                    j += 2
                    continue
                if text[j : j + 2] == "}}":
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                    continue
                j += 1
            inner = text[start + 2 : j - 2]
            name = re.split(r"[|\n]", inner, maxsplit=1)[0].strip().lower()
            if name in LISTING_TEMPLATES:
                out.append((name, inner, start))
            i = j
        else:
            i += 1
    return out


def _split_params(inner: str) -> dict[str, str]:
    """把模板参数拆成 {键: 值}。只有顶层的 | 才分割。"""
    lines = inner.split("\n", 1)
    head = lines[0]
    body = lines[1] if len(lines) > 1 else ""
    if "|" in head:
        body = head.split("|", 1)[1] + ("\n" + body if body else "")

    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    i = 0
    while i < len(body):
        pair = body[i : i + 2]
        if pair in ("{{", "[[", "{|"):
            depth += 1
            cur.append(pair)
            i += 2
            continue
        if pair in ("}}", "]]", "|}"):
            depth -= 1
            cur.append(pair)
            i += 2
            continue
        if body[i] == "|" and depth <= 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(body[i])
        i += 1
    parts.append("".join(cur))

    out: dict[str, str] = {}
    for p in parts:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip().lower()
        if k:
            out[k] = v.strip()
    return out


def _pick_variant(m: re.Match) -> str:
    """`-{zh-hans:个;zh-hant:個}-` → 个；`-{个}-` → 个。

    这是 MediaWiki 的繁简转换语法，不清掉景点名会变成「-{个}-园」。
    优先取简体变体，没有就取第一个，最后退回原文。
    """
    inner = m.group(1)
    if ":" not in inner:
        return inner
    first = ""
    for part in inner.split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k in ("zh-hans", "zh-cn", "zh-sg"):
            return v
        if not first:
            first = v
    return first or inner


def clean(text: str) -> str:
    """wikitext 片段 → 纯文本。"""
    if not text:
        return ""
    t = text
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<ref[^>]*/>", "", t)
    # 繁简转换标记：-{个}- 表示「不转换」，-{zh-hans:个;zh-hant:個}- 是变体选择。
    # 不清掉的话景点名会变成「-{个}-园」，检索和展示都是错的。
    t = re.sub(r"-\{([^{}]*)\}-", _pick_variant, t)
    t = re.sub(r"\[\[(?:File|Image|文件|图像):[^\]]*\]\]", "", t, flags=re.I)
    t = re.sub(r"\[\[([^\]|]+)\|([^\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\]]+)\]\]", r"\1", t)
    t = re.sub(r"\[(?:https?://\S+)\s+([^\]]+)\]", r"\1", t)
    t = re.sub(r"\[(?:https?://\S+)\]", "", t)
    # 脚注编号：[4] / [12] 是维基的引用标记，不是正文。大连的老虎滩条目里就留着
    # 「…等著名景点[4]。」，直接进回答会显得很怪。
    t = re.sub(r"\[\d{1,3}\]", "", t)
    t = re.sub(r"'''''(.+?)'''''", r"\1", t)
    t = re.sub(r"''(.+?)''", r"\1", t)
    t = re.sub(r"<[^>]+>", " ", t)
    # 残留嵌套模板：{{lang|en|xx}} → xx；其余整体删掉
    for _ in range(3):
        t = re.sub(r"\{\{[^{}]*\|([^{}|]*)\}\}", r"\1", t)
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"[ \t\u00a0]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def clean_section(name: str) -> str:
    """小节标题 → 可展示的地理分组名。

    小节名以前是**原样**存进数据集的，因为它只是内部用来判断「父节是不是景点节」。
    但导览档会把它当分组标题写进正文（`**古城**`），于是维基导游里那些写成链接的
    小节标题就原形毕露了 —— 杭州「景点」下面的小节标题整条是一串官方外链，
    线上正文里就出现 `[https://westlake.hangzhou.gov.cn/… 杭州西湖文化景观]
    [https://web.archive.org/… [页面存档<nowiki>]</nowiki>]`。

    这里按「能不能当地名念出来」来判定：洗完还剩链接/括号/花括号的一律丢弃
    （宁可不分组，也不能把标记漏给用户），过长的也丢弃（那是一句话，不是地名）。
    """
    if not name:
        return ""
    t = clean(name)
    t = re.sub(r"\[[^\]]*\]", "", t)  # 洗不干净的残链：[页面存档 ]
    t = re.sub(r"https?://\S+", "", t)  # 漏网的裸 URL
    t = re.sub(r"[\[\]{}<>]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    # 太长的是「一句话」而不是地名，先按括号/冒号砍掉解释部分再判：
    # 「武陵源（张家界国家森林公园、张家界砂岩峰林国家地质公园）」→「武陵源」。
    if len(t) > 24:
        t = re.split(r"[（(：:]", t, maxsplit=1)[0].strip()
    if not t or len(t) > 24:
        return ""
    if "http" in t.lower() or "nowiki" in t.lower():
        return ""
    return t


def trim(text: str, limit: int) -> str:
    """按句子边界截断，不硬切半句话。"""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("。", "；", "！", "？", "\n"):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + 1]
    return cut.rstrip("，、；： ") + "…"


# ---------------------------------------------------------------- 结构解析


def sections(body: str) -> list[tuple[int, str, str]]:
    """按 `== 标题 ==` 切成 [(层级, 小节名, 正文)]，导语记为 (0, '', ...)。

    层级必须保留：绍兴把景点拆在 `=== 古城 ===`、`=== 西郊 ===` 这些**地理子节**里，
    父节才是 `== 景点 ==`。只按小节名判断会把这些子节全丢掉 —— 实测那样做绍兴
    会一条都提不出来。
    """
    marks = [
        (m.start(), len(m.group(1)), m.group(2).strip())
        for m in re.finditer(r"(?m)^(={2,4})\s*([^=\n]+?)\s*={2,4}\s*$", body)
    ]
    if not marks:
        return [(0, "", body)]
    out: list[tuple[int, str, str]] = []
    if marks[0][0] > 0:
        out.append((0, "", body[: marks[0][0]]))
    for idx, (pos, level, name) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(body)
        line_end = body.find("\n", pos)
        start = line_end + 1 if line_end != -1 else end
        out.append((level, name, body[start:end]))
    return out


def _is_sight_section(name: str) -> bool:
    low = name.lower()
    if any(k in low for k in SKIP_SECTION_KEYS):
        return False
    return any(k in low for k in SIGHT_SECTION_KEYS)


def extract(body: str, content_limit: int = 220) -> list[dict]:
    """从城市条目里提取景点条目。

    小节归属按**父节继承**：`== 景点 ==` 下面的 `=== 古城 ===` 算景点节；
    而 `== 抵达 ==` 下面的 `=== 航空 ===` 不算 —— 哈尔滨把机场、火车站都写成了
    listing，不按父节过滤就会把交通枢纽当景点抓进来。
    """
    items: list[dict] = []
    seen: set[str] = set()
    parent_ok = False
    for level, sec_name, sec_body in sections(body):
        if level <= 2:  # 一级/二级标题：重置父节状态
            parent_ok = _is_sight_section(sec_name)
            take = parent_ok
        else:
            take = parent_ok or _is_sight_section(sec_name)
        if not take:
            continue
        for _tpl, inner, _pos in _find_templates(sec_body):
            p = _split_params(inner)
            name = clean(p.get("name", "")).strip()
            if not name or len(name) > 40:
                continue
            key = re.sub(r"[\s·・\-—（）()]", "", name)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "n": name,
                    "sec": clean_section(sec_name),
                    "addr": clean(p.get("address", "")).strip()[:60],
                    "hours": clean(p.get("hours", "")).strip()[:40],
                    "price": clean(p.get("price", "")).strip()[:30],
                    "desc": trim(clean(p.get("content", "")), content_limit),
                }
            )
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description="从中文维基导游 dump 提取景点资料")
    ap.add_argument("--download", action="store_true", help="先下载 dump")
    ap.add_argument("--probe", action="store_true", help="只统计覆盖情况，不写文件")
    ap.add_argument("--force", action="store_true", help="忽略已有缓存，重新下载")
    args = ap.parse_args()

    if args.download or not DUMP_FILE.exists():
        download(args.force)
    if not DUMP_FILE.exists():
        print("dump 不存在，先跑 --download")
        return 1

    cities = our_cities()
    want = set(cities)
    t0 = time.time()
    result: dict[str, list[dict]] = {}
    for title, redirect, body in iter_pages(DUMP_FILE):
        if redirect or title not in want:
            continue
        items = extract(body)
        if items:
            result[title] = items
    print(f"解析完成 {time.time() - t0:.0f}s")

    n_city = len(result)
    n_item = sum(len(v) for v in result.values())
    with_price = sum(1 for v in result.values() for i in v if i["price"])
    with_hours = sum(1 for v in result.values() for i in v if i["hours"])
    with_desc = sum(1 for v in result.values() for i in v if len(i["desc"]) >= 30)
    print(f"命中城市 {n_city}/{len(cities)}，景点条目 {n_item}")
    if n_item:
        print(f"  有门票 {with_price} ({with_price / n_item * 100:.0f}%)")
        print(f"  有开放时间 {with_hours} ({with_hours / n_item * 100:.0f}%)")
        print(f"  有介绍(≥30字) {with_desc} ({with_desc / n_item * 100:.0f}%)")
        per = sorted((len(v), k) for k, v in result.items())
        print(
            f"  每城条数 最少 {per[0][0]}({per[0][1]}) / 中位 {per[len(per) // 2][0]} / 最多 {per[-1][0]}({per[-1][1]})"
        )
        thin = [k for k, v in result.items() if len(v) < 5]
        print(f"  少于 5 条的城市 {len(thin)} 个")

    if args.probe:
        print("\n--- 绍兴前 6 条 ---")
        for it in result.get("绍兴", [])[:6]:
            print(f"  {it['n']} ｜{it['price'] or '-'}｜{it['hours'] or '-'}｜{it['desc'][:60]}")
        return 0

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"已写入 {OUT_FILE.relative_to(ROOT)}  {OUT_FILE.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
