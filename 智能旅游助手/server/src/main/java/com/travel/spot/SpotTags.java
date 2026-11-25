package com.travel.spot;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * 标签推导与时长估算。
 *
 * <p>规则放在一个类里，是因为「种子导入」和「后台手工录入」必须用同一套规则：
 * 两处各写一份，早晚会出现「导入的景点带『室内』、手录的不带」，
 * 用户按「室内」筛出来的结果就漏掉一半，而且没有任何报错。
 *
 * <p>标签是<b>粗粒度</b>的：目的是让「下雨天想逛室内」「带娃找亲子」这种一句话需求
 * 能被筛出来，不是做内容画像。标签越多越难维护，所以只保留 8 个固定值。
 */
public final class SpotTags {

    /** 全部合法标签，前端「我的偏好」也从这里取。 */
    public static final List<String> ALL = List.of("室内", "室外", "免费", "亲子", "拍照", "历史", "夜游", "少走路");

    /** 与高德快照 k 字段对齐，另加手录时可能用到的「自然」「美食」。 */
    public static final List<String> CATEGORIES = List.of("地标", "公园", "古迹", "场馆", "亲子", "街区", "自然", "美食");

    private SpotTags() {}

    public static List<String> parse(String raw) {
        if (raw == null || raw.isBlank()) {
            return List.of();
        }
        Set<String> out = new LinkedHashSet<>();
        for (String s : raw.split("[,，]")) {
            String t = s.trim();
            if (!t.isEmpty()) {
                out.add(t);
            }
        }
        return new ArrayList<>(out);
    }

    public static String join(List<String> tags) {
        if (tags == null || tags.isEmpty()) {
            return "";
        }
        Set<String> out = new LinkedHashSet<>();
        for (String t : tags) {
            if (t != null && !t.isBlank()) {
                out.add(t.trim());
            }
        }
        return String.join(",", out);
    }

    /**
     * 按分类 + 名称关键词 + 门票推导标签。
     *
     * <p>门票 {@code null}（未录入）时不打「免费」标签：宁可漏掉，也不能把收费景点
     * 标成免费——用户按免费筛出来跑到门口买票，比筛不出来更伤。
     */
    public static List<String> derive(String category, String name, BigDecimal ticketPrice) {
        Set<String> tags = new LinkedHashSet<>();
        String cat = category == null ? "" : category.trim();
        String n = name == null ? "" : name;

        switch (cat) {
            case "场馆" -> {
                tags.add("室内");
                tags.add("少走路");
                tags.add("亲子");
            }
            case "公园" -> {
                tags.add("室外");
                tags.add("亲子");
                tags.add("拍照");
            }
            case "古迹" -> {
                tags.add("历史");
                tags.add("室外");
            }
            case "街区" -> {
                tags.add("拍照");
                tags.add("夜游");
            }
            case "亲子" -> {
                tags.add("亲子");
                tags.add("室外");
            }
            case "地标" -> tags.add("拍照");
            case "自然" -> {
                tags.add("室外");
                tags.add("拍照");
            }
            case "美食" -> {
                tags.add("夜游");
                tags.add("少走路");
            }
            default -> { }
        }

        if (containsAny(n, "博物馆", "纪念馆", "美术馆", "科技馆", "展览馆", "图书馆")) {
            tags.add("室内");
            tags.add("少走路");
        }
        if (containsAny(n, "乐园", "动物园", "海洋馆", "水族馆", "游乐")) {
            tags.add("亲子");
        }
        if (containsAny(n, "古镇", "古街", "老街", "夜市", "外滩", "步行街", "风情街")) {
            tags.add("拍照");
            tags.add("夜游");
        }
        if (containsAny(n, "寺", "庙", "塔", "宫", "祠", "故居", "遗址", "陵", "城墙", "关")) {
            tags.add("历史");
        }
        if (containsAny(n, "山", "湖", "海", "湿地", "森林", "峡谷", "瀑布", "岛")) {
            tags.add("室外");
            tags.add("拍照");
        }
        if (ticketPrice != null && ticketPrice.compareTo(BigDecimal.ZERO) == 0) {
            tags.add("免费");
        }
        return new ArrayList<>(tags);
    }

    /** 建议时长（分钟）：按分类给一个保守值，后台可以改。 */
    public static int suggestMinutes(String category) {
        if (category == null) {
            return 90;
        }
        return switch (category.trim()) {
            case "场馆" -> 120;
            case "公园" -> 90;
            case "古迹" -> 90;
            case "街区" -> 90;
            case "亲子" -> 180;
            case "地标" -> 45;
            case "自然" -> 150;
            case "美食" -> 60;
            default -> 90;
        };
    }

    private static boolean containsAny(String text, String... keys) {
        for (String k : keys) {
            if (text.contains(k)) {
                return true;
            }
        }
        return false;
    }
}
