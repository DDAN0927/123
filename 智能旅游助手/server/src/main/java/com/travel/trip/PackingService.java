package com.travel.trip;

import com.travel.trip.TripDtos.WeatherRow;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;

/**
 * 行前装备清单：气候带 + 天数 + 预报 三段合成。
 *
 * <p>不是一张写死的清单，因为「去哈尔滨穿什么」和「去三亚穿什么」差着一整个衣柜。
 * 判定顺序：有预报按最高温分档；没有预报按月份分档，再用纬度修正（北方同月低一档）。
 * 拿不到预报就明确写「按季节估算」，不做假精确。
 */
@Service
public class PackingService {

    private static final List<String> COASTAL =
            List.of("三亚", "厦门", "青岛", "大连", "北海", "珠海", "海口", "日照", "秦皇岛", "威海", "舟山");
    private static final List<String> PLATEAU =
            List.of("拉萨", "日喀则", "林芝", "香格里拉", "稻城", "西宁", "格尔木", "九寨沟");

    private static final Map<String, List<String>> CLOTHES = new LinkedHashMap<>();

    static {
        CLOTHES.put(
                "severe_cold",
                List.of(
                        "羽绒服（充绒量 150g 以上，长款更抗风）",
                        "保暖内衣 / 加绒打底",
                        "厚毛衣或抓绒衣",
                        "加绒长裤（不建议牛仔裤，风一吹透心凉）",
                        "厚袜子 + 防水防滑雪地靴",
                        "帽子、围巾、手套（三件套缺一不可）",
                        "暖宝宝（贴腰和脚底，室外待久了很管用）"));
        CLOTHES.put(
                "cold",
                List.of(
                        "厚外套 / 冲锋衣（带可拆内胆最佳）",
                        "毛衣或卫衣",
                        "长裤 + 秋裤（早晚温差大时用得上）",
                        "保暖鞋 + 厚袜",
                        "围巾（北方风大，护住脖子体感差很多）"));
        CLOTHES.put(
                "cool",
                List.of("薄外套 / 风衣 / 针织开衫", "长袖 T 恤或衬衫", "长裤（备一条薄款应对升温）", "舒适步行鞋"));
        CLOTHES.put(
                "mild",
                List.of("长袖 + 薄外套（早晚温差大，别只带短袖）", "短袖 T 恤", "休闲长裤 / 薄长裙", "透气步行鞋"));
        CLOTHES.put(
                "hot",
                List.of(
                        "速干短袖 T 恤",
                        "短裤 / 轻薄长裙",
                        "防晒外套（室内空调和正午暴晒都用得上）",
                        "凉鞋或透气运动鞋",
                        "换洗内衣袜子（按天数准备）"));
    }

    private static final List<String> DOCS =
            List.of(
                    "身份证（住宿登记、景区购票、火车高铁必备）",
                    "学生证 / 教师证 / 老年证（很多景区半价，能省不少）",
                    "银行卡 + 少量现金（小店、乡镇摊位可能不支持扫码）",
                    "驾驶证（计划自驾时必带）");
    private static final List<String> ELECTRONICS =
            List.of("手机 + 充电器", "充电宝（20000mAh 以内可随身登机，别托运）", "数据线（多带一根，坏一根是常事）", "耳机（长途交通上很有用）");
    private static final List<String> TOILETRIES =
            List.of(
                    "洗漱包（牙刷牙膏、洗面奶、小瓶洗发水）",
                    "防晒霜（SPF50+，阴天也要涂）",
                    "常用药：感冒药、肠胃药、创可贴、晕车药",
                    "个人处方药（按天数 + 2 天备量，别刚好带够）",
                    "纸巾 / 湿巾");
    private static final List<String> BOOKING =
            List.of(
                    "往返大交通（机票 / 高铁，越早越便宜）",
                    "住宿（热门城市旺季提前 2 周以上）",
                    "热门景点门票（故宫、迪士尼这类要提前 7 天实名预约）",
                    "当地交通：地铁卡或打车软件绑定支付方式",
                    "旅游意外险（几十块，长途或户外强烈建议）",
                    "离线地图（山区、海岛信号差，提前下载）");

    private final CityGeoService geo;

