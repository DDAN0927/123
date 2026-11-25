package com.travel.trip;

import com.travel.ai.AiClient;
import com.travel.common.BizException;
import com.travel.trip.TripDtos.BudgetView;
import com.travel.trip.TripDtos.CreateReq;
import com.travel.trip.TripDtos.DayView;
import com.travel.trip.TripDtos.ItemCreateReq;
import com.travel.trip.TripDtos.ItemUpdateReq;
import com.travel.trip.TripDtos.ItemView;
import com.travel.trip.TripDtos.PackingView;
import com.travel.trip.TripDtos.ProgressView;
import com.travel.trip.TripDtos.ShareView;
import com.travel.trip.TripDtos.TripView;
import com.travel.trip.TripDtos.UpdateReq;
import com.travel.trip.TripDtos.WeatherRow;
import com.travel.trip.TripDtos.WeatherView;
import java.security.SecureRandom;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 行程业务。
 *
 * <p>两条贯穿全类的设计约束：
 * <ol>
 *   <li><b>写操作做到条目粒度</b>：勾选、改一条、删一条各有自己的方法。没有「整篇覆盖」
 *       接口 —— 勾选是最频繁的操作，整篇 PUT 会让用户勾到一半的进度在改一个字之后归零。</li>
 *   <li><b>越权一律 404</b>：不是 403。403 等于告诉对方「这个 id 存在，只是你没权限」。</li>
 * </ol>
 */
@Service
public class TripService {

    private static final Set<String> KINDS = Set.of("spot", "food", "stay", "transit", "experience", "packing", "doc");
    private static final SecureRandom RANDOM = new SecureRandom();

    private final TripRepository trips;
    private final TripItemRepository items;
    private final ExpenseRepository expenses;
    private final WeatherService weather;
    private final PackingService packing;
    private final AiClient ai;
    private final ExpenseService expenseService;
    private final TripTemplateService templates;
    private final com.travel.note.TripNoteRepository notes;

    public TripService(
            TripRepository trips,
            TripItemRepository items,
            ExpenseRepository expenses,
            WeatherService weather,
            PackingService packing,
            AiClient ai,
            ExpenseService expenseService,
            TripTemplateService templates,
            com.travel.note.TripNoteRepository notes) {
        this.trips = trips;
        this.items = items;
        this.expenses = expenses;
        this.weather = weather;
        this.packing = packing;
        this.ai = ai;
        this.expenseService = expenseService;
        this.templates = templates;
        this.notes = notes;
    }

    // ------------------------------------------------------------ 行程本体

    @Transactional
    public TripView create(String username, CreateReq req) {
        String id = HexFormat.of().formatHex(randomBytes(6));
        String title = req.title() == null || req.title().isBlank() ? req.city().trim() + "之行" : req.title().trim();
        TripEntity trip = new TripEntity(id, username, req.city().trim(), title);
        trip.setDays(req.days() == null ? 3 : req.days());
        trip.setBudget(req.budget() == null ? 0 : req.budget());
        trip.setNote(req.note());
        trip.setStartDate(parseDate(req.startDate(), true));
        return view(trips.save(trip), false);
    }

    @Transactional(readOnly = true)
    public List<TripView> list(String username) {
        return trips.findByUsernameOrderByUpdatedAtDesc(username).stream().map(t -> view(t, false)).toList();
    }

    @Transactional(readOnly = true)
    public TripView get(String username, String id) {
        return view(owned(id, username), true);
    }

    @Transactional
    public TripView update(String username, String id, UpdateReq req) {
        TripEntity trip = owned(id, username);
        if (req.city() != null && !req.city().isBlank()) {
            trip.setCity(req.city().trim());
        }
        if (req.title() != null && !req.title().isBlank()) {
            trip.setTitle(req.title().trim());
        }
        if (req.days() != null) {
            trip.setDays(req.days());
        }
        if (req.budget() != null) {
            trip.setBudget(req.budget());
        }
        if (req.note() != null) {
            trip.setNote(req.note());
        }
        if (req.startDate() != null) {
            trip.setStartDate(parseDate(req.startDate(), true));
        }
        trip.touch();
        return view(trips.save(trip), true);
    }

    @Transactional
    public void delete(String username, String id) {
        TripEntity trip = owned(id, username);
        items.deleteByTrip(id);
        expenses.deleteByTrip(id);
        // 游记跟着行程走：行程删了游记留着就成了孤儿，详情页再也进不去
        notes.deleteByTripId(id);
        trips.delete(trip);
    }

