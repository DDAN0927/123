package com.travel.trip;

import com.travel.security.CurrentUser;
import com.travel.trip.TripDtos.TripView;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 模板与公开分享接口。 */
@RestController
public class TemplateAndShareController {

    private final TripTemplateService templates;
    private final TripService trips;
    private final CurrentUser currentUser;

    public TemplateAndShareController(TripTemplateService templates, TripService trips, CurrentUser currentUser) {
        this.templates = templates;
        this.trips = trips;
        this.currentUser = currentUser;
    }

    /** 模板列表是公开的：官网展示与登录前的预览都要用。 */
    @GetMapping("/api/templates")
    public Map<String, Object> templates() {
        return Map.of("templates", templates.all());
    }

    @PostMapping("/api/trips/{id}/templates/{key}")
    public Map<String, Object> apply(@PathVariable String id, @PathVariable String key) {
        return trips.applyTemplate(currentUser.username(), id, key);
    }

    /** 分享页只读数据：token 即凭证，不带用户名等隐私字段。 */
    @GetMapping("/api/share/{token}")
    public Map<String, Object> shared(@PathVariable String token) {
        TripView view = trips.byShareToken(token);
        return Map.of("trip", view);
    }

    /**
     * 把 /s/{token} 交给分享页处理：页面自己从 URL 取 token，服务端不做渲染。
     *
     * <p>这里必须显式 forward，**不能返回 "forward:/share.html" 字符串** ——
     * 本类是 @RestController，返回的 String 会被 StringHttpMessageConverter 当成响应体
     * 直接写出去，浏览器上就只显示一行 "forward:/share.html"，分享页完全打不开。
     */
    @GetMapping("/s/{token}")
    public void sharePage(@PathVariable String token, HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        request.getRequestDispatcher("/share.html").forward(request, response);
    }

    /**
     * /s 与 /s/（没有 token）也交给分享页：页面自己的无 token 分支会说
     * 「链接不完整，请向分享者要一份新的链接」。不补这条映射的话，空 token
     * 落不到上面的 {token} 变量（Spring 的路径变量不匹配空段），用户直接
     * 看到裸的 {"detail":"Not Found"} JSON —— 页面、样式、人话全没有。
     */
    @GetMapping({"/s", "/s/"})
    public void sharePageWithoutToken(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        request.getRequestDispatcher("/share.html").forward(request, response);
    }

    /** 供前端渲染下拉框：支持的条目类型。 */
    @GetMapping("/api/trips/meta/kinds")
    public Map<String, Object> kinds() {
        return Map.of("kinds", List.of("spot", "food", "stay", "transit", "experience", "doc"));
    }
}
