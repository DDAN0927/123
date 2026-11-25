package com.travel.security;

/** 登录态主体：只放鉴权需要的两个字段，不放实体（避免把密码哈希带进 SecurityContext）。 */
public record AuthUser(String username, String role) {

    public boolean isAdmin() {
        return "admin".equals(role);
    }
}