    // ------------------------------------------------------------ 条目

    @Transactional
    public TripView addItem(String username, String id, ItemCreateReq req) {
        TripEntity trip = owned(id, username);
        int day = req.dayIndex() == null ? 0 : Math.max(0, Math.min(req.dayIndex(), trip.getDays()));
        String kind = req.kind() == null || !KINDS.contains(req.kind()) ? (day == 0 ? "doc" : "spot") : req.kind();
        int sort = (int) items.findByTripIdOrderByDayIndexAscSortAscIdAsc(id).stream().filter(i -> i.getDayIndex() == day).count();
        TripItemEntity item = new TripItemEntity(id, day, trim(req.slot(), 20), kind, trim(req.title(), 120), sort);
        item.setNote(trim(req.note(), 500));
        items.save(item);
        trip.touch();
        trips.save(trip);
        return view(trip, true);
    }

    @Transactional
    public TripView updateItem(String username, String id, Long itemId, ItemUpdateReq req) {
        TripEntity trip = owned(id, username);
        TripItemEntity item = items.findByIdAndTripId(itemId, id).orElseThrow(() -> BizException.notFound("条目不存在"));
        if (req.title() != null && !req.title().isBlank()) {
            item.setTitle(trim(req.title(), 120));
        }
        if (req.note() != null) {
            item.setNote(trim(req.note(), 500));
        }
        if (req.slot() != null) {
            item.setSlot(trim(req.slot(), 20));
        }
        if (req.done() != null) {
            item.setDone(req.done());
        }
        items.save(item);
        trip.touch();
        trips.save(trip);
        return view(trip, true);
    }

    @Transactional
    public void deleteItem(String username, String id, Long itemId) {
        owned(id, username);
        TripItemEntity item = items.findByIdAndTripId(itemId, id).orElseThrow(() -> BizException.notFound("条目不存在"));
        items.delete(item);
    }

    // ------------------------------------------------------------ 装备清单

    @Transactional
    public PackingView generatePacking(String username, String id) {
        TripEntity trip = owned(id, username);
        List<WeatherRow> rows = weather.forecast(trip.getCity(), trip.getDays(), trip.getStartDate());
        List<Map<String, Object>> groups = packing.build(trip.getCity(), trip.getDays(), trip.getStartDate(), rows);

        // 只删自动生成的 packing 条目：用户手加的（kind=doc）要留着，
        // 「重新生成清单」不该把手工内容一起抹掉。
        items.deleteGeneratedPacking(id);
        int sort = 0;
        for (Map<String, Object> g : groups) {
            @SuppressWarnings("unchecked")
            List<String> list = (List<String>) g.get("items");
            for (String title : list) {
                TripItemEntity item = new TripItemEntity(id, 0, String.valueOf(g.get("group")), "packing", trim(title, 120), sort++);
                items.save(item);
            }
        }
        trip.touch();
        trips.save(trip);
        return new PackingView(
                rows.isEmpty() ? "season" : "forecast",
                groups,
                rows,
                rows.isEmpty() ? List.of() : weather.advice(rows));
    }

    // ------------------------------------------------------------ 每日行程（AI）

    @Transactional
    public Map<String, Object> plan(String username, String id) {
        TripEntity trip = owned(id, username);
        List<AiClient.PlanItem> plan = ai.plan(trip.getCity(), trip.getDays(), trip.getBudget());
        replaceItinerary(trip, plan, Map.of());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", plan.size());
        out.put("trip", view(trip, true));
        return out;
    }

    /**
     * 自然语言改行程。
     *
     * <p>已勾选的条目按标题保留勾选状态：用户勾了三项，改一句「第三天换室内」，
     * 进度不该被清零 —— 这是「改」与「重来」的区别。
     */
    @Transactional
    public Map<String, Object> revise(String username, String id, String instruction) {
        TripEntity trip = owned(id, username);
        List<ItemView> current = itemViews(id).stream().filter(i -> i.dayIndex() >= 1).toList();
        if (current.isEmpty()) {
            throw BizException.badRequest("还没有每日安排，先生成一次再修改");
        }
        List<AiClient.PlanItem> revised = ai.revise(trip.getCity(), trip.getDays(), instruction, current);
        Map<String, Boolean> doneByTitle = new HashMap<>();
        itemEntities(id).stream().filter(i -> i.getDayIndex() >= 1).forEach(i -> doneByTitle.put(i.getTitle(), i.isDone()));
        replaceItinerary(trip, revised, doneByTitle);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", revised.size());
        out.put("trip", view(trip, true));
        return out;
    }

