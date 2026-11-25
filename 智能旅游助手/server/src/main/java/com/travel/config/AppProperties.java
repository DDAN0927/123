package com.travel.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 全部外部依赖的开关都集中在这里，避免散落的 {@code @Value}。
 * 配置项见 {@code application.yml} 的 {@code app.*}。
 */
@ConfigurationProperties(prefix = "app")
public record AppProperties(Jwt jwt, Admin admin, boolean allowRegistration, Ai ai, Weather weather) {

    public record Jwt(String secret, long ttlSeconds) {}

    public record Admin(String username, String password) {}

    public record Ai(String baseUrl, String internalSecret, int timeoutSeconds) {}

    public record Weather(String baseUrl, int timeoutSeconds) {}
}
