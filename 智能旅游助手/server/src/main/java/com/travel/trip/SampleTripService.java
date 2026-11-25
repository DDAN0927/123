package com.travel.trip;

import com.travel.common.BizException;
import com.travel.trip.CityGeoService.Spot;
import com.travel.trip.TripDtos.CreateReq;
import com.travel.trip.TripDtos.ExpenseCreateReq;
import com.travel.trip.TripDtos.ItemCreateReq;
import com.travel.trip.TripDtos.TripView;
import java.math.BigDecimal;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.temporal.TemporalAdjusters;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 示例行程：让新用户（以及答辩现场自己点开链接的老师）三十秒内看到工作台装满的样子。
 *
 * <p>为什么要后端做，而不是前端拼几个请求：示例必须**确定**。答辩时网络抖一下、
 * 模型抽一次风，演示就断在那里。这里的内容全部来自 {@code geo-data.js} 的真实景点名，
 * 不调 AI、不查外部接口，同样的城市永远得到同一份结果。
 *
 * <p>为什么不直接复用 {@link TripTemplateService}：模板只给骨架（「核心景点（提前预约）」），
 * 拿去演示看不出这是「北京的行程」。示例行程要具体到景点名，才撑得起「攻略库」的说服力。
 *
 * <p>刻意不做的事：不编造门票价格与开放时间。分类与景点名是地图数据里的事实，
 * 价格是示例值 —— 备注里写清楚，用户才不会拿它当报价单。
 */
@Service
public class SampleTripService {

    /** 标题里带这个词，用来识别「这份是我给的示例」，避免用户重复点击堆出一堆。 */
    private static final String MARK = "示例行程";

    private static final int DEFAULT_DAYS = 3;
    private static final int MAX_DAYS = 7;
    private static final int SAMPLE_BUDGET = 3000;

    private final CityGeoService geo;
    private final TripService trips;
    private final ExpenseService expenses;

    public SampleTripService(CityGeoService geo, TripService trips, ExpenseService expenses) {
        this.geo = geo;
        this.trips = trips;
        this.expenses = expenses;
    }

    /** 返回的 {@code reused} 让前端能说「已为你打开上次那份」而不是假装新建了一份。 */
    public record Result(TripView trip, boolean reused) {}

    @Transactional
    public Result create(String username, String city, Integer days) {
        String target = city == null || city.isBlank() ? "北京" : city.trim();
        if (!geo.contains(target)) {
            throw BizException.badRequest("暂无该城市的地图数据：" + target);
        }
        List<Spot> spots = geo.spots(target);
        if (spots.isEmpty()) {
            throw BizException.badRequest("暂无该城市的景点数据：" + target);
        }

        Optional<TripView> existing = findExisting(username);
        if (existing.isPresent()) {
            return new Result(existing.get(), true);
        }

        int d = days == null ? DEFAULT_DAYS : Math.max(1, Math.min(days, MAX_DAYS));
        // 默认排到下个周六：演示时日期看着像「真的要出门」，比今天更自然
        LocalDate start = LocalDate.now().with(TemporalAdjusters.next(DayOfWeek.SATURDAY));
        TripView trip =
                trips.create(
                        username,
                        new CreateReq(
                                target,
                                start.toString(),
                                d,
                                SAMPLE_BUDGET,
                                target + " " + d + " 日" + MARK,
                                "这是一份" + MARK + "：景点名称来自本地地图数据，门票与花费为示例值，随时可以删除。"));

        for (ItemCreateReq item : plan(target, spots, d)) {
            trips.addItem(username, trip.id(), item);
        }
        for (ItemCreateReq item : prep()) {
            trips.addItem(username, trip.id(), item);
        }
        addExpenses(username, trip.id(), start);
        return new Result(trips.get(username, trip.id()), false);
    }

    private Optional<TripView> findExisting(String username) {
        return trips.list(username).stream()
                .filter(t -> t.title() != null && t.title().contains(MARK))
                .findFirst();
    }

