package com.travel.trip;

import com.travel.security.CurrentUser;
import com.travel.trip.TripDtos.CreateReq;
import com.travel.trip.TripDtos.ItemCreateReq;
import com.travel.trip.TripDtos.ItemUpdateReq;
import com.travel.trip.TripDtos.PackingView;
import com.travel.trip.TripDtos.ReviseReq;
import com.travel.trip.TripDtos.SampleReq;
import com.travel.trip.TripDtos.ShareView;
import com.travel.trip.TripDtos.TripView;
import com.travel.trip.TripDtos.UpdateReq;
import com.travel.trip.TripDtos.WeatherView;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 行程接口。路径与旧 Python 版本完全一致，前端不用改一行就能接过来。
 */
@RestController
@RequestMapping("/api/trips")
public class TripController {

    private final TripService trips;
    private final SampleTripService samples;
    private final CurrentUser currentUser;

    public TripController(TripService trips, SampleTripService samples, CurrentUser currentUser) {
        this.trips = trips;
        this.samples = samples;
        this.currentUser = currentUser;
    }

    @GetMapping
    public Map<String, Object> list() {
        List<TripView> list = trips.list(currentUser.username());
        return Map.of("trips", list);
    }

    @PostMapping
    public Map<String, Object> create(@Valid @RequestBody CreateReq req) {
        return Map.of("trip", trips.create(currentUser.username(), req));
    }

    /**
     * 载入示例行程。
     *
     * <p>独立成一个接口而不是让前端「建行程 + 套模板 + 逐条加条目」：那样要发十几个请求，
     * 中间断一个就留下半份行程。这里一次事务建完，失败什么都不留。
     *
     * <p>同一用户已有示例行程时直接返回那一份（{@code reused=true}），避免反复点击堆出十几份。
     */
    @PostMapping("/sample")
    public Map<String, Object> sample(@Valid @RequestBody(required = false) SampleReq req) {
        String city = req == null ? null : req.city();
        Integer days = req == null ? null : req.days();
        SampleTripService.Result r = samples.create(currentUser.username(), city, days);
        return Map.of("trip", r.trip(), "reused", r.reused());
    }

    @GetMapping("/{id}")
    public Map<String, Object> get(@PathVariable String id) {
        return Map.of("trip", trips.get(currentUser.username(), id));
    }

    @PatchMapping("/{id}")
    public Map<String, Object> update(@PathVariable String id, @Valid @RequestBody UpdateReq req) {
        return Map.of("trip", trips.update(currentUser.username(), id, req));
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable String id) {
        trips.delete(currentUser.username(), id);
        return Map.of("ok", true);
    }

    // ------------------------------------------------------------ 条目

    @PostMapping("/{id}/items")
    public Map<String, Object> addItem(@PathVariable String id, @Valid @RequestBody ItemCreateReq req) {
        return Map.of("trip", trips.addItem(currentUser.username(), id, req));
    }

    @PatchMapping("/{id}/items/{itemId}")
    public Map<String, Object> updateItem(@PathVariable String id, @PathVariable Long itemId, @RequestBody ItemUpdateReq req) {
        return Map.of("trip", trips.updateItem(currentUser.username(), id, itemId, req));
    }

    @DeleteMapping("/{id}/items/{itemId}")
    public Map<String, Object> deleteItem(@PathVariable String id, @PathVariable Long itemId) {
        trips.deleteItem(currentUser.username(), id, itemId);
        return Map.of("ok", true);
    }

    // ------------------------------------------------------------ 装备 / 行程 / 天气

    @PostMapping("/{id}/packing")
    public PackingView packing(@PathVariable String id) {
        return trips.generatePacking(currentUser.username(), id);
    }

    @PostMapping("/{id}/plan")
    public Map<String, Object> plan(@PathVariable String id) {
        return trips.plan(currentUser.username(), id);
    }

    /** 自然语言改行程：说一句「第三天想换室内」就只改那一天，已勾选的条目保留勾选状态。 */
    @PostMapping("/{id}/revise")
    public Map<String, Object> revise(@PathVariable String id, @Valid @RequestBody ReviseReq req) {
        return trips.revise(currentUser.username(), id, req.instruction());
    }

    @GetMapping("/{id}/weather")
    public WeatherView weather(@PathVariable String id) {
        return trips.tripWeather(currentUser.username(), id);
    }

    // ------------------------------------------------------------ 分享

    @PostMapping("/{id}/share")
    public ShareView share(@PathVariable String id) {
        return trips.share(currentUser.username(), id);
    }

    @DeleteMapping("/{id}/share")
    public Map<String, Object> unshare(@PathVariable String id) {
        trips.unshare(currentUser.username(), id);
        return Map.of("ok", true);
    }
}
