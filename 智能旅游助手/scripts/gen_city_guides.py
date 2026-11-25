"""把维基导游快照生成为知识库「导览档」文档。

用法
----
    .venv/Scripts/python.exe scripts/gen_city_guides.py           # 生成/更新
    .venv/Scripts/python.exe scripts/gen_city_guides.py --check   # 只校验是否同步
    .venv/Scripts/python.exe scripts/gen_city_guides.py --clean   # 删除全部导览档

为什么单独一档
--------------
现有两档是「人工精编 6 城」和「只有景点名的清单 349 城」，中间缺一档：
**有真实介绍、门票、开放时间，但不是人工精编**。中文维基导游正好填这个空。

实测它能提供 262 城 / 3193 条景点，其中 883 条有实质介绍、725 条带门票、
487 条带开放时间。这些数据清单档完全没有 —— 清单档只有名字。

为什么不是替换清单档
--------------------
维基导游的条目分布极不均匀：绍兴有 48 条、青岛有 152 条，但青岛 152 条里只有
2 条写了介绍（其余是裸名字）。而清单档有 9213 个景点名。两者互补：
导览档给深度，清单档给广度。所以导览档文档 = 「详解条目 + 该城其余景点名单」。

分档靠目录：`knowledge_base/guides/`。索引器用 `Path(doc).stem` 作城市名，
文件名里塞后缀会让城市识别失效（见 app/rag/coverage.py 的注释）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gen_city_spots import (
    KIND_CN,
    _dedupe_suffix,
    _norm,
    load_extras,
    parse_geo,
)

WV_FILE = ROOT / "datasets" / "wikivoyage_spots.json"
GUIDES_DIR = ROOT / "knowledge_base" / "guides"

# 详解条目的门槛：至少满足其一，否则这条只是裸名字，清单档里已经有了
MIN_DESC = 30
MAX_DETAILS = 12  # 每城详解条目上限
DESC_LIMIT = 160  # 单条介绍截断长度（按句子边界）

# 这些小节名是「类别」不是「地点」，当成地理分组显示没有信息量
_GENERIC_SECTION = (
    "观光",
    "景点",
    "景区",
    "游览",
    "看",
    "名胜",
    "活动",
    "体验",
    "游玩",
    "自然风光",
    "人文景点",
    "景点与地标",
)


def trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("。", "；", "！", "？"):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + 1]
    return cut.rstrip("，、；： ") + "…"


def substantive(item: dict) -> bool:
    """这条值不值得写进详解：有介绍、有门票、或有开放时间。"""
    return len(item.get("desc", "")) >= MIN_DESC or bool(item.get("price")) or bool(item.get("hours"))


def load_wikivoyage() -> dict[str, list[dict]]:
    if not WV_FILE.exists():
        return {}
    return json.loads(WV_FILE.read_text(encoding="utf-8"))


def _amap_index() -> dict[str, dict[str, dict]]:
    """{城市: {归一化景点名: 高德条目}}，用于补评分与地址。"""
    path = ROOT / "datasets" / "amap_spots.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {city: {_norm(s["n"]): s for s in items if s.get("n")} for city, items in raw.items()}


def _detail_line(item: dict, amap: dict | None) -> list[str]:
    """一条详解：标题行（名称 + 门票 + 地址 + 评分）+ 缩进的介绍行。"""
    bits = [f"**{item['n']}**"]
    if item.get("price"):
        bits.append(f"门票 {item['price']}")
    addr = item.get("addr") or (amap or {}).get("addr", "")
    if addr:
        bits.append(addr)
    if item.get("hours"):
        bits.append(f"开放 {item['hours']}")
    rating = (amap or {}).get("rating", "")
    if rating:
        bits.append(f"评分 {rating}")
    lines = ["- " + "｜".join(bits)]
    desc = trim(item.get("desc", ""), DESC_LIMIT)
    if desc:
        # 缩进两格 → Markdown 里是同一个列表项的续行，不会另起一条
        lines.append(f"  {desc}")
    return lines


def _safe_section(sec: str) -> str:
    """分组名兜底过滤。

    数据层（`fetch_wikivoyage.clean_section`）已经洗过一遍，这里再挡一次：
    快照文件是**入库的**，换人重新抓时可能带进旧版本的脏值。分组名会直接写进
    正文给用户看，一旦漏了就是一条裸露的 URL —— 这类问题在检索评估里查不出来，
    只有人眼能看到。
    """
    if not sec or len(sec) > 24:
        return ""
    if re.search(r"https?://|[\[\]{}<>]|nowiki", sec):
        return ""
    return sec


def render(city: str, details: list[dict], rest: list[tuple[str, str]], amap: dict[str, dict]) -> str:
    """生成一座城市的导览档正文。纯函数：同样输入永远同样字节。"""
    lines = [
        f"# {city}景点导览",
        "",
        "> 数据来源：中文维基导游（CC BY-SA 4.0）与高德地图 POI，由脚本整理生成。",
        "> 门票、开放时间等易变信息可能已变动，出行前请以景区官方渠道为准。",
        "",
        f"## {city}景点详解",
    ]
    if details:
        lines.append(f"以下 {len(details)} 处景点有较完整的介绍，按地理位置分组排列。")
        lines.append("")
        last_sec = None
        for item in details:
            sec = _safe_section(item.get("sec") or "")
            # 小节名本身是地理线索（「古城」「西郊」），单独起一行当分组提示，
            # 但用粗体行而不是标题，避免被索引器切成独立块。
            # 「观光」「景点」这类是类别不是地点，显示出来等于噪音。
            if sec and sec != last_sec and not any(g in sec for g in _GENERIC_SECTION):
                lines.append(f"**{sec}**")
                last_sec = sec
            lines += _detail_line(item, amap.get(_norm(item["n"])))
    else:
        lines.append("（暂无详细介绍）")

    if rest:
        lines += ["", f"## {city}其他景点"]
        names = "、".join(f"{n}（{KIND_CN.get(k, k)}）" for n, k in rest)
        lines.append(f"此外还收录 {len(rest)} 个景点：{names}。")
    lines.append("")
    return "\n".join(lines)


def plan() -> dict[str, str]:
    """{文件名: 正文}"""
    wv = load_wikivoyage()
    if not wv:
        return {}
    geo = parse_geo()
    extras = load_extras()
    amap = _amap_index()

    out: dict[str, str] = {}
    for city, items in wv.items():
        details = [i for i in items if substantive(i)][:MAX_DETAILS]
        if not details:
            continue  # 一条有内容的都没有 → 不值得单独成档，留给清单档

        detailed_keys = {_norm(i["n"]) for i in details}
        # 其余景点：地图数据 + 外部补充，去掉已经在详解里出现过的。
        # 复用清单档的 _dedupe_suffix：「仓桥直街」和「仓桥直街历史街区」不该并列出现。
        seen: set[str] = set(detailed_keys)
        geo_kept: list[tuple[str, str]] = []
        for name, kind in geo.get(city, []):
            key = _norm(name)
            if not key or key in seen:
                continue
            seen.add(key)
            geo_kept.append((name, kind))
        extra_kept: list[tuple[str, str]] = []
        for name, kind, _label in extras.get(city, []):
            key = _norm(name)
            if not key or key in seen:
                continue
            seen.add(key)
            extra_kept.append((name, kind))
        rest = geo_kept + _dedupe_suffix(geo_kept, extra_kept)
        out[f"{city}.md"] = render(city, details, rest, amap.get(city, {}))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="生成维基导游导览档")
    ap.add_argument("--check", action="store_true", help="只校验是否同步")
    ap.add_argument("--clean", action="store_true", help="删除全部导览档")
    args = ap.parse_args()

    if args.clean:
        n = 0
        for f in GUIDES_DIR.glob("*.md"):
            f.unlink()
            n += 1
        print(f"已删除 {n} 个导览档")
        return 0

    wanted = plan()
    if not wanted:
        print("✗ 没有可生成的导览档（datasets/wikivoyage_spots.json 缺失或为空）")
        print("  先跑：.venv/Scripts/python.exe scripts/fetch_wikivoyage.py --download")
        return 1

    if args.check:
        stale = []
        for name, body in wanted.items():
            f = GUIDES_DIR / name
            if not f.exists() or f.read_bytes() != body.encode("utf-8"):
                stale.append(name)
        extra = [p.name for p in GUIDES_DIR.glob("*.md")] if GUIDES_DIR.is_dir() else []
        extra = [n for n in extra if n not in wanted]
        if stale or extra:
            print(f"✗ 导览档不同步：{len(stale)} 个需更新，{len(extra)} 个多余")
            for n in (stale + extra)[:8]:
                print(f"    {n}")
            print("  修复：.venv/Scripts/python.exe scripts/gen_city_guides.py")
            return 1
        print(f"✓ {len(wanted)} 个导览档与快照一致")
        return 0

    GUIDES_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for name, body in wanted.items():
        f = GUIDES_DIR / name
        data = body.encode("utf-8")
        if f.exists() and f.read_bytes() == data:
            continue
        with open(f, "wb") as fp:  # 显式二进制写：Windows 默认会把 \n 写成 \r\n
            fp.write(data)
        written += 1
    removed = 0
    for f in GUIDES_DIR.glob("*.md"):
        if f.name not in wanted:
            f.unlink()
            removed += 1

    total = sum(len(v) for v in wanted.values())
    sizes = sorted(len(v) for v in wanted.values())
    print(f"完成：{len(wanted)} 城导览档，写入 {written} 个，清理 {removed} 个")
    print(
        f"  总字数 {total / 10000:.1f} 万，单城 最短 {sizes[0]} / 中位 {sizes[len(sizes) // 2]} / 最长 {sizes[-1]} 字"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