    // ------------------------------------------------------------ 模板

    /** 套用模板：只替换行程条目，不动行前清单（清单是用户勾到一半的东西）。 */
    @Transactional
    public Map<String, Object> applyTemplate(String username, String id, String key) {
        TripEntity trip = owned(id, username);
        List<AiClient.PlanItem> plan = templates.expand(key, trip.getDays());
        replaceItinerary(trip, plan, Map.of());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", plan.size());
        out.put("trip", view(trip, true));
        return out;
    }

    /**
     * 用新计划替换每日行程（day_index >= 1）。
     *
     * <p>行前清单（day_index = 0）不动 —— 那是用户勾到一半的东西。
     * {@code doneByTitle} 用来把已勾选条目的状态带到新条目上：改一句需求不该让进度归零。
     */
    private void replaceItinerary(TripEntity trip, List<AiClient.PlanItem> plan, Map<String, Boolean> doneByTitle) {
        items.deleteItinerary(trip.getId());
        int sort = 0;
        for (AiClient.PlanItem p : plan) {
            int day = Math.max(1, Math.min(p.day(), trip.getDays()));
            TripItemEntity item =
                    new TripItemEntity(
                            trip.getId(),
                            day,
                            trim(p.slot(), 20),
                            KINDS.contains(p.kind()) ? p.kind() : "spot",
                            trim(p.title(), 120),
                            sort++);
            item.setNote(trim(p.note(), 500));
            item.setDone(Boolean.TRUE.equals(doneByTitle.get(item.getTitle())));
            items.save(item);
        }
        trip.touch();
        trips.save(trip);
    }

    // ------------------------------------------------------------ 天气

    public WeatherView tripWeather(String username, String id) {
        TripEntity trip = owned(id, username);
        List<WeatherRow> rows = weather.forecast(trip.getCity(), trip.getDays(), trip.getStartDate());
        if (rows.isEmpty()) {
            return new WeatherView(
                    false,
                    "暂时拿不到「" + trip.getCity() + "」的预报：可能是出发日期超出 16 天预报窗口，或城市未收录在坐标库中",
                    null,
                    List.of(),
                    List.of());
        }
        return new WeatherView(true, null, "open-meteo", rows, weather.advice(rows));
    }

    // ------------------------------------------------------------ 分享

    @Transactional
    public ShareView share(String username, String id) {
        TripEntity trip = owned(id, username);
        if (trip.getShareToken() == null) {
            trip.setShareToken(HexFormat.of().formatHex(randomBytes(9)));
            trip.touch();
            trips.save(trip);
        }
        return new ShareView(trip.getShareToken(), "/s/" + trip.getShareToken());
    }

    @Transactional
    public void unshare(String username, String id) {
        TripEntity trip = owned(id, username);
        trip.setShareToken(null);
        trip.touch();
        trips.save(trip);
    }

    /** 分享页读取：只读视图，且不带任何隐私字段（用户名、备注里的私人信息不外泄）。 */
    @Transactional(readOnly = true)
    public TripView byShareToken(String token) {
        TripEntity trip = trips.findByShareToken(token).orElseThrow(() -> BizException.notFound("分享链接已失效"));
        return view(trip, true, true);
    }

    // ------------------------------------------------------------ 内部

    TripEntity owned(String id, String username) {
        return trips.findByIdAndUsername(id, username).orElseThrow(() -> BizException.notFound("行程不存在或无权访问"));
    }

    private List<TripItemEntity> itemEntities(String id) {
        return items.findByTripIdOrderByDayIndexAscSortAscIdAsc(id);
    }

    private List<ItemView> itemViews(String id) {
        return itemEntities(id).stream()
                .map(i -> new ItemView(i.getId(), i.getDayIndex(), i.getSlot(), i.getKind(), i.getTitle(), i.getNote(), i.isDone()))
                .toList();
    }

    private TripView view(TripEntity trip, boolean full) {
        return view(trip, full, false);
    }

