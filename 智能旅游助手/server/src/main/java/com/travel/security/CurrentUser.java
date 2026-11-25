package com.travel.security;

import com.travel.common.BizException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

/** 从 SecurityContext 取当前用户。控制器只依赖它，不直接碰 SecurityContextHolder。 */
@Component
public class CurrentUser {

    /** 当前用户；未登录抛 401（公开接口不要用它）。 */
    public AuthUser require() {
        AuthUser user = optional();
        if (user == null) {
            throw BizException.unauthorized("未登录或登录已过期");
        }
        return user;
    }

    public String username() {
        return require().username();
    }

    /** 管理员校验：越权用 403，与「未登录 401」区分开，前端才能给出不同提示。 */
    public String requireAdmin() {
        AuthUser user = require();
        if (!user.isAdmin()) {
            throw BizException.forbidden("需要管理员权限");
        }
        return user.username();
    }

    public AuthUser optional() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof AuthUser user)) {
            return null;
        }
        return user;
    }
}
