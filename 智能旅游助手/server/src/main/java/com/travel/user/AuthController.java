package com.travel.user;

import com.travel.config.AppProperties;
import com.travel.security.CurrentUser;
import com.travel.spot.SpotService;
import com.travel.user.AuthDtos.AuthResp;
import com.travel.user.AuthDtos.ChangePasswordReq;
import com.travel.user.AuthDtos.LoginReq;
import com.travel.user.AuthDtos.PreferenceReq;
import com.travel.user.AuthDtos.RegisterReq;
import com.travel.user.AuthDtos.SimpleMessage;
import com.travel.user.AuthDtos.UserView;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService auth;
    private final CurrentUser currentUser;
    private final AppProperties props;
    private final SpotService spotService;

    public AuthController(AuthService auth, CurrentUser currentUser, AppProperties props, SpotService spotService) {
        this.auth = auth;
        this.currentUser = currentUser;
        this.props = props;
        this.spotService = spotService;
    }

    /**
     * 登录页选项：前端据此决定是否显示「注册」入口。只暴露布尔开关，无敏感信息。
     *
     * <p>{@code rate_limit_enabled} 以前恒为 false：那时候 Python 侧确实有
     * {@code auth_rate_limit}，但 {@code /api/auth} 从来没被反代到 Python，
     * 那段限流一次都没执行过 —— 开关说 false 反倒是「诚实」的。S-03 之后 Spring 侧
     * 真的会限流了，这个开关必须跟着说真话，否则调用方会以为可以无限重试。
     *
     * <p>两个 {@code *_per_minute} 字段是旧 Python 配置的残留（按分钟计）。本版本改成
     * 「5 分钟滑动窗口 + 连续失败锁定」，按分钟折算没有意义，所以恒为 0；保留键名只是
     * 为了不改变响应形状（前端目前一个字段都没读，改动风险为零）。
     */
    @GetMapping("/options")
    public Map<String, Object> options() {
        return Map.of(
                "allow_registration", props.allowRegistration(),
                "rate_limit_enabled", true,
                "rate_limit_anonymous_per_minute", 0,
                "rate_limit_per_minute", 0);
    }

    @PostMapping("/register")
    public AuthResp register(@Valid @RequestBody RegisterReq req) {
        return auth.register(req.username(), req.password());
    }

    @PostMapping("/login")
    public AuthResp login(@Valid @RequestBody LoginReq req) {
        return auth.login(req.username(), req.password());
    }

    @GetMapping("/me")
    public UserView me() {
        return auth.me(currentUser.username());
    }

    /**
     * 改密：返回新 token。
     *
     * <p>改密会让此前签发的所有 token 失效（会话世代 +1），包括当前这台设备的。
     * 所以这里必须发一个新的回去，否则前端一改完密码就被自己踢下线。
     */
    @PostMapping("/change-password")
    public AuthResp changePassword(@Valid @RequestBody ChangePasswordReq req) {
        return auth.changePassword(currentUser.username(), req.oldPassword(), req.newPassword());
    }

    /** 无状态：服务端无需处理，前端删掉本地 token 即可。保留接口是为了前端调用不出 404。 */
    @PostMapping("/logout")
    public SimpleMessage logout() {
        return new SimpleMessage("已退出登录");
    }

    /** 我的偏好标签。返回空数组而不是 null，前端少一个判空分支。 */
    @GetMapping("/preferences")
    public Map<String, Object> preferences() {
        return Map.of("tags", spotService.preferences(currentUser.username()));
    }

    /** 保存偏好标签（最多 8 个）。推荐接口立刻按新偏好生效。 */
    @PutMapping("/preferences")
    public Map<String, Object> savePreferences(@Valid @RequestBody PreferenceReq req) {
        return Map.of("tags", spotService.savePreferences(currentUser.username(), req.tags()));
    }
}
