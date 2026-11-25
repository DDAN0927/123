"""为地图里有、但还没有精编攻略的城市生成「景点清单」基础档文档。

用法
----
    .venv/Scripts/python.exe scripts/gen_city_spots.py          # 生成/更新
    .venv/Scripts/python.exe scripts/gen_city_spots.py --check   # 只校验是否与地图数据同步
    .venv/Scripts/python.exe scripts/gen_city_spots.py --clean   # 删掉全部清单档

为什么要有这一档
----------------
地图数据里有 355 城 / 1558 个景点，但精编攻略只有 6 城。用户问「哈尔滨有什么好玩的」，
检索拿不到任何资料，模型退回通用知识，而用户以为看的是攻略库内容。补一份**只含
景点名与类型**的清单，至少让「这个城市有哪些景点」这件事有据可依。

为什么清单档单独放 `knowledge_base/spots/`
------------------------------------------
`knowledge_base/*.md` 是人工精编档（门票、开放时间、交通、行程），`spots/` 是机器
生成档。分目录而不是加文件名后缀，是因为索引器用 `Path(doc).stem` 作城市名、
检索器用它做城市硬约束 —— 目录能分层，文件名加后缀会把城市名变成
「哈尔滨-景点清单」，城市识别直接失效。

为什么一个城市只写一节
----------------------
`app/rag/indexer.py` 按 Markdown 标题切块，一节就是一个检索单元。清单档本来就只有
一屏内容，拆成多节会让同一个城市在索引里重复出现，白占 top-k 名额。

内容纪律
--------
**只写真实存在的景点名与类型**，不编造门票、开放时间、交通方式 ——
这些正是「看起来像攻略、其实是编的」最容易出事的地方。文档里显式写明这一点，
提示词层也会据此约束模型（见 `app/agents/base.py:_coverage_block`）。

景点名有两个来源：内置地图数据（人工校对，地图页展示的就是这批）与
OpenStreetMap（`datasets/osm_spots.json`，由 `scripts/fetch_osm_spots.py` 抓取，
只保留带 wikidata 条目的知名景点，已过滤游乐设施与配套设施噪声）。
两者都不提供门票与开放时间，因此这一档的措辞始终是「清单」而不是「攻略」。
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GEO_FILE = ROOT / "frontend" / "static" / "assets" / "js" / "geo-data.js"
KB_DIR = ROOT / "knowledge_base"
SPOTS_DIR = KB_DIR / "spots"
# 外部数据源快照，由 scripts/fetch_osm_spots.py / fetch_amap_spots.py 生成。
# 放在 datasets/ 而不是 data/：data/ 是 gitignore 的运行时目录，
# 这份快照必须进仓库，否则别人 clone 下来重跑会得到不同的清单档。
# 高德在前（国内覆盖更好、有地址与评分），OSM 在后作为无 key 时的兜底。
EXTRA_FILES = (
    (ROOT / "datasets" / "amap_spots.json", "高德"),
    (ROOT / "datasets" / "osm_spots.json", "OpenStreetMap"),
)

# 类型中文名。地图数据里的分类是固定的 11 个（见 geo-data.js 文件头注释），
# 未知分类原样输出，免得新增分类时静默丢信息。
KIND_CN = {
    "地标": "地标",
    "古迹": "古迹",
    "公园": "公园",
    "街区": "街区",
    "商圈": "商圈",
    "自然": "自然风光",
    "乐园": "主题乐园",
    "亲子": "亲子",
    "体验": "体验项目",
    "场馆": "场馆",
    "美食": "美食",
}


def parse_geo() -> dict[str, list[tuple[str, str]]]:
    """解析 geo-data.js，返回 {城市名: [(景点名, 分类), ...]}"""
    text = GEO_FILE.read_text(encoding="utf-8")
    block = re.search(r"var RAW\s*=\s*\[(.*?)\n\s*\];", text, re.S)
    if not block:
        raise SystemExit(f"无法解析 {GEO_FILE}（找不到 var RAW = [...]）")
    out: dict[str, list[tuple[str, str]]] = {}
    for item in re.findall(r'"([^"]*)"', block.group(1)):
        parts = item.split("|")
        if len(parts) < 4:
            continue
        city = parts[0]
        spots = []
        for raw in parts[3:]:
            fields = raw.split(",")
            if len(fields) >= 4 and fields[0]:
                spots.append((fields[0], fields[3]))
        if spots:
            out[city] = spots
    return out


def full_cities() -> set[str]:
    """已经有精编攻略的城市（`knowledge_base/*.md`），不生成清单档。"""
    return {p.stem for p in KB_DIR.glob("*.md")}


def load_extras() -> dict[str, list[tuple[str, str, str]]]:
    """外部补充景点 {城市: [(名称, 分类, 来源名)]}，按 EXTRA_FILES 顺序合并。

    文件不存在时返回空——没有这些快照也能正常生成，退回纯地图数据的旧行为。
    """
    out: dict[str, list[tuple[str, str, str]]] = {}
    for path, label in EXTRA_FILES:
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        for city, items in raw.items():
            bucket = out.setdefault(city, [])
            for s in items:
                if s.get("n"):
                    bucket.append((s["n"], s["k"], label))
    return out


def _norm(name: str) -> str:
    """去重用的归一化：去括号备注、去间隔号与空白。"""
    n = re.sub(r"[（(][^）)]*[）)]", "", name)
    return re.sub(r"[\s·・\-—]", "", n)


# 高德会把「亚龙湾」和「亚龙湾海滩」「西湖」和「西湖景区」当成两条 POI，
# 清单里并列出现就显得很业余。但只合并**短名 + 通用后缀**这一种：
# 「故宫」/「故宫博物院」、「西湖」/「西湖国宾馆」这类必须都留着，它们是两个地方。
_GENERIC_SUFFIX = (
    "风景名胜区",
    "国家森林公园",
    "历史文化街区",
    "旅游度假区",
    "风景旅游区",
    "文化旅游区",
    "旅游景区",
    "森林公园",
    "湿地公园",
    "遗址公园",
    "风景区",
    "旅游区",
    "景区",
    "公园",
    "广场",
    "海滩",
    "沙滩",
    "观景台",
)


def _dedupe_suffix(base: list[tuple[str, str]], extra: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """丢掉「短名 + 通用后缀」的长名版本，保留短名。

    `base`（地图数据）原样保留，只对 `extra`（外部补充）做删减——
    地图那批是人工校对过的，不能被机器规则删掉。
    """
    keys = {_norm(n) for n, _ in base} | {_norm(n) for n, _ in extra}
    out: list[tuple[str, str]] = []
    for name, kind in extra:
        key = _norm(name)
        drop = False
        for suf in _GENERIC_SUFFIX:
            if key.endswith(suf) and len(key) > len(suf) and key[: -len(suf)] in keys:
                drop = True
                break
        if not drop:
            out.append((name, kind))
    return out


def merge(
    city: str, geo: list[tuple[str, str]], extras: list[tuple[str, str, str]]
) -> tuple[list, int, list[str]]:
    """地图景点在前（保持原顺序），外部补充在后（保持数据源自身的排序）。

    返回 (合并后的列表, 实际新增条数, 用到的来源名)。外部数据只补名字，不改地图数据本身——
    地图页展示的仍是人工校对过的那批景点，避免把地图铺满未经筛选的 POI。

    **高德优先、命中即止**：高德每城能给 24 条带评分与营业时间的 POI，质量明显高于
    OSM 的裸名字；一旦高德已经覆盖该城，就不再拿 OSM 的条目去稀释它。
    OSM 只在「没有高德数据」时兜底（没配 Key 或该城高德无结果）。
    """
    seen = {_norm(n) for n, _ in geo}
    extra: list[tuple[str, str]] = []
    used: list[str] = []
    for name, kind, label in extras:
        if used and label not in used:
            break  # 前一个数据源已经贡献过条目，后面的不再混入
        key = _norm(name)
        if not key or key in seen:
            continue
        seen.add(key)
        extra.append((name, kind))
        if label not in used:
            used.append(label)
    kept = _dedupe_suffix(geo, extra)
    return geo + kept, len(kept), used


def render(
    city: str, spots: list[tuple[str, str]], osm_added: int = 0, sources: list[str] | None = None
) -> str:
    """生成一座城市的清单档正文。纯函数：同样的输入永远得到同样的字节。"""
    kinds = Counter(k for _, k in spots)
    # 类型按出现次数降序、同次数按名称升序 —— 保证输出稳定，避免每次重跑产生 diff
    dist = "、".join(
        f"{KIND_CN.get(k, k)} {n}" for k, n in sorted(kinds.items(), key=lambda x: (-x[1], x[0]))
    )
    lines = [
        f"# {city}景点清单（基础档）",
        "",
        f"## {city}景点清单",
        f"{city}共收录 {len(spots)} 个景点，类型分布：{dist}。",
    ]
    for name, kind in spots:
        lines.append(f"- {name}（{KIND_CN.get(kind, kind)}）")
    source = "内置地图数据"
    extra_note = ""
    if osm_added and sources:
        credit = " / ".join(sources)
        if "OpenStreetMap" in sources:
            credit = credit.replace(
                "OpenStreetMap", "OpenStreetMap（© OpenStreetMap contributors，ODbL 许可）"
            )
        # 中文来源直接接「与」，拉丁字母来源补一个空格，免得「与OpenStreetMap」糊在一起
        source += ("与 " if credit[0].isascii() else "与") + credit
        extra_note = f"，其中 {osm_added} 个为外部补充"
    lines += [
        "",
        f"> 本页为「景点清单」基础档：只提供景点名称与类型，来源为{source}{extra_note}；"
        "**不含**门票价格、开放时间、交通方式与行程建议。这些易变信息请以官方渠道为准。",
        "",
    ]
    return "\n".join(lines)


def plan() -> dict[str, str]:
    """{文件名: 正文} —— 需要生成的全部清单档。"""
    skip = full_cities()
    extras = load_extras()
    out: dict[str, str] = {}
    for city, geo in parse_geo().items():
        if city in skip:
            continue
        spots, added, sources = merge(city, geo, extras.get(city, []))
        out[f"{city}.md"] = render(city, spots, added, sources)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 349 城景点清单基础档")
    ap.add_argument("--check", action="store_true", help="只校验是否与地图数据同步（不写文件）")
    ap.add_argument("--clean", action="store_true", help="删除全部清单档")
    args = ap.parse_args()

    if args.clean:
        removed = 0
        for f in SPOTS_DIR.glob("*.md"):
            f.unlink()
            removed += 1
        print(f"已删除 {removed} 个清单档")
        return 0

    wanted = plan()

    if args.check:
        stale = []
        for name, body in wanted.items():
            f = SPOTS_DIR / name
            # 比字节而不是比文本：Windows 上 write_text 默认会把 \n 转成 \r\n，
            # 文件进 git 后跟 Linux 生成的结果不一致，比对文本却看不出来。
            if not f.exists() or f.read_bytes() != body.encode("utf-8"):
                stale.append(name)
        extra = [p.name for p in SPOTS_DIR.glob("*.md") if p.name not in wanted] if SPOTS_DIR.is_dir() else []
        if stale or extra:
            print(f"✗ 清单档与地图数据不同步：{len(stale)} 个需更新，{len(extra)} 个多余")
            for name in (stale + extra)[:10]:
                print(f"    {name}")
            print("  修复：.venv/Scripts/python.exe scripts/gen_city_spots.py")
            return 1
        print(f"✓ {len(wanted)} 个清单档与地图数据一致")
        return 0

    SPOTS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for name, body in wanted.items():
        f = SPOTS_DIR / name
        data = body.encode("utf-8")
        # 内容相同就不碰 mtime：否则每次重跑都会让 doc_signature 变化，
        # 触发一次没必要的全量重建索引。
        if f.exists() and f.read_bytes() == data:
            continue
        # 显式 newline="\n"：不加的话 Windows 会写 CRLF，而镜像里是 LF，
        # 同一份清单在两处字节不同，start.sh 的 cmp 会判定「有更新」而反复覆盖。
        with open(f, "wb") as fp:
            fp.write(data)
        written += 1
    removed = 0
    for f in SPOTS_DIR.glob("*.md"):
        if f.name not in wanted:
            f.unlink()
            removed += 1
    print(f"完成：共 {len(wanted)} 城清单档，本次写入 {written} 个，清理 {removed} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