    /**
     * 排一份 3 天的骨架：抵达日 → 中间日 → 返程日。
     *
     * <p>景点按 {@code geo-data.js} 里的顺序取（数据里本来就是按知名度排的），
     * 取完了就用「城市漫步」占位而不是重复同一个景点 —— 重复会让人一眼看出是机器排的。
     * 126 座城市只有 3 个景点，3 天行程必然要用到占位，这是数据本身的边界，不该硬凑。
     */
    private List<ItemCreateReq> plan(String city, List<Spot> spots, int days) {
        List<ItemCreateReq> out = new ArrayList<>();
        int cursor = 0;

        out.add(new ItemCreateReq("抵达 + 酒店寄存行李", 1, "上午", "transit", "先安顿再出门，别拖着箱子逛"));
        if (cursor < spots.size()) {
            out.add(spotItem(spots.get(cursor++), 1, "下午"));
        } else {
            out.add(walkItem(1, "下午"));
        }
        out.add(new ItemCreateReq(city + "本地特色晚餐", 1, "晚上", "food", "热门店提前取号，避开 18:30 的高峰"));

        for (int day = 2; day < days; day++) {
            out.add(cursor < spots.size() ? spotItem(spots.get(cursor++), day, "上午") : walkItem(day, "上午"));
            out.add(cursor < spots.size() ? spotItem(spots.get(cursor++), day, "下午") : walkItem(day, "下午"));
            out.add(new ItemCreateReq("小吃街 / 夜市扫街", day, "晚上", "food", "少量多样，别在第一家吃饱"));
        }

        if (days >= 2) {
            out.add(
                    cursor < spots.size()
                            ? spotItem(spots.get(cursor), days, "上午")
                            : new ItemCreateReq("自由活动 / 补漏", days, "上午", "spot", "留一个机动名额，行程才不容易崩"));
            out.add(new ItemCreateReq("返程", days, "下午", "transit", "预留 2 小时到站 / 到机场"));
        }
        return out;
    }

    /**
     * 三条通用行前项，让「行前清单」面板不是空的。
     *
     * <p>只放**跟天气无关**的东西：装备清单要读预报，示例行程不该联网。
     * 分组名沿用 {@link PackingService} 的（证件与票据 / 电子设备 / 行前预订），
     * 这样用户之后点「生成装备清单」，新生成的条目会和这几条落在同样的分组里。
     *
     * <p>kind 用 {@code packing} 而不是 {@code doc}：用户点生成时这三条会被完整清单替换，
     * 正是想要的效果 —— 示例只负责让他看见面板长什么样。
     */
    private List<ItemCreateReq> prep() {
        return List.of(
                new ItemCreateReq("身份证", 0, "证件与票据", "packing", "住宿登记、景区购票、高铁进站都要用"),
                new ItemCreateReq("充电器与充电宝", 0, "电子设备", "packing", "充电宝要随身带，不能托运"),
                new ItemCreateReq("预约热门景点", 0, "行前预订", "packing", "多数博物馆需提前 3~7 天实名预约"));
    }

    private ItemCreateReq spotItem(Spot spot, int day, String slot) {
        String note =
                switch (spot.category()) {
                    case "美食" -> "本地口味，饭点人多，错峰更舒服";
                    case "自然", "公园" -> "天气好的时候最值，出发前看一下预报";
                    default -> "门票与预约方式以景区公告为准";
                };
        return new ItemCreateReq(spot.name(), day, slot, kindOf(spot.category()), note);
    }

    /** 景点不够时的占位：不编一个不存在的景点名，也不重复用过的。 */
    private ItemCreateReq walkItem(int day, String slot) {
        return new ItemCreateReq("城市漫步 / 老城区闲逛", day, slot, "experience", "不赶景点，跟着街巷走走看看");
    }

    private static String kindOf(String category) {
        return switch (category) {
            case "美食" -> "food";
            case "场馆", "乐园", "亲子", "体验" -> "experience";
            default -> "spot";
        };
    }

    /**
     * 三笔示例花费，让预算面板不是空的。
     *
     * <p>金额是示例值，不是真实票价 —— 所以标题里都带「示例」，用户改起来没有心理负担。
     */
    private void addExpenses(String username, String tripId, LocalDate start) {
        expenses.add(
                username,
                tripId,
                new ExpenseCreateReq("餐饮", "示例：第一天餐饮", new BigDecimal("180"), 1, start.toString()));
        expenses.add(
                username,
                tripId,
                new ExpenseCreateReq(
                        "门票", "示例：景点门票", new BigDecimal("60"), 2, start.plusDays(1).toString()));
        expenses.add(
                username,
                tripId,
                new ExpenseCreateReq(
                        "交通", "示例：市内交通", new BigDecimal("40"), 1, start.toString()));
    }
}
