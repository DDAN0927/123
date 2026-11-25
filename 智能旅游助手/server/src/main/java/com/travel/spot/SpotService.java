package com.travel.spot;

import com.travel.common.BizException;
import com.travel.spot.SpotDtos.MetaView;
import com.travel.spot.SpotDtos.PageView;
import com.travel.spot.SpotDtos.SpotView;
import com.travel.spot.SpotDtos.UpsertReq;
import com.travel.user.UserEntity;
import com.travel.user.UserRepository;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 景点库。
 *
 * <p>筛选在内存里做而不是拼 SQL：单城最多几十条、全库 8000 条，一次全取再过滤
 * 在演示规模下只要几毫秒，而动态 SQL 一旦条件组合写错（比如 {@code free=false}
 * 被当成「不筛」），筛出来的结果是错的却不报错——这类 bug 最难查。
 * 真到十万条量级再换 Specification，接口不用变。
 */
@Service
public class SpotService {

    private final SpotRepository spots;
    private final UserRepository users;

    public SpotService(SpotRepository spots, UserRepository users) {
        this.spots = spots;
        this.users = users;
    }

    // ------------------------------------------------------------ 查询

    @Transactional(readOnly = true)
    public PageView list(
            String city,
            String q,
            String category,
            String tag,
            Boolean free,
            Integer maxMinutes,
            int page,
            int size) {
        String kw = q == null ? "" : q.trim().toLowerCase(Locale.ROOT);
        String cat = category == null ? "" : category.trim();
        String tg = tag == null ? "" : tag.trim();

        List<SpotEntity> pool = city == null || city.isBlank() ? spots.findAll() : spots.findByCityOrderByNameAsc(city.trim());

        List<SpotEntity> hits = new ArrayList<>();
        for (SpotEntity s : pool) {
            if (!cat.isEmpty() && !cat.equals(s.getCategory())) {
                continue;
            }
            if (!tg.isEmpty() && !SpotTags.parse(s.getTags()).contains(tg)) {
                continue;
            }
            if (!kw.isEmpty() && !s.getName().toLowerCase(Locale.ROOT).contains(kw) && !cityHit(s, kw)) {
                continue;
            }
            if (free != null) {
                boolean isFree = s.getTicketPrice() != null && s.getTicketPrice().compareTo(BigDecimal.ZERO) == 0;
                if (free != isFree) {
                    continue;
                }
            }
            if (maxMinutes != null && maxMinutes > 0
                    && s.getSuggestMinutes() != null
                    && s.getSuggestMinutes() > maxMinutes) {
                continue;
            }
            hits.add(s);
        }
        hits.sort(byRatingThenName());

        int p = Math.max(1, page);
        int z = Math.max(1, Math.min(100, size));
        int from = Math.min(hits.size(), (p - 1) * z);
        int to = Math.min(hits.size(), from + z);
        List<SpotView> items = hits.subList(from, to).stream().map(s -> view(s, null)).toList();
        return new PageView(items, hits.size(), p, z);
    }

    @Transactional(readOnly = true)
    public MetaView meta() {
        return new MetaView(SpotTags.CATEGORIES, SpotTags.ALL, new ArrayList<>(spots.distinctCities()), spots.count());
    }

    @Transactional(readOnly = true)
    public SpotView get(Long id) {
        return view(require(id), null);
    }

    /**
     * 按偏好标签匹配计数推荐（任务书 2(3)：标签匹配计数筛选）。
     *
     * <p>打分只有一条规则：偏好标签与景点标签的交集大小。同分时评分高的在前，
     * 再同分按名称稳定排序——排序必须稳定，否则同一个用户刷两次得到不同顺序，
     * 会被当成「随机推荐」而失去可信度。
     */
    @Transactional(readOnly = true)
    public List<SpotView> recommend(String username, String city, int limit) {
        List<String> prefs = preferences(username);
        List<SpotEntity> pool = city == null || city.isBlank() ? spots.findAll() : spots.findByCityOrderByNameAsc(city.trim());
        List<SpotView> out = new ArrayList<>();
        for (SpotEntity s : pool) {
            List<String> tags = SpotTags.parse(s.getTags());
            int hit = 0;
            for (String p : prefs) {
                if (tags.contains(p)) {
                    hit++;
                }
            }
            // 没有偏好时不要「全都 0 分」地硬推：退回按评分排序，至少结果说得通
            if (!prefs.isEmpty() && hit == 0) {
                continue;
            }
            out.add(view(s, prefs.isEmpty() ? 0 : hit));
        }
        out.sort((a, b) -> {
            int c = Integer.compare(nz(b.matchCount()), nz(a.matchCount()));
            if (c != 0) {
                return c;
            }
            c = Double.compare(rating(b.rating()), rating(a.rating()));
            if (c != 0) {
                return c;
            }
            return a.name().compareTo(b.name());
        });
        return out.size() > limit ? out.subList(0, limit) : out;
    }

    /** 当前用户的偏好标签；未设置时返回空列表（不是 null，前端少一个判空分支）。 */
    @Transactional(readOnly = true)
    public List<String> preferences(String username) {
        return users.findByUsername(username).map(u -> SpotTags.parse(u.getPreferenceTags())).orElse(List.of());
    }

