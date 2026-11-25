package com.travel.user;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Map;

/** 认证相关的请求/响应体。用 record：无 getter 样板，Jackson 也能直接序列化。 */
public final class AuthDtos {

    private AuthDtos() {}

    public record RegisterReq(
            @NotBlank(message = "不能为空")
                    @Size(min = 3, max = 20, message = "长度需在 3-20 之间")
                    String username,
            @NotBlank(message = "不能为空") @Size(min = 6, max = 64, message = "长度需在 6-64 之间") String password) {}

    public record LoginReq(@NotBlank(message = "不能为空") String username, @NotBlank(message = "不能为空") String password) {}

    public record ChangePasswordReq(
            @NotBlank(message = "不能为空") String oldPassword,
            @NotBlank(message = "不能为空") @Size(min = 6, max = 64, message = "长度需在 6-64 之间") String newPassword) {}

    public record AuthResp(String token, String username, String role) {}

    /** 个人信息：偏好标签随「我是谁」一起返回，前端登录后就能直接渲染偏好面板。 */
    public record UserView(String username, String role, java.util.List<String> preferenceTags) {}

    /** 偏好标签维护（任务书 3(1)：个人信息与偏好标签维护）。 */
    public record PreferenceReq(
            @Size(max = 8, message = "最多选 8 个偏好") java.util.List<String> tags) {}

    public record SimpleMessage(String message) {}

    public record Options(boolean allowRegistration, boolean rateLimitEnabled) {
        public Map<String, Object> toMap() {
            return Map.of("allow_registration", allowRegistration, "rate_limit_enabled", rateLimitEnabled);
        }
    }
}
