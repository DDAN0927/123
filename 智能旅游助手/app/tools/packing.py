"""行前装备清单：按目的地、天数、季节与天气预报生成**可勾选**的准备清单。

为什么值得单独做一个模块
------------------------
「去哈尔滨穿什么」这类问题，模型每次都能答，但答完就散在聊天记录里，
用户临出门还得再问一遍。这里把它变成结构化条目落进行程，能打勾、能带进度。

设计取舍
--------
* **有预报用预报，没预报按季节估**：预报只能覆盖未来 16 天，更远的行程不硬猜温度，
  只按月份给「冬/春/夏/秋」四档，并明确标注这是估算 —— 假装精确比不精确更糟。
* **南北差异靠纬度**：12 月的哈尔滨和三亚，装备差着一整个衣柜。纬度取自
  `geo-data.js`（前端地图已经在用），不另建城市纬度表。
* **不生成「买什么牌子」**：清单只回答「带什么」，具体型号交给用户。
"""

import datetime

from app.rag import coverage

# 城市名里带这些字的，按海滨目的地处理（泳衣、沙滩鞋、防水袋）
_COASTAL_HINTS = ("三亚", "厦门", "青岛", "大连", "北海", "珠海", "海口", "日照", "秦皇岛", "威海", "舟山")

# 高原目的地：防晒与保湿要单独提醒，海拔高的地方感冒不是小事
_PLATEAU_HINTS = ("拉萨", "日喀则", "林芝", "香格里拉", "稻城", "西宁", "格尔木", "九寨沟")


def _band(tmax: float | None, month: int, lat: float | None) -> str:
    """把「最高温 + 月份 + 纬度」归到一档穿衣策略。

    有预报时以温度为准；没有预报时按月份与南北给粗略档位，宁可粗也不要假精确。
    """
    if tmax is not None:
        if tmax <= 0:
            return "severe_cold"
        if tmax <= 10:
            return "cold"
        if tmax <= 20:
            return "cool"
        if tmax <= 28:
            return "mild"
        return "hot"
    # 无预报：按月份分档，再用纬度做一次修正（北方同月份低一档）
    north = lat is not None and lat >= 38
    if month in (12, 1, 2):
        return "severe_cold" if north else "cold"
    if month in (3, 4, 5):
        return "cool"
    if month in (6, 7, 8):
        return "hot"
    return "cool" if north else "mild"


_CLOTHES = {
    "severe_cold": [
        "羽绒服（充绒量 150g 以上，长款更抗风）",
        "保暖内衣 / 加绒打底",
        "厚毛衣或抓绒衣",
        "加绒长裤（不建议牛仔裤，风一吹透心凉）",
        "厚袜子 + 防水防滑雪地靴",
        "帽子、围巾、手套（三件套缺一不可）",
        "暖宝宝（贴腰和脚底，室外待久了很管用）",
    ],
    "cold": [
        "厚外套 / 冲锋衣（带可拆内胆最佳）",
        "毛衣或卫衣",
        "长裤 + 秋裤（早晚温差大时用得上）",
        "保暖鞋 + 厚袜",
        "围巾（北方风大，护住脖子体感差很多）",
    ],
    "cool": [
        "薄外套 / 风衣 / 针织开衫",
        "长袖 T 恤或衬衫",
        "长裤（备一条薄款应对升温）",
        "舒适步行鞋",
    ],
    "mild": [
        "长袖 + 薄外套（早晚温差大，别只带短袖）",
        "短袖 T 恤",
        "休闲长裤 / 薄长裙",
        "透气步行鞋",
    ],
    "hot": [
        "速干短袖 T 恤",
        "短裤 / 轻薄长裙",
        "防晒外套（室内空调和正午暴晒都用得上）",
        "凉鞋或透气运动鞋",
        "换洗内衣袜子（按天数准备）",
    ],
}