    @Transactional
    public List<String> savePreferences(String username, List<String> tags) {
        UserEntity user = users.findByUsername(username).orElseThrow(() -> BizException.unauthorized("用户不存在"));
        List<String> clean = new ArrayList<>();
        for (String t : tags == null ? List.<String>of() : tags) {
            String v = t == null ? "" : t.trim();
            if (!v.isEmpty() && !clean.contains(v)) {
                clean.add(v);
            }
        }
        if (clean.size() > 8) {
            throw BizException.badRequest("最多选 8 个偏好");
        }
        user.setPreferenceTags(SpotTags.join(clean));
        users.save(user);
        return clean;
    }

    // ------------------------------------------------------------ 维护（管理员）

    @Transactional
    public SpotView create(UpsertReq req) {
        String city = req.city().trim();
        String name = req.name().trim();
        spots.findByCityAndName(city, name).ifPresent(s -> {
            throw BizException.badRequest("这个城市已经有同名景点了");
        });
        SpotEntity s = new SpotEntity(city, name, blankTo(req.category(), "地标"));
        apply(s, req);
        return view(spots.save(s), null);
    }

    @Transactional
    public SpotView update(Long id, UpsertReq req) {
        SpotEntity s = require(id);
        s.setCity(req.city().trim());
        s.setName(req.name().trim());
        s.setCategory(blankTo(req.category(), "地标"));
        apply(s, req);
        return view(spots.save(s), null);
    }

    @Transactional
    public void delete(Long id) {
        spots.delete(require(id));
    }

    private void apply(SpotEntity s, UpsertReq req) {
        s.setTicketPrice(req.ticketPrice());
        s.setAddress(req.address());
        s.setLng(req.lng());
        s.setLat(req.lat());
        s.setRating(req.rating());
        s.setOpenTime(req.openTime());
        s.setSuggestMinutes(req.suggestMinutes() == null ? SpotTags.suggestMinutes(s.getCategory()) : req.suggestMinutes());
        // 显式传了标签就用传的；没传则按规则推导，保证「手工录入」与「种子导入」标签口径一致
        s.setTags(req.tags() == null || req.tags().isEmpty()
                ? SpotTags.join(SpotTags.derive(s.getCategory(), s.getName(), s.getTicketPrice()))
                : SpotTags.join(req.tags()));
    }

    private SpotEntity require(Long id) {
        return spots.findById(id).orElseThrow(() -> BizException.notFound("景点不存在"));
    }

    private static SpotView view(SpotEntity s, Integer match) {
        return new SpotView(
                s.getId(),
                s.getCity(),
                s.getName(),
                s.getCategory(),
                SpotTags.parse(s.getTags()),
                s.getTicketPrice(),
                s.getSuggestMinutes(),
                s.getAddress(),
                s.getLng(),
                s.getLat(),
                s.getRating(),
                s.getOpenTime(),
                s.getSource(),
                match);
    }

    private static boolean cityHit(SpotEntity s, String kw) {
        return s.getCity() != null && s.getCity().toLowerCase(Locale.ROOT).contains(kw);
    }

    private static Comparator<SpotEntity> byRatingThenName() {
        return (a, b) -> {
            int c = Double.compare(rating(b.getRating()), rating(a.getRating()));
            return c != 0 ? c : a.getName().compareTo(b.getName());
        };
    }

    private static double rating(String raw) {
        if (raw == null || raw.isBlank()) {
            return 0d;
        }
        try {
            return Double.parseDouble(raw.trim());
        } catch (NumberFormatException e) {
            return 0d;
        }
    }

    private static int nz(Integer v) {
        return v == null ? 0 : v;
    }

    private static String blankTo(String v, String fallback) {
        return v == null || v.isBlank() ? fallback : v.trim();
    }

    /** 供种子导入复用：按城市批量写入并跳过重名。 */
    @Transactional
    public int seedCity(String city, List<List<Object>> rows) {
        Set<String> seen = new LinkedHashSet<>();
        List<SpotEntity> batch = new ArrayList<>();
        for (List<Object> r : rows) {
            String name = String.valueOf(r.get(0)).trim();
            if (name.isEmpty() || !seen.add(name)) {
                continue;
            }
            if (spots.findByCityAndName(city, name).isPresent()) {
                continue;
            }
            String cat = r.size() > 1 ? String.valueOf(r.get(1)) : "";
            SpotEntity s = new SpotEntity(city, name, blankTo(cat, "地标"));
            s.setSource("amap");
            if (r.size() > 2 && r.get(2) != null) {
                s.setLng(asDouble(r.get(2)));
            }
            if (r.size() > 3 && r.get(3) != null) {
                s.setLat(asDouble(r.get(3)));
            }
            s.setAddress(r.size() > 4 ? asString(r.get(4)) : null);
            s.setRating(r.size() > 5 ? asString(r.get(5)) : null);
            s.setOpenTime(r.size() > 6 ? asString(r.get(6)) : null);
            s.setSuggestMinutes(SpotTags.suggestMinutes(s.getCategory()));
            s.setTags(SpotTags.join(SpotTags.derive(s.getCategory(), s.getName(), null)));
            batch.add(s);
        }
        spots.saveAll(batch);
        return batch.size();
    }

    private static String asString(Object o) {
        if (o == null) {
            return null;
        }
        String v = String.valueOf(o).trim();
        return v.isEmpty() ? null : v;
    }

    private static Double asDouble(Object o) {
        try {
            return Double.valueOf(String.valueOf(o));
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