    public PackingService(CityGeoService geo) {
        this.geo = geo;
    }

    /** 归到一档穿衣策略：有预报按温度，没有按月份 + 纬度。 */
    String band(Integer tmax, int month, Double lat) {
        if (tmax != null) {
            if (tmax <= 0) {
                return "severe_cold";
            }
            if (tmax <= 10) {
                return "cold";
            }
            if (tmax <= 20) {
                return "cool";
            }
            if (tmax <= 28) {
                return "mild";
            }
            return "hot";
        }
        boolean north = lat != null && lat >= 38;
        if (month == 12 || month == 1 || month == 2) {
            return north ? "severe_cold" : "cold";
        }
        if (month >= 3 && month <= 5) {
            return "cool";
        }
        if (month >= 6 && month <= 8) {
            return "hot";
        }
        return north ? "cool" : "mild";
    }

    /**
     * 生成分组清单。{@code rows} 为空表示没有预报，走季节估算。
     *
     * @return {@code [{group, items}]}，顺序即建议展示顺序
     */
    public List<Map<String, Object>> build(String city, int days, LocalDate startDate, List<WeatherRow> rows) {
        int d = Math.max(1, Math.min(days, 30));
        String name = city == null ? "" : city.trim();
        int month = startDate != null ? startDate.getMonthValue() : LocalDate.now().getMonthValue();

        Integer tmax = null;
        Integer precip = null;
        if (rows != null && !rows.isEmpty()) {
            tmax = rows.stream().mapToInt(WeatherRow::tmax).max().orElse(0);
            precip = rows.stream().mapToInt(r -> r.precip() == null ? 0 : r.precip()).max().orElse(0);
        }
        Optional<double[]> center = geo.center(name);
        Double lat = center.map(c -> c[0]).orElse(null);
        String band = band(tmax, month, lat);

        List<Map<String, Object>> groups = new ArrayList<>();
        groups.add(group("证件与票据", new ArrayList<>(DOCS)));

        List<String> clothes = new ArrayList<>(CLOTHES.get(band));
        int wash = Math.min(d, 5);
        clothes.add("换洗内衣袜子 " + wash + " 套（按 " + d + " 天行程，中途可洗）");
        groups.add(group("衣物与鞋", clothes));

        groups.add(group("电子设备", new ArrayList<>(ELECTRONICS)));
        groups.add(group("洗护与药品", new ArrayList<>(TOILETRIES)));

        List<String> special = new ArrayList<>();
        if (precip != null && precip >= 40) {
            special.add("雨具（降水概率约 " + precip + "%，折叠伞 + 一次性雨衣各一）");
            special.add("防水鞋套或备用鞋（雨天鞋子湿了最难熬）");
        } else if (band.equals("cool") || band.equals("mild")) {
            special.add("折叠伞（天气多变，晴雨两用）");
        }
        if (band.equals("hot") || (tmax != null && tmax >= 28)) {
            special.add("太阳镜 + 遮阳帽");
            special.add("防蚊液 / 驱蚊贴（夏季傍晚户外必备）");
        }
        if (band.equals("cold") || band.equals("severe_cold")) {
            special.add("润唇膏 + 护手霜（干冷地区皮肤容易裂）");
        }
        if (COASTAL.stream().anyMatch(name::contains)) {
            special.add("泳衣 + 沙滩鞋（海滨目的地）");
            special.add("手机防水袋");
        }
        if (PLATEAU.stream().anyMatch(name::contains)) {
            special.add("高倍防晒 + 保湿面膜（高原紫外线强、空气干）");
            special.add("葡萄糖 / 便携氧气（初上高原备用）");
        }
        if (d >= 5) {
            special.add("折叠行李袋（回程带特产用）");
        }
        if (!special.isEmpty()) {
            groups.add(group("季节专项", special));
        }
        groups.add(group("行前预订", new ArrayList<>(BOOKING)));

        if (tmax == null) {
            groups.add(group("说明", List.of("以上按季节与目的地估算，出发前 3 天请再看一次天气，按实际温度调整衣物")));
        }
        return groups;
    }

    private Map<String, Object> group(String name, List<String> items) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("group", name);
        m.put("items", items);
        return m;
    }
}