    private TripView view(TripEntity trip, boolean full, boolean readonly) {
        List<ItemView> all = itemViews(trip.getId());
        List<ItemView> prep = all.stream().filter(i -> i.dayIndex() == 0).toList();

        Map<Integer, List<ItemView>> byDay = new LinkedHashMap<>();
        all.stream().filter(i -> i.dayIndex() >= 1).forEach(i -> byDay.computeIfAbsent(i.dayIndex(), k -> new ArrayList<>()).add(i));
        List<DayView> itinerary = byDay.entrySet().stream().map(e -> new DayView(e.getKey(), e.getValue())).toList();

        int total = all.size();
        int done = (int) all.stream().filter(ItemView::done).count();
        ProgressView progress = new ProgressView(done, total, total == 0 ? 0 : Math.round(done * 100f / total));

        Integer countdown = null;
        String phase = "undated";
        if (trip.getStartDate() != null) {
            long delta = ChronoUnit.DAYS.between(LocalDate.now(), trip.getStartDate());
            countdown = (int) delta;
            if (delta > 0) {
                phase = "upcoming";
            } else if (delta > -trip.getDays()) {
                phase = "ongoing";
            } else {
                phase = "past";
            }
        }

        BudgetView budget = expenseService.budget(trip.getId(), trip.getBudget());
        return new TripView(
                trip.getId(),
                trip.getCity(),
                trip.getTitle(),
                trip.getStartDate() == null ? "" : trip.getStartDate().toString(),
                trip.getDays(),
                trip.getBudget(),
                trip.getNote(),
                countdown,
                phase,
                progress,
                prep,
                full ? itinerary : List.of(),
                readonly ? null : trip.getShareToken(),
                budget,
                readonly,
                conflicts(trip, all));
    }

    /**
     * 排期冲突检查（任务书 2(2)）。
     *
     * <p>四条规则都只产出「人话提示」，不阻塞保存：行程规划本来就是不断试错的过程，
     * 硬性拒绝会逼着用户去猜系统的规则，而提示只是把「可能排不下」提前告诉他。
     */
    static List<String> conflicts(TripEntity trip, List<ItemView> all) {
        List<String> out = new ArrayList<>();
        Map<Integer, List<ItemView>> byDay = new LinkedHashMap<>();
        for (ItemView i : all) {
            if (i.dayIndex() >= 1) {
                byDay.computeIfAbsent(i.dayIndex(), k -> new ArrayList<>()).add(i);
            }
        }
        for (Map.Entry<Integer, List<ItemView>> e : byDay.entrySet()) {
            int day = e.getKey();
            List<ItemView> list = e.getValue();
            if (day > trip.getDays()) {
                out.add("第 " + day + " 天超出行程天数（共 " + trip.getDays() + " 天），这部分不会被算进日程");
            }
            Map<String, List<String>> bySlot = new LinkedHashMap<>();
            for (ItemView i : list) {
                String slot = i.slot() == null ? "" : i.slot().trim();
                if (!slot.isEmpty()) {
                    bySlot.computeIfAbsent(slot, k -> new ArrayList<>()).add(i.title());
                }
            }
            for (Map.Entry<String, List<String>> s : bySlot.entrySet()) {
                if (s.getValue().size() > 1) {
                    out.add("第 " + day + " 天「" + s.getKey() + "」安排了 " + s.getValue().size() + " 项（"
                            + String.join("、", s.getValue()) + "），时间可能撞车");
                }
            }
            Map<String, Integer> seen = new LinkedHashMap<>();
            for (ItemView i : list) {
                seen.merge(i.title(), 1, Integer::sum);
            }
            seen.forEach((title, n) -> {
                if (n > 1) {
                    out.add("第 " + day + " 天「" + title + "」重复安排了 " + n + " 次");
                }
            });
            if (list.size() > 6) {
                out.add("第 " + day + " 天安排了 " + list.size() + " 项，一天可能跑不完，建议留点机动时间");
            }
        }
        return out;
    }

    /** 空串/空白一律当「没填」；日期格式错误不静默吞掉，直接告诉用户。 */
    static LocalDate parseDate(String raw, boolean allowBlank) {
        if (raw == null || raw.isBlank()) {
            if (allowBlank) {
                return null;
            }
            throw BizException.badRequest("日期不能为空");
        }
        try {
            return LocalDate.parse(raw.trim());
        } catch (RuntimeException e) {
            throw BizException.badRequest("日期格式应为 YYYY-MM-DD");
        }
    }

    static String trim(String s, int max) {
        if (s == null) {
            return "";
        }
        String t = s.trim();
        return t.length() <= max ? t : t.substring(0, max);
    }

    private static byte[] randomBytes(int n) {
        byte[] b = new byte[n];
        RANDOM.nextBytes(b);
        return b;
    }
}
