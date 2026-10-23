"""知识库覆盖范围：用户问的城市，到底有没有本地攻略可查。

系统里有两套城市数据，覆盖面差两个数量级，这个边界必须显式暴露给用户：

- **地图**（`frontend/static/assets/js/geo-data.js`）：355 城 / 1558 个景点，
  只有坐标与分类，**没有攻略内容**，用于地图页定位与路线规划；
- **知识库**（`knowledge_base/*.md`）：目前 6 城，有门票、开放时间、交通、玩法，
  是 RAG 检索的唯一事实来源。

不区分这两者的后果很具体：用户问「哈尔滨有什么好玩的」，检索拿不到资料，
模型退回通用知识作答，而用户以为自己看到的是攻略库里的内容 —— 一旦门票价格
或开放时间过时，责任全在系统。所以这里把「问了哪些城市、其中哪些没覆盖」
算清楚，交给提示词层去显式声明。

扩展方式：把 `哈尔滨.md` 放进 `knowledge_base/` 再重建索引，本模块会自动把它
算进覆盖城市，无需改代码。
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


_kb_cache: tuple[tuple, tuple[str, ...]] | None = None


def _index_cities() -> set[str]:
    """已加载索引里实际存在的城市。

    为什么不能只看 `kb_dir`：索引才是检索真正用的数据源。测试里 `KB_DIR` 指向
    临时空目录、而索引由夹具直接注入，只看目录就会得出「一个城市都没覆盖」的
    错误结论，把所有查询都判成越界。生产环境两者一致，这里取并集不影响结果。
    """
    try:
        from app.rag import retriever
    except Exception:  # 索引模块不可用（极端情况），退化为只看目录
        return set()
    chunks = getattr(retriever, "_chunks", None) or []
    return {str(c.get("doc", "")).rsplit(".", 1)[0] for c in chunks}


def kb_cities() -> tuple[str, ...]:
    """知识库真正覆盖的城市。

    判定标准：`knowledge_base/` 下存在以城市名命名的 `.md`/`.txt`，或索引里
    有该城市的文本块。「外部攻略-小红书.md」这类非城市命名的文档会参与检索，
    但不算作某个城市的覆盖 —— 否则文案会声称覆盖了实际没有攻略的城市。

    缓存键含「文件数 + 最新 mtime + 索引对象标识」：管理员上传/删除文档、
    重建索引后无需重启即可生效，又不必每次请求都遍历一遍目录。
    """
    global _kb_cache
    directory = Path(settings.kb_dir)
    files = []
    if directory.is_dir():
        files = [p for p in (*directory.glob("*.md"), *directory.glob("*.txt")) if p.is_file()]
    chunks = _index_cities()
    signature = (
        len(files),
        max((p.stat().st_mtime for p in files), default=0.0),
        len(chunks),
        ",".join(sorted(chunks))[:200],
    )
    if _kb_cache and _kb_cache[0] == signature:
        return _kb_cache[1]

    known = set(map_cities())
    names = {p.stem for p in files} | chunks
    result = tuple(sorted(n for n in names if n in known))
    _kb_cache = (signature, result)
    return result


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
    covered: tuple[str, ...] = ()  # 其中有本地攻略库的
    uncovered: tuple[str, ...] = ()  # 其中没有的

    @property
    def has_gap(self) -> bool:
        """是否需要向用户声明「这部分不是攻略库内容」。"""
        return bool(self.uncovered)

    def to_dict(self) -> dict:
        return {
            "asked": list(self.asked),
            "covered": list(self.covered),
            "uncovered": list(self.uncovered),
            "kb_cities": list(kb_cities()),
            "map_cities": len(map_cities()),
        }


def detect(text: str) -> Coverage:
    """识别文本里提到的城市，并区分「有攻略库」与「只有地图数据」。

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

    covered_set = set(kb_cities())
    asked = tuple(c for c in hit if c in known)
    if not covered_set:
        # 一个城市都没覆盖，说明是**整个知识库不可用**（索引缺失或文档被清空），
        # `/health` 的 rag_state 已经会报这件事。此时给用户「XX 暂无攻略库」
        # 属于甩错锅：真实原因是检索没起来，不是这个城市没收录。
        return Coverage(asked=asked)
    return Coverage(
        asked=asked,
        covered=tuple(c for c in asked if c in covered_set),
        uncovered=tuple(c for c in asked if c not in covered_set),
    )


def summary() -> dict:
    """给接口用的覆盖概况（公开信息，不含任何内部路径）。"""
    cities = kb_cities()
    return {
        "cities": list(cities),
        "count": len(cities),
        "map_cities": len(map_cities()),
        "map_spots": map_spot_count(),
    }
