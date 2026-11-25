"""知识库覆盖范围：用户问的城市，到底有多少本地资料可查。

系统里有两套城市数据，覆盖面差两个数量级，这个边界必须显式暴露给用户：

- **地图**（`frontend/static/assets/js/geo-data.js`）：355 城 / 1558 个景点，
  只有坐标与分类，没有门票与开放时间，用于地图页定位与路线规划；
- **知识库**：分三档
  * **完整攻略档** `knowledge_base/*.md` —— 6 城，有门票、开放时间、交通、
    行程、美食，是 RAG 检索的权威事实来源；
  * **景点导览档** `knowledge_base/guides/*.md` —— 171 城，由
    `scripts/gen_city_guides.py` 从中文维基导游 + 高德生成，有景点介绍与
    **部分**门票、开放时间，但非人工精编，可能过时；
  * **景点清单档** `knowledge_base/spots/*.md` —— 其余城市，由
    `scripts/gen_city_spots.py` 从地图数据生成，只有景点名与类型。

为什么必须分档而不是「有/没有」
------------------------------
一档化会制造一种更隐蔽的错误：用户看到「哈尔滨有中央大街、太阳岛」，就以为
门票和开放时间也是攻略库给的，而实际是模型自己补的。分档之后，提示词层可以
精确要求「导览档城市可以引用介绍与门票区间，但要注明以景区公告为准；清单档
城市只能介绍有哪些景点，易变信息必须写约值」，回答末尾的脚注也能说清楚
「这一段依据的是哪一档」。

扩展方式：把 `哈尔滨.md` 放进 `knowledge_base/` 再重建索引，它就自动升级成
完整攻略档（导览档与清单档的同名文件都会被忽略），无需改代码。
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings

# 地图数据文件（前端与后端共用同一份，避免两套城市清单打架）
_GEO_FILE = Path(__file__).resolve().parents[2] / "frontend" / "static" / "assets" / "js" / "geo-data.js"

# 城市俗称。只收「不会作为普通词语/街道名出现」的别名：
# 「长安」看着像西安，但「长安街」在北京，收进来就会把「北京的长安街」误判成西安。
_ALIAS: dict[str, str] = {
    "京城": "北京",
    "帝都": "北京",
    "魔都": "上海",
    "申城": "上海",
    "蓉城": "成都",
    "锦官城": "成都",
    "山城": "重庆",
    "雾都": "重庆",
    "杭城": "杭州",
    "钱塘": "杭州",
}

# 比城市名更长、且**包含**某个城市名的专有地名。
# 「长白山」按最长匹配会先命中「白山」（吉林白山市），「峨眉山」会命中「眉山」（四川眉山市），
# 都是错的。先把这类词整体挖掉再匹配。
_LONGER_PLACES = ("长白山", "峨眉山")

_MASK = "\u0000"


@lru_cache(maxsize=1)
def map_cities() -> tuple[str, ...]:
    """地图数据覆盖的城市（355 城）。解析失败时返回空元组，不影响主链路。"""
    try:
        text = _GEO_FILE.read_text(encoding="utf-8")
    except OSError:
        return ()
    block = re.search(r"var RAW\s*=\s*\[(.*?)\n\s*\];", text, re.S)
    if not block:
        return ()
    cities = []
    for item in re.findall(r'"([^"]*)"', block.group(1)):
        parts = item.split("|")
        if len(parts) >= 4 and parts[0]:
            cities.append(parts[0])
    return tuple(cities)


@lru_cache(maxsize=1)
def map_spot_count() -> int:
    """地图数据里的景点总数（1558），用于对外文案与接口自检。"""
    try:
        text = _GEO_FILE.read_text(encoding="utf-8")
    except OSError:
        return 0
    block = re.search(r"var RAW\s*=\s*\[(.*?)\n\s*\];", text, re.S)
    if not block:
        return 0
    total = 0
    for item in re.findall(r'"([^"]*)"', block.group(1)):
        parts = item.split("|")
        if len(parts) >= 4:
            total += len(parts) - 3
    return total


@lru_cache(maxsize=1)
def city_centers() -> dict[str, tuple[float, float]]:
    """城市中心坐标 {城市名: (纬度, 经度)}。

    装备清单要靠纬度判断「南方还是北方」（12 月去哈尔滨和去三亚带的东西完全不同），
    而这份坐标前端地图已经在用了，没必要再维护第二份城市纬度表。
    """
    try:
        text = _GEO_FILE.read_text(encoding="utf-8")
    except OSError:
        return {}
    block = re.search(r"var RAW\s*=\s*\[(.*?)\n\s*\];", text, re.S)
    if not block:
        return {}
    out: dict[str, tuple[float, float]] = {}
    for item in re.findall(r'"([^"]*)"', block.group(1)):
        parts = item.split("|")
        if len(parts) < 4:
            continue
        try:
            lat, lng = (float(x) for x in parts[2].split(","))
        except (ValueError, TypeError):
            continue
        out[parts[0]] = (lat, lng)
    return out


def city_center(name: str) -> tuple[float, float] | None:
    """按城市名取中心坐标；先精确匹配，再退化为「包含」匹配（「北京市」→「北京」）。"""
    centers = city_centers()
    if name in centers:
        return centers[name]
    for city, coord in centers.items():
        if city in name:
            return coord
    return None


_kb_cache: tuple[tuple, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] | None = None


def _index_cities() -> set[str]:
    """已加载索引里实际存在的城市。

    为什么不能只看 `kb_dir`：索引才是检索真正用的数据源。测试里 `KB_DIR` 指向
    临时空目录、而索引由夹具直接注入，只看目录就会得出「一个城市都没覆盖」的
    错误结论，把所有查询都判成越界。生产环境两者一致，这里只在目录里一个文档
    都没有时兜底使用。
    """
    try:
        from app.rag import retriever
    except Exception:  # 索引模块不可用（极端情况），退化为只看目录
        return set()
    chunks = getattr(retriever, "_chunks", None) or []
    return {Path(str(c.get("doc", ""))).stem for c in chunks if c.get("doc")}


def _kb_files() -> tuple[list[Path], list[Path], list[Path]]:
    """(完整攻略档文件, 景点导览档文件, 景点清单档文件)。

    分档靠**目录**而不是文件名后缀：索引器用 `Path(doc).stem` 作城市名、检索器
    拿它做城市硬约束，文件名里塞「-景点清单」会把城市名变成
    「哈尔滨-景点清单」，城市识别直接失效。
    """
    directory = Path(settings.kb_dir)
    if not directory.is_dir():
        return [], [], []
    exts = (".md", ".txt")

    def pick(d: Path) -> list[Path]:
        return [p for p in sorted(d.glob("*")) if p.is_file() and p.suffix.lower() in exts]

    guides_dir = directory / "guides"
    spots_dir = directory / "spots"
    return (
        pick(directory),
        pick(guides_dir) if guides_dir.is_dir() else [],
        pick(spots_dir) if spots_dir.is_dir() else [],
    )


def _tiers() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """(完整攻略档城市, 景点导览档城市, 景点清单档城市)，均已按地图城市名过滤。

    缓存键含「文件数 + 最新 mtime」：管理员上传/删除文档、脚本重新生成清单档后
    无需重启即可生效，又不必每次请求都遍历 500 多个文件。
    """
    global _kb_cache
    guides, guided, spots = _kb_files()
    signature: tuple = (
        len(guides),
        len(guided),
        len(spots),
        max((p.stat().st_mtime for p in (*guides, *guided, *spots)), default=0.0),
    )
    if not guides and not guided and not spots:
        # 目录为空时结果来自索引兜底，签名必须把索引规模也算进去，
        # 否则夹具换了一批块、缓存还认为「没变化」。
        signature += (len(_index_cities()),)
    if _kb_cache and _kb_cache[0] == signature:
        return _kb_cache[1]

    known = set(map_cities())
    full = tuple(sorted(p.stem for p in guides if p.stem in known))
    full_set = set(full)
    guide_tier = tuple(sorted(p.stem for p in guided if p.stem in known and p.stem not in full_set))
    guide_set = set(guide_tier)
    listed = tuple(
        sorted(
            p.stem for p in spots if p.stem in known and p.stem not in full_set and p.stem not in guide_set
        )
    )
    if not full and not guide_tier and not listed:
        # 目录里一个文档都没有，但索引里有块（测试夹具会这样注入）：
        # 无法判断档位，按「完整攻略」处理 —— 否则所有查询都会被判成越界。
        full = tuple(sorted(_index_cities() & known))
    result = (full, guide_tier, listed)
    _kb_cache = (signature, result)
    return result


def kb_cities() -> tuple[str, ...]:
    """知识库有收录的城市（三档合计）。

    「外部攻略-小红书.md」这类非城市命名的文档会参与检索，但不算作某个城市的
    覆盖 —— 否则文案会声称覆盖了实际没有攻略的城市。
    """
    full, guided, listed = _tiers()
    return tuple(sorted((*full, *guided, *listed)))


def full_cities() -> tuple[str, ...]:
    """有完整攻略（门票/开放时间/交通/行程）的城市。"""
    return _tiers()[0]


def guided_cities() -> tuple[str, ...]:
    """有景点导览（介绍 + 部分门票/开放时间）的城市。

    来自中文维基导游，比清单档多出景点介绍与部分门票，但**不是**人工精编，
    数据可能过时，措辞上要与完整攻略档区分开。
    """
    return _tiers()[1]


def list_cities() -> tuple[str, ...]:
    """只有景点清单（景点名 + 类型）的城市。"""
    return _tiers()[2]


def reset_cache() -> None:
    """索引重建 / 知识库变更后清缓存（与 retriever.reset() 一起调用）。"""
    global _kb_cache
    _kb_cache = None
    map_cities.cache_clear()
    map_spot_count.cache_clear()
    city_centers.cache_clear()


@dataclass(frozen=True)
class Coverage:
    """一次查询的城市覆盖判定结果。"""

    asked: tuple[str, ...] = ()  # 用户提到、且我们有地图数据的城市
    covered: tuple[str, ...] = ()  # 其中有完整攻略的
    guided: tuple[str, ...] = ()  # 其中有景点导览（介绍 + 部分门票）的
    listed: tuple[str, ...] = ()  # 其中只有景点清单的
    uncovered: tuple[str, ...] = ()  # 其中连清单都没有的

    @property
    def has_gap(self) -> bool:
        """是否需要向用户声明「这部分资料不完整」。

        导览档不算缺口：它有景点介绍与部分门票，只是不是人工精编。
        """
        return bool(self.listed or self.uncovered)

    def to_dict(self) -> dict:
        full, guided_all, listed_all = _tiers()
        return {
            "asked": list(self.asked),
            "covered": list(self.covered),
            "guided": list(self.guided),
            "listed": list(self.listed),
            "uncovered": list(self.uncovered),
            "kb_cities": sorted((*full, *guided_all, *listed_all)),
            "full_cities": list(full),
            "guided_count": len(guided_all),
            "list_count": len(listed_all),
            "map_cities": len(map_cities()),
        }


def detect(text: str) -> Coverage:
    """识别文本里提到的城市，并区分「完整攻略 / 仅景点清单 / 未收录」。

    按**最长优先**匹配并就地挖除：先命中的长名会占位成 `\\u0000`，
    短名不会在它的位置上二次命中（否则「马鞍山」会被同时算成「鞍山」）。
    """
    if not text:
        return Coverage()
    known = set(map_cities())
    if not known:
        return Coverage()

    masked = text
    for place in _LONGER_PLACES:
        masked = masked.replace(place, _MASK * len(place))

    # 城市名 + 别名一起按长度降序，保证长名优先
    candidates = sorted(known | set(_ALIAS), key=len, reverse=True)
    hit: list[str] = []
    for name in candidates:
        if name not in masked:
            continue
        city = _ALIAS.get(name, name)
        if city not in hit:
            hit.append(city)
        masked = masked.replace(name, _MASK * len(name))

    full, guided, listed = (set(x) for x in _tiers())
    asked = tuple(c for c in hit if c in known)
    if not full and not guided and not listed:
        # 一个城市都没收录，说明是**整个知识库不可用**（索引缺失或文档被清空），
        # `/health` 的 rag_state 已经会报这件事。此时给用户「XX 暂无攻略库」
        # 属于甩错锅：真实原因是检索没起来，不是这个城市没收录。
        return Coverage(asked=asked)
    return Coverage(
        asked=asked,
        covered=tuple(c for c in asked if c in full),
        guided=tuple(c for c in asked if c in guided and c not in full),
        listed=tuple(c for c in asked if c in listed and c not in full and c not in guided),
        uncovered=tuple(c for c in asked if c not in full and c not in guided and c not in listed),
    )


def summary() -> dict:
    """给接口用的覆盖概况（公开信息，不含任何内部路径）。"""
    full, guided, listed = _tiers()
    return {
        "cities": sorted((*full, *guided, *listed)),
        "count": len(full) + len(guided) + len(listed),
        "full_cities": list(full),
        "full_count": len(full),
        "guided_count": len(guided),
        "list_count": len(listed),
        "map_cities": len(map_cities()),
        "map_spots": map_spot_count(),
    }
