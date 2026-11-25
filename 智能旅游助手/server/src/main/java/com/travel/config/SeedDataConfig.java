package com.travel.config;

import com.travel.user.UserEntity;
import com.travel.user.UserRepository;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * 启动期数据初始化。
 *
 * <p>只建不覆盖：管理员已存在就不动密码 —— 否则每次重启都会把改过的密码冲回配置值，
 * 这在容器环境里会被误当成「账号被重置」。
 *
 * <p><b>口令为空时宁可不建号</b>：早先这里回落到内置默认口令 {@code admin123}，
 * 于是「什么都没配」的部署会得到一个 admin/admin123 的可用管理员账号 —— 而站点还
 * 允许匿名对话、登录又不限流，等于把后台交出去。现在改成：没配就不建，并打一条
 * ERROR 说明怎么配；运维必须显式给一个口令才能有管理员。
 */
@Configuration
public class SeedDataConfig {

    private static final Logger log = LoggerFactory.getLogger(SeedDataConfig.class);

    /** 常见弱口令：不拒绝（那是运维的显式选择），但要在日志里喊出来。 */
    private static final Set<String> WEAK_PASSWORDS =
            Set.of("admin", "admin123", "123456", "12345678", "password", "111111", "admin888");

    private static final int RECOMMENDED_MIN_LENGTH = 10;

    @Bean
    public ApplicationRunner seedAdmin(UserRepository users, PasswordEncoder encoder, AppProperties props) {
        return args -> {
            String name = props.admin().username();
            if (name == null || name.isBlank() || users.existsByUsername(name)) {
                return;
            }
            String password = props.admin().password();
            if (password == null || password.isBlank()) {
                log.error(
                        "未创建管理员账号「{}」：ADMIN_PASSWORD 未设置。"
                                + "需要管理员时请设置环境变量 ADMIN_PASSWORD（建议 ≥{} 位随机串）后重启；"
                                + "已有账号登录后可在页面右上角「修改密码」自助改密，忘记口令再用 scripts/admin_password.py 重置。",
                        name,
                        RECOMMENDED_MIN_LENGTH);
                return;
            }
            if (WEAK_PASSWORDS.contains(password.toLowerCase()) || password.length() < RECOMMENDED_MIN_LENGTH) {
                log.warn(
                        "管理员账号「{}」的口令偏弱（长度 {}，或属于常见弱口令）。"
                                + "该账号已创建，但请尽快在页面右上角「修改密码」改成 ≥{} 位的随机串"
                                + "（忘记口令时用 scripts/admin_password.py 重置）。",
                        name,
                        password.length(),
                        RECOMMENDED_MIN_LENGTH);
            }
            users.save(new UserEntity(name, encoder.encode(password), "admin"));
            log.info("已创建默认管理员：{}", name);
        };
    }
}
