package com.travel.trip;

import com.travel.ai.AiClient.PlanItem;
import com.travel.common.BizException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

/**
 * 行程模板库。
 *
 * <p>解决的是「面对空白页不知道从哪下手」：新建行程后先套一个节奏，
 * 用户改起来比从零写快得多。模板只给**骨架**（什么时候做什么类型的事），
 * 不写具体景点 —— 具体景点需要城市知识，那是 AI 生成那一步的事。
 *
 * <p>结构是「抵达日 + 中间日循环 + 返程日」：这样 2 天的行程和 7 天的行程
 * 都不会出现「第三天还在抵达」或者「最后一天排满景点」这种明显不合理的排法。
 */
@Service
public class TripTemplateService {

    public record Template(String key, String name, String description, List<String> tags) {}

    /** 一天里的一个时段：{slot, kind, title, note}。 */
    private record Slot(String slot, String kind, String title, String note) {}

    /** 一套模板：抵达日 / 中间日（可循环）/ 返程日。 */
    private record Plan(List<Slot> arrival, List<List<Slot>> middle, List<Slot> departure) {}

    private static final List<Template> TEMPLATES =
            List.of(
                    new Template("classic", "三天两夜经典", "第一次来一座城市最稳的节奏：抵达安顿 → 核心景点 → 收尾返程", List.of("通用", "首刷")),
                    new Template("family", "亲子家庭", "上午精神好安排主项目，下午留白，晚上早回酒店", List.of("带娃", "节奏慢")),
                    new Template("photo", "摄影出片", "围绕日出、日落与蓝调时刻排机位，白天留给转场与踩点", List.of("出片", "早出晚归")),
                    new Template("food", "美食探店", "以早茶、小吃街、夜市为锚点，景点只做消食用", List.of("吃货", "少走路")));

    private static final Map<String, Plan> PLANS = new LinkedHashMap<>();

    static {
        PLANS.put(
                "classic",
                new Plan(
                        List.of(
                                slot("上午", "transit", "抵达 + 酒店寄存行李", "先安顿再出门，别拖着箱子逛"),
                                slot("下午", "spot", "老城区 / 城市地标", "先建立方位感，找一条主街慢慢走"),
                                slot("晚上", "food", "本地特色晚餐 + 夜景", "提前查好营业时间，热门店要取号")),
                        List.of(
                                List.of(
                                        slot("上午", "spot", "核心景点（提前预约）", "门票与预约方式以景区公告为准"),
                                        slot("下午", "experience", "博物馆 / 特色街区", "下雨或暴晒时的最佳备选"),
                                        slot("晚上", "food", "小吃街扫街", "少量多样，别在第一家吃饱")),
                                List.of(
                                        slot("上午", "spot", "近郊景点", "路上时间要算进去"),
                                        slot("下午", "experience", "手作 / 演出 / 温泉", "给行程留一点非景点的体验"),
                                        slot("晚上", "food", "本地人常去的馆子", "离景区远一点，价格差一半"))),
                        List.of(
                                slot("上午", "spot", "补漏：没去成的那个", "留一个机动名额，行程才不容易崩"),
                                slot("下午", "transit", "返程", "预留 2 小时到站 / 到机场"))));
        PLANS.put(
                "family",
                new Plan(
                        List.of(
                                slot("上午", "transit", "抵达 + 入住（选带早餐的）", "孩子午睡时间要留出来"),
                                slot("下午", "spot", "公园 / 动物园", "推车能走的路优先"),
                                slot("晚上", "food", "酒店附近解决晚饭", "别为了网红店跑远路")),
                        List.of(
                                List.of(
                                        slot("上午", "experience", "科技馆 / 海洋馆", "室内项目，天气无关"),
                                        slot("下午", "spot", "亲子友好景点", "避开长台阶与排队 1 小时以上的项目"),
                                        slot("晚上", "food", "早回酒店", "保证第二天状态"))),
                        List.of(
                                slot("上午", "spot", "轻松收尾", "留出收拾行李的时间"),
                                slot("下午", "transit", "返程", "按孩子作息挑班次"))));
        PLANS.put(
                "photo",
                new Plan(
                        List.of(
                                slot("上午", "transit", "抵达 + 踩点", "先看机位与光线方向"),
                                slot("下午", "spot", "老城 / 建筑群", "下午侧光出质感"),
                                slot("傍晚", "spot", "日落机位", "提前 40 分钟到位占位")),
                        List.of(
                                List.of(
                                        slot("清晨", "spot", "日出机位", "查好日出时间，提前 30 分钟到"),
                                        slot("下午", "experience", "室内馆 / 展", "正午光硬，转室内"),
                                        slot("傍晚", "spot", "蓝调时刻 + 夜景", "三脚架与快门线别忘"))),
                        List.of(
                                slot("清晨", "spot", "补拍", "天气不好就换成街拍"),
                                slot("下午", "transit", "返程", "存储卡留够空间"))));
        PLANS.put(
                "food",
                new Plan(
                        List.of(
                                slot("上午", "transit", "抵达 + 放下行李", "先去吃一顿当地早饭"),
                                slot("下午", "food", "老字号 / 本地菜", "错峰 14:00 后不用排队"),
                                slot("晚上", "food", "夜市 / 小吃街", "少量多样，边走边吃")),
                        List.of(
                                List.of(
                                        slot("上午", "spot", "消食：公园或市场", "菜市场最能看出本地口味"),
                                        slot("下午", "food", "下午茶 / 甜品", "留肚子给晚饭"),
                                        slot("晚上", "food", "预约制餐厅", "热门店提前 3 天订"))),
                        List.of(
                                slot("上午", "food", "带走的特产", "真空包装才扛得住路上"),
                                slot("下午", "transit", "返程", "液体类记得托运"))));
    }

    private static Slot slot(String slot, String kind, String title, String note) {
        return new Slot(slot, kind, title, note);
    }

    public List<Template> all() {
        return TEMPLATES;
    }

    /**
     * 按天数展开模板。
     * 1 天 = 只有抵达日；2 天 = 抵达 + 返程；3 天以上中间日按模板循环填充。
     */
    public List<PlanItem> expand(String key, int days) {
        Plan plan = PLANS.get(key);
        if (plan == null) {
            throw BizException.badRequest("没有这个模板：" + key);
        }
        int d = Math.max(1, Math.min(days, 30));
        List<PlanItem> out = new ArrayList<>();
        append(out, 1, plan.arrival());
        if (d >= 2) {
            for (int day = 2; day <= d - 1; day++) {
                append(out, day, plan.middle().get((day - 2) % plan.middle().size()));
            }
            append(out, d, plan.departure());
        }
        return out;
    }

    private void append(List<PlanItem> out, int day, List<Slot> slots) {
        for (Slot s : slots) {
            out.add(new PlanItem(day, s.slot(), s.kind(), s.title(), s.note()));
        }
    }
}
