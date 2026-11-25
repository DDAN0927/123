package com.travel;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * 个人智能旅游行程规划系统 · SpringBoot 主后端入口。
 *
 * <p>职责边界：
 * <ul>
 *   <li>本服务：用户与认证、行程与条目、预算记账、分享与导出、模板库、静态站点托管；</li>
 *   <li>Python 服务（app/）：检索增强（RAG）与多智能体编排，通过 {@code /api/ai/**} 调用。</li>
 * </ul>
 *
 * <p>排除 {@code UserDetailsServiceAutoConfiguration}：我们用的是自定义 JWT 过滤器链，
 * 不排除的话启动日志会打印一个「随机生成的 security password」，纯属误导。
 */
@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
@ConfigurationPropertiesScan
public class TravelApplication {

    public static void main(String[] args) {
        SpringApplication.run(TravelApplication.class, args);
    }
}
