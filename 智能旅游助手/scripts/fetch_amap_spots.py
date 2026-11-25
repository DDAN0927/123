"""从高德开放平台「Web 服务」接口抓取城市 POI，补充攻略库的景点清单。

和 fetch_osm_spots.py 的关系
----------------------------
两个是**可选的、互为补充**的数据源，产物格式相同，`gen_city_spots.py` 会按
`高德 → OSM → 地图数据` 的顺序去重合并：

| | OpenStreetMap | 高德 |
|---|---|---|
| 要不要 key | 不要 | 要（免费注册） |
| 国内覆盖 | 一般，景点标签稀疏 | 好，含地址、类型、评分 |
| 有门票/开放时间吗 | 几乎没有 | 部分 POI 有 `biz_ext.open_time` |
| 许可 | ODbL | 按其服务条款，需遵守配额 |

为什么必须用「Web 服务」类型的 Key
---------------------------------
高德把 Key 按平台分开：JS API 的 Key 调 Web 服务接口会返回
`{"info":"USERKEY_PLAT_NOMATCH","infocode":"10009"}`。本项目前端用的那个 Key
是 JS API 类型，**不能**拿来跑这个脚本。

申请方式：高德开放平台 → 控制台 → 应用管理 → 创建新应用 → 添加 Key →
服务平台选「Web服务」。个人开发者有免费日配额，够把 355 城跑好几遍。

用法
----
    set AMAP_WEB_KEY=你的key            # Windows CMD
    export AMAP_WEB_KEY=你的key         # Git Bash / Linux
    .venv/Scripts/python.exe scripts/fetch_amap_spots.py
    .venv/Scripts/python.exe scripts/fetch_amap_spots.py --limit 20   # 先试 20 城
    .venv/Scripts/python.exe scripts/fetch_amap_spots.py --check      # 只验证 key

产物
----
    datasets/amap_spots.json    {城市: [{n: 名称, k: 分类, lat, lon, addr, rating, open_time}]}
    data/amap_cache/*.json      原始响应缓存（gitignore），断点续跑靠它
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO_FILE = ROOT / "frontend" / "static" / "assets" / "js" / "geo-data.js"
OUT_FILE = ROOT / "datasets" / "amap_spots.json"
CACHE_DIR = ROOT / "data" / "amap_cache"

API = "https://restapi.amap.com/v3/place/text"
# 110000 风景名胜；140000 科教文化服务（博物馆、美术馆多在这里）
TYPES = "110000|140000"
OFFSET = 25  # 单页上限 25
PAGES = 3  # 最多请求 3 页（75 条），实际按 MAX_PER_CITY 截断
MAX_PER_CITY = 24  # 单城最终保留条数：清单档不是攻略，24 条足够覆盖主力景点
RADIUS = 40000  # 米，超出城市中心 40km 的丢弃（高德的 city 参数偶尔会串到邻市）
DELAY = 0.6  # 配额友好：约 1.6 次/秒
QUOTA_SLEEP = 60  # 撞到 10045 后等待的秒数
QUOTA_RETRIES = 3  # 同一页最多重试次数；仍失败才放弃本轮

KIND_BY_TYPE = (
    ("博物馆", "场馆"),
    ("美术馆", "场馆"),
    ("展览馆", "场馆"),
    ("纪念馆", "场馆"),
    ("科技馆", "场馆"),
    ("动物园", "亲子"),
    ("水族馆", "亲子"),
    ("海洋馆", "亲子"),
    ("游乐园", "乐园"),
    ("公园", "公园"),
    ("广场", "公园"),
    ("寺庙", "古迹"),
    ("教堂", "古迹"),
    ("遗址", "古迹"),
    ("故居", "古迹"),
    ("古镇", "街区"),
    ("步行街", "街区"),
    ("商业街", "街区"),
)

NOISE_WORDS = (
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
    "酒店",
    "宾馆",
    "饭店",
    "招待所",
    "公寓",
    "小区",
    # 广场的组成部分、桥、通道被高德归到「风景名胜」，这些不是景点
    "下沉式",
    "人行桥",
    "天桥",
    "隧道",
    "高架",
    "地下通道",
)

CJK = re.compile(r"[\u4e00-\u9fff]")

# 配额类错误：跑不完不是代码错，停下来落盘已有缓存、下次接着跑
QUOTA_CODES = {"10003", "10044", "10045", "10041"}


class QuotaExhausted(RuntimeError):
    """当日配额用完。缓存已落盘，第二天重跑会自动跳过已抓城市。"""


class CitySkipped(RuntimeError):
    """高德不认这个地名（`USER_ABROAD_*` 报错）。

    地图数据里有「五台山」「凤凰」这类景区名而不是行政区名，高德会把它们
    当成境外/无法归属的查询，走另一条额度且常年耗尽。这类城市直接跳过，
    不能因为它中断整轮抓取。
    """


# 高德错误码 → 人能看懂的处置建议
ERROR_HINTS = {
    "10001": "Key 不正确或已过期，去控制台核对。",
    "10003": "日配额或并发超限，等配额重置或换 Key。",
    "10009": "Key 平台类型不匹配：这里必须用「Web服务」类型的 Key，JS API 的 Key 用不了。",
    "10010": "IP 白名单限制：把当前出口 IP 加进 Key 的白名单，或取消白名单。",
    "10012": "账号权限不足，确认账号已开通 Web 服务。",
    "10013": "Key 已被删除或停用。",
    "10041": "并发或 QPS 超限，降低请求频率后重试。",
    "10044": "当日调用量已达上限。",
    "10045": "当日调用量已达上限（个人开发者免费额度用尽）。",
    "20000": "请求参数错误，检查 city / types 是否合法。",
    "20003": "无结果：该城市名高德认不出来，可换成行政区编码。",
}


def parse_geo() -> list[tuple[str, float, float]]:
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


def call(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "travel-copilot-kb/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf-8"))
    if str(data.get("status")) != "1":
        code = str(data.get("infocode", ""))
        info = str(data.get("info", ""))
        hint = ERROR_HINTS.get(code, info or "未知错误")
        # 先判 ABROAD：它也是 10045，但含义完全不同，重试一辈子也不会成功
        if "ABROAD" in info.upper():
            raise CitySkipped(info)
        if code in QUOTA_CODES:
            raise QuotaExhausted(f"infocode={code}：{hint}")
        raise SystemExit(f"高德接口报错 infocode={code}：{hint}")
    return data


def kind_of(type_str: str) -> str:
    for key, kind in KIND_BY_TYPE:
        if key in type_str:
            return kind
    return "地标"


def clean_name(name: str) -> str | None:
    name = (name or "").strip()
    if not name or not CJK.search(name) or len(name) > 20:
        return None
    if any(w in name for w in NOISE_WORDS):
        return None
    return re.sub(r"[（(][^）)]*[）)]$", "", name).strip() or None


def load_key() -> str:
    """优先环境变量，其次项目根目录的 `.env`。

    手动解析而不是引入 dotenv：这个脚本要能在最裸的环境里跑，
    少一个导入就少一个「跑不起来」的理由。
    """
    key = (os.environ.get("AMAP_WEB_KEY") or "").strip()
    if key:
        return key
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("AMAP_WEB_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="从高德 Web 服务接口抓取城市 POI")
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 城")
    ap.add_argument("--check", action="store_true", help="只验证 Key 是否可用")
    ap.add_argument("--reset", action="store_true", help="忽略缓存重抓")
    args = ap.parse_args()

    key = load_key()
    if not key:
        print(
            "缺少 AMAP_WEB_KEY。\n"
            "  1. 打开 https://console.amap.com/dev/key/app 创建一个「Web服务」类型的 Key\n"
            "  2. 二选一：\n"
            "     · 在项目根目录的 .env 里加一行  AMAP_WEB_KEY=你的key\n"
            "     · 或临时设置环境变量  export AMAP_WEB_KEY=你的key\n"
            "  3. 重跑本脚本",
            file=sys.stderr,
        )
        return 2

    # 先用最便宜的一次请求验证 Key，免得跑了一半才发现类型不对
    probe = call({"key": key, "keywords": "故宫", "city": "北京", "offset": 1, "page": 1})
    print(f"Key 可用，探测返回 {len(probe.get('pois') or [])} 条结果")
    if args.check:
        return 0

    cities = parse_geo()
    if args.limit:
        cities = cities[: args.limit]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # 配额提示：每城最多 PAGES 次请求，缓存过的城市不会重复消耗。
    cached = sum(1 for c, _, _ in cities if (CACHE_DIR / f"{c}.json").exists())
    todo = len(cities) - cached
    print(f"待抓 {todo} 城（已缓存 {cached}），本次最多消耗 {todo * PAGES} 次配额", flush=True)

    quota_hit = False
    skipped: list[str] = []
    for i, (city, _lat, _lng) in enumerate(cities, 1):
        cache = CACHE_DIR / f"{city}.json"
        if cache.exists() and not args.reset:
            continue
        pois: list[dict] = []
        try:
            for page in range(1, PAGES + 1):
                data = None
                for attempt in range(QUOTA_RETRIES + 1):
                    try:
                        data = call(
                            {
                                "key": key,
                                "keywords": "景点",
                                "types": TYPES,
                                "city": city,
                                "citylimit": "true",
                                "offset": OFFSET,
                                "page": page,
                                "extensions": "all",
                            }
                        )
                        break
                    except QuotaExhausted:
                        if attempt == QUOTA_RETRIES:
                            raise
                        # 10045 实测是「窗口内调用量过大」而不是「当日彻底用尽」，
                        # 等一分钟就能继续，别因为一次限流丢掉整轮进度
                        print(
                            f"  ⏳ {city} 第 {page} 页被限流，等 {QUOTA_SLEEP}s 重试"
                            f"（{attempt + 1}/{QUOTA_RETRIES}）",
                            flush=True,
                        )
                        time.sleep(QUOTA_SLEEP)
                batch = (data or {}).get("pois") or []
                pois.extend(batch)
                time.sleep(DELAY)
                if len(batch) < OFFSET:
                    break
        except CitySkipped:
            # 写空缓存：以后重跑直接跳过，不再浪费配额试探
            cache.write_text("[]", encoding="utf-8")
            skipped.append(city)
            print(f"  [{i}/{len(cities)}] {city}  跳过（高德不认这个地名）", flush=True)
            continue
        except QuotaExhausted as e:
            # 关键：已抓到的先落盘，然后跳出循环去做归并，而不是整体退出
            if pois:
                cache.write_text(json.dumps(pois, ensure_ascii=False), encoding="utf-8")
            quota_hit = True
            print(f"\n⚠️ 配额用尽（{e}），停在第 {i}/{len(cities)} 城：{city}", flush=True)
            break
        cache.write_text(json.dumps(pois, ensure_ascii=False), encoding="utf-8")
        print(f"  [{i}/{len(cities)}] {city}  {len(pois)} 条", flush=True)

    # ---- 归并 ----
    result: dict[str, list[dict]] = {}
    for city, clat, clng in cities:
        cache = CACHE_DIR / f"{city}.json"
        if not cache.exists():
            continue
        bucket = result.setdefault(city, [])
        for poi in json.loads(cache.read_text(encoding="utf-8")):
            name = clean_name(poi.get("name", ""))
            if not name:
                continue
            loc = (poi.get("location") or "").split(",")
            if len(loc) != 2:
                continue
            lng_, lat_ = float(loc[0]), float(loc[1])
            if haversine(clat, clng, lat_, lng_) > RADIUS:
                continue
            if any(s["n"] == name for s in bucket):
                continue
            biz = poi.get("biz_ext") or {}
            rating = biz.get("rating")
            bucket.append(
                {
                    "n": name,
                    "k": kind_of(poi.get("type", "")),
                    "lat": round(lat_, 5),
                    "lon": round(lng_, 5),
                    "addr": poi.get("address") if isinstance(poi.get("address"), str) else "",
                    "rating": rating if isinstance(rating, str) else "",
                    "open_time": biz.get("open_time") if isinstance(biz.get("open_time"), str) else "",
                }
            )

        # 评分高的排前面（无评分的排后面），同分按名称稳定排序 —— 保证每次重跑字节一致
        def _rank(s: dict) -> tuple:
            try:
                score = float(s["rating"])
            except (TypeError, ValueError):
                score = 0.0
            return (-score, s["k"], s["n"])

        bucket.sort(key=_rank)
        result[city] = bucket[:MAX_PER_CITY]

    result = {c: result[c] for c in sorted(result) if result[c]}
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    total = sum(len(v) for v in result.values())
    print(f"\n完成：{len(result)} 城共 {total} 个景点 → {OUT_FILE.relative_to(ROOT)}")
    if skipped:
        print(
            f"跳过 {len(skipped)} 城（地名不是行政区，高德查不到）：{'、'.join(skipped[:12])}"
            f"{' 等' if len(skipped) > 12 else ''}"
        )
    if quota_hit:
        missing = len(cities) - len(result) - len(skipped)
        print(f"还有 {missing} 城未抓（配额用尽）。缓存已保存，配额重置后直接重跑本脚本即可续抓。")
    print("下一步：.venv/Scripts/python.exe scripts/gen_city_spots.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
