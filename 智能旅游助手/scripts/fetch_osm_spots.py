"""从 OpenStreetMap（Overpass API）抓取各城市的知名景点，补充攻略库的「景点清单」档。

为什么用 OSM
------------
知识库里 349 城只有「景点名 + 类型」，每城 3~7 个，且全部来自内置地图数据。
问「杭州有什么好玩的」，能检索到的景点太少，模型只能补通用知识。
OSM 是免费、可商用（ODbL）、有中文名的开放数据，能把这个清单从 4 个扩到十几个。

为什么不直接全量抓 tourism=*
--------------------------------
试过：杭州 25km 内 tourism=attraction 有 160 条，其中大量是「十二生肖石」
「江湖汇观亭」「马可波罗像」这类微 POI。全量塞进知识库只会让检索变差。
因此**只保留带 `wikidata` 标签的条目** —— 有维基数据条目意味着这个对象
被独立收录过，是「值得写进攻略」的景点，噪声显著下降（杭州降到 33 条）。

为什么不抓门票和开放时间
------------------------
OSM 里中国景点的 opening_hours / fee 标签几乎为空（实测 156 条里 0 条有值）。
硬凑就是编造，违反清单档的内容纪律。这些字段留给人工精编档或高德 POI。

用法
----
    .venv/Scripts/python.exe scripts/fetch_osm_spots.py            # 全量（约 40 分钟）
    .venv/Scripts/python.exe scripts/fetch_osm_spots.py --limit 40 # 只抓前 40 城（试跑）
    .venv/Scripts/python.exe scripts/fetch_osm_spots.py --reset    # 丢弃缓存重抓

产物
----
    datasets/osm_spots.json      {城市: [{n: 名称, k: 分类, wd: QID, lat, lon}]}
    data/osm_cache/*.json        原始响应缓存（gitignore），断点续跑靠它

抓完记得跑 `scripts/gen_city_spots.py` 把清单档重新生成。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO_FILE = ROOT / "frontend" / "static" / "assets" / "js" / "geo-data.js"
OUT_FILE = ROOT / "datasets" / "osm_spots.json"
CACHE_DIR = ROOT / "data" / "osm_cache"

ENDPOINT = "https://overpass-api.de/api/interpreter"
# Overpass 使用条款要求可识别的 UA，缺了直接 406。
UA = "travel-copilot-kb/1.0 (graduation project; https://github.com/DDAN0927)"

BATCH = 5  # 一次查询合并 5 个城市，把 355 城压到 71 次请求
RADIUS = 30000  # 米。城市中心 30km 基本覆盖主城区 + 近郊景区
TIMEOUT = 120  # 单次请求秒数
DELAY = 2.0  # 请求间隔，别把公共实例打挂

TOURISM_RE = "^(attraction|museum|viewpoint|zoo|theme_park|gallery|aquarium)$"

# OSM 的 tourism 取值 → 地图数据里固定的 11 个分类（见 geo-data.js 文件头）
KIND_MAP = {
    "museum": "场馆",
    "gallery": "场馆",
    "aquarium": "场馆",
    "zoo": "亲子",
    "theme_park": "乐园",
    "viewpoint": "自然",
    "attraction": "地标",
}

# 名字里带这些词的，基本是配套设施而不是景点。宁可漏，不可错。
NOISE_WORDS = (
    "酒店",
    "宾馆",
    "饭店",
    "招待所",
    "公寓",
    "小区",
    "停车场",
    "售票",
    "入口",
    "出口",
    "厕所",
    "公交",
    "地铁",
    "车站",
    "码头",
    "游客中心",
    "服务中心",
    "派出所",
    "银行",
    "加油站",
    "充电站",
    "便利店",
    "超市",
    "餐厅",
    "咖啡",
    "商场",
)

# 主题乐园里的单个游乐设施也会被标成 tourism=attraction（上海迪士尼一次贡献
# 「七个小矮人矿山车」「巴斯光年星际营救」「弹簧狗团团转」等 5 条），
# 这类条目写进「XX 有什么好玩的」只会让答案显得滑稽。
RIDE_WORDS = (
    "矿山车",
    "过山车",
    "旋转木马",
    "碰碰车",
    "巡游",
    "营救",
    "史迪奇",
    "巴斯光年",
    "太空幸会",
    "团团转",
    "飞越",
    "飞跃",
    "漂流",
    "剧场",
    "舞台",
    "演出",
    "表演",
    "秀场",
    "影院",
    "历险",
    "探险岛",
    "摩天轮",
)

# 只有两三个字的通用名词（「古井」）也是噪声，但没有统一后缀可依，单独列。
GENERIC_NAMES = frozenset(
    {
        "古井",
        "水井",
        "石碑",
        "石像",
        "牌坊",
        "雕像",
        "凉亭",
        "亭子",
        "牌楼",
        "水池",
        "花园",
        "广场",
        "公园",
        "城楼",
        "城门",
        "旧址",
        "故居",
    }
)

CJK = re.compile(r"[\u4e00-\u9fff]")


def parse_geo() -> list[tuple[str, float, float]]:
    """[(城市名, lat, lng)]，来自 geo-data.js 的紧凑格式。"""
    text = GEO_FILE.read_text(encoding="utf-8")
    block = re.search(r"var RAW\s*=\s*\[(.*?)\n\s*\];", text, re.S)
    if not block:
        raise SystemExit(f"无法解析 {GEO_FILE}")
    out: list[tuple[str, float, float]] = []
    for item in re.findall(r'"([^"]*)"', block.group(1)):
        parts = item.split("|")
        if len(parts) < 4:
            continue
        try:
            lat, lng = (float(x) for x in parts[2].split(","))
        except ValueError:
            continue
        out.append((parts[0], lat, lng))
    return out


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_query(batch: list[tuple[str, float, float]]) -> str:
    parts = []
    for _, lat, lng in batch:
        parts.append(f'node[tourism~"{TOURISM_RE}"][wikidata][name](around:{RADIUS},{lat},{lng});')
    # `out tags` 不返回坐标（nodes 也一样），必须用 `out body` 才带 lat/lon
    return "[out:json][timeout:110];(" + "".join(parts) + f");out body {len(batch) * 800};"


def fetch(query: str) -> dict:
    """带重试的 POST。Overpass 高峰期会返回 502「queue is full」，退避重试即可。"""
    body = urllib.parse.urlencode({"data": query}).encode()
    last = ""
    for attempt, wait in enumerate((0, 8, 20, 45), 1):
        if wait:
            time.sleep(wait)
        req = urllib.request.Request(
            ENDPOINT,
            data=body,
            headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
            return json.loads(raw)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            last = f"{type(e).__name__}: {str(e)[:80]}"
            print(f"    第 {attempt} 次失败（{last}），重试…", flush=True)
    raise SystemExit(f"Overpass 连续失败：{last}")


def clean_name(tags: dict) -> str | None:
    name = (tags.get("name:zh") or tags.get("name") or "").strip()
    if not name or not CJK.search(name) or len(name) > 20:
        return None
    if any(w in name for w in NOISE_WORDS):
        return None
    if any(w in name for w in RIDE_WORDS):
        return None
    # 「西湖·断桥」这类用间隔号拼出来的，保留原样；全角括号里的别名去掉
    name = re.sub(r"[（(][^）)]*[）)]$", "", name).strip()
    if not name or name in GENERIC_NAMES:
        return None
    # OSM 里偶尔出现「李众胜堂祖铺 李众胜堂祖铺」这种名字被复制两遍的脏数据
    half = len(name) // 2
    if len(name) % 2 == 1 and name[:half] == name[half + 1 :]:
        name = name[:half]
    return name


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取 OSM 知名景点，补充清单档")
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 个城市（试跑用）")
    ap.add_argument("--reset", action="store_true", help="忽略缓存，全部重抓")
    args = ap.parse_args()

    cities = parse_geo()
    if args.limit:
        cities = cities[: args.limit]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    batches = [cities[i : i + BATCH] for i in range(0, len(cities), BATCH)]
    print(f"共 {len(cities)} 城，{len(batches)} 批，每批 {BATCH} 城", flush=True)

    for idx, batch in enumerate(batches):
        cache = CACHE_DIR / f"b{idx:03d}.json"
        if cache.exists() and not args.reset:
            continue
        query = build_query(batch)
        t0 = time.time()
        data = fetch(query)
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        n = len(data.get("elements") or [])
        print(
            f"  [{idx + 1}/{len(batches)}] {batch[0][0]}…{batch[-1][0]}  {n} 条  {time.time() - t0:.0f}s",
            flush=True,
        )
        time.sleep(DELAY)

    # ---- 归并：按距离把每个 POI 分给最近的城市中心 ----
    result: dict[str, list[dict]] = {}
    for idx, batch in enumerate(batches):
        cache = CACHE_DIR / f"b{idx:03d}.json"
        if not cache.exists():
            continue
        data = json.loads(cache.read_text(encoding="utf-8"))
        for el in data.get("elements") or []:
            tags = el.get("tags") or {}
            lat, lon = el.get("lat"), el.get("lon")
            if lat is None or lon is None:
                continue
            name = clean_name(tags)
            if not name:
                continue
            kind = KIND_MAP.get(tags.get("tourism", ""), "地标")
            city = min(batch, key=lambda c: haversine(lat, lon, c[1], c[2]))[0]
            bucket = result.setdefault(city, [])
            if any(s["n"] == name for s in bucket):
                continue
            bucket.append(
                {"n": name, "k": kind, "wd": tags.get("wikidata"), "lat": round(lat, 5), "lon": round(lon, 5)}
            )

    # 排序保证重跑字节一致（gen_city_spots --check 靠这个）
    for city in result:
        result[city].sort(key=lambda s: (s["k"], s["n"]))
    result = {c: result[c] for c in sorted(result)}

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )

    total = sum(len(v) for v in result.values())
    print(f"\n完成：{len(result)} 城共 {total} 个景点 → {OUT_FILE.relative_to(ROOT)}")
    print("下一步：.venv/Scripts/python.exe scripts/gen_city_spots.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
