package com.travel.spot;

import com.travel.security.CurrentUser;
import com.travel.spot.SpotDtos.MetaView;
import com.travel.spot.SpotDtos.PageView;
import com.travel.spot.SpotDtos.SpotView;
import com.travel.spot.SpotDtos.UpsertReq;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 景点库接口（任务书 3(2)）。
 *
 * <p>读接口登录即可用，写接口仅管理员——与 {@code /api/notes} 的权限划分保持一致：
 * 浏览是普通用户的高频操作，维护景点库是低频管理操作。
 */
@RestController
@RequestMapping("/api/spots")
public class SpotController {

    private final SpotService spots;
    private final CurrentUser currentUser;

    public SpotController(SpotService spots, CurrentUser currentUser) {
        this.spots = spots;
        this.currentUser = currentUser;
    }

    /** 条件检索：城市 / 关键词 / 分类 / 标签 / 免费 / 时长上限。 */
    @GetMapping
    public PageView list(
            @RequestParam(required = false) String city,
            @RequestParam(name = "q", required = false) String q,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String tag,
            @RequestParam(required = false) Boolean free,
            @RequestParam(name = "max_minutes", required = false) Integer maxMinutes,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return spots.list(city, q, category, tag, free, maxMinutes, page, size);
    }

    @GetMapping("/meta")
    public MetaView meta() {
        return spots.meta();
    }

    /** 按我的偏好标签匹配计数推荐。未设置偏好时退回评分排序。 */
    @GetMapping("/recommend")
    public Map<String, Object> recommend(
            @RequestParam(required = false) String city, @RequestParam(defaultValue = "12") int limit) {
        List<String> prefs = spots.preferences(currentUser.username());
        return Map.of("tags", prefs, "items", spots.recommend(currentUser.username(), city, Math.max(1, Math.min(60, limit))));
    }

    @GetMapping("/{id}")
    public SpotView get(@PathVariable Long id) {
        return spots.get(id);
    }

    @PostMapping
    public Map<String, Object> create(@Valid @RequestBody UpsertReq req) {
        currentUser.requireAdmin();
        return Map.of("spot", spots.create(req));
    }

    @PutMapping("/{id}")
    public Map<String, Object> update(@PathVariable Long id, @Valid @RequestBody UpsertReq req) {
        currentUser.requireAdmin();
        return Map.of("spot", spots.update(id, req));
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable Long id) {
        currentUser.requireAdmin();
        spots.delete(id);
        return Map.of("message", "已删除");
    }
}