_BASE = {
    "证件与票据": [
        "身份证（住宿登记、景区购票、火车高铁必备）",
        "学生证 / 教师证 / 老年证（很多景区半价，能省不少）",
        "银行卡 + 少量现金（小店、乡镇摊位可能不支持扫码）",
        "驾驶证（计划自驾时必带）",
    ],
    "电子设备": [
        "手机 + 充电器",
        "充电宝（20000mAh 以内可随身登机，别托运）",
        "数据线（多带一根，坏一根是常事）",
        "耳机（长途交通上很有用）",
    ],
    "洗护与药品": [
        "洗漱包（牙刷牙膏、洗面奶、小瓶洗发水）",
        "防晒霜（SPF50+，阴天也要涂）",
        "常用药：感冒药、肠胃药、创可贴、晕车药",
        "个人处方药（按天数 + 2 天备量，别刚好带够）",
        "纸巾 / 湿巾",
    ],
    "行前预订": [
        "往返大交通（机票 / 高铁，越早越便宜）",
        "住宿（热门城市旺季提前 2 周以上）",
        "热门景点门票（故宫、迪士尼这类要提前 7 天实名预约）",
        "当地交通：地铁卡或打车软件绑定支付方式",
        "旅游意外险（几十块，长途或户外强烈建议）",
        "离线地图（山区、海岛信号差，提前下载）",
    ],
}


def build(
    city: str,
    days: int = 3,
    start_date: str = "",
    tmax: float | None = None,
    tmin: float | None = None,
    precip: float | None = None,
) -> list[dict]:
    """生成装备清单。

    返回 `[{"group": 分组名, "items": [条目, ...]}, ...]`，顺序即建议展示顺序。

    `tmax/tmin/precip` 来自行程期间的天气预报；拿不到就传 None，函数会退化为季节估算。
    """
    days = max(1, min(int(days or 1), 30))
    city = (city or "").strip()

    if start_date:
        try:
            month = datetime.date.fromisoformat(start_date).month
        except ValueError:
            month = datetime.date.today().month
    else:
        month = datetime.date.today().month

    coord = coverage.city_center(city) if city else None
    lat = coord[0] if coord else None
    band = _band(tmax, month, lat)

    groups: list[dict] = [
        {"group": "证件与票据", "items": list(_BASE["证件与票据"])},
    ]

    # 衣物：按档位取，再按天数调整换洗量
    clothes = list(_CLOTHES[band])
    wash = min(days, 5)
    clothes.append(f"换洗内衣袜子 {wash} 套（按 {days} 天行程，中途可洗）")
    groups.append({"group": "衣物与鞋", "items": clothes})

    groups.append({"group": "电子设备", "items": list(_BASE["电子设备"])})
    groups.append({"group": "洗护与药品", "items": list(_BASE["洗护与药品"])})

    # 季节 / 天气专项
    special: list[str] = []
    if precip is not None and precip >= 40:
        special.append(f"雨具（降水概率约 {round(precip)}%，折叠伞 + 一次性雨衣各一）")
        special.append("防水鞋套或备用鞋（雨天鞋子湿了最难熬）")
    elif band in ("cool", "mild"):
        special.append("折叠伞（天气多变，晴雨两用）")
    if band == "hot" or (tmax is not None and tmax >= 28):
        special.append("太阳镜 + 遮阳帽")
        special.append("防蚊液 / 驱蚊贴（夏季傍晚户外必备）")
    if band in ("cold", "severe_cold"):
        special.append("润唇膏 + 护手霜（干冷地区皮肤容易裂）")
    if any(h in city for h in _COASTAL_HINTS):
        special.append("泳衣 + 沙滩鞋（海滨目的地）")
        special.append("手机防水袋")
    if any(h in city for h in _PLATEAU_HINTS):
        special.append("高倍防晒 + 保湿面膜（高原紫外线强、空气干）")
        special.append("葡萄糖 / 便携氧气（初上高原备用）")
    if days >= 5:
        special.append("折叠行李袋（回程带特产用）")
    if special:
        groups.append({"group": "季节专项", "items": special})

    groups.append({"group": "行前预订", "items": list(_BASE["行前预订"])})

    if tmax is None:
        # 说清楚这是估算，避免用户把它当成精确预报
        groups.append(
            {
                "group": "说明",
                "items": ["以上按季节与目的地估算，出发前 3 天请再看一次天气，按实际温度调整衣物"],
            }
        )
    return groups


def items_of(groups: list[dict]) -> list[dict]:
    """把分组清单压成 `[{"group": 分组, "title": 条目}]`，便于落库。

    分组写进条目的 `slot` 字段（行前清单没有「上午/下午」，正好复用这一列），
    条目正文写 `title`，不把两段拼成一个字符串 —— 拼起来以后想改分组就得解析文本。
    """
    return [{"group": g["group"], "title": item} for g in groups for item in g["items"]]
