package com.travel.user;

import com.travel.common.BizException;
import com.travel.config.AppProperties;
import com.travel.security.JwtService;
import com.travel.user.AuthDtos.AuthResp;
import com.travel.user.AuthDtos.UserView;
import java.time.Instant;
import java.util.regex.Pattern;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** 注册、登录、改密与默认管理员初始化。 */
@Service
public class AuthService {

    private static final Pattern USERNAME = Pattern.compile("^[A-Za-z0-9_\\u4e00-\\u9fa5]{3,20}$");

    private final UserRepository users;
    private final PasswordEncoder encoder;
    private final JwtService jwt;
    private final AppProperties props;

    public AuthService(UserRepository users, PasswordEncoder encoder, JwtService jwt, AppProperties props) {
        this.users = users;
        this.encoder = encoder;
        this.jwt = jwt;
        this.props = props;
    }

    @Transactional
    public AuthResp register(String username, String password) {
        if (!props.allowRegistration()) {
            throw BizException.forbidden("本站已关闭开放注册，请联系管理员开通账号");
        }
        return create(username, password, "user");
    }

    /** 管理员创建账号走这里（不受开放注册开关限制）。 */
    @Transactional
    public AuthResp create(String username, String password, String role) {
        String name = username == null ? "" : username.trim();
        if (!USERNAME.matcher(name).matches()) {
            throw BizException.badRequest("用户名需为 3-20 位字母、数字、下划线或中文");
        }
        if (password == null || password.length() < 6) {
            throw BizException.badRequest("密码至少 6 位");
        }
        if (users.existsByUsername(name)) {
            throw BizException.badRequest("用户名已存在");
        }
        UserEntity saved = users.save(new UserEntity(name, encoder.encode(password), role));
        return new AuthResp(jwt.issue(saved.getUsername(), saved.getRole(), saved.epoch()), saved.getUsername(), saved.getRole());
    }

    @Transactional(readOnly = true)
    public AuthResp login(String username, String password) {
        // 401 而不是 400：这不是「参数写错了」，是「凭据不对」。
        // 同时不区分「用户不存在」与「密码错误」—— 否则等于给了一个枚举账号的接口。
        UserEntity user =
                users.findByUsername(username == null ? "" : username.trim())
                        .orElseThrow(() -> BizException.unauthorized("用户名或密码错误"));
        if (!encoder.matches(password == null ? "" : password, user.getPasswordHash())) {
            throw BizException.unauthorized("用户名或密码错误");
        }
        return new AuthResp(jwt.issue(user.getUsername(), user.getRole(), user.epoch()), user.getUsername(), user.getRole());
    }

    /**
     * 改密并踢掉此前所有会话。
     *
     * <p>返回一个新 token：世代 +1 之后，连当前这台设备的旧 token 也失效了，
     * 不返回新 token 就等于「改完密码自己被登出」，体验很差。
     */
    @Transactional
    public AuthResp changePassword(String username, String oldPassword, String newPassword) {
        UserEntity user =
                users.findByUsername(username).orElseThrow(() -> BizException.unauthorized("用户不存在"));
        if (!encoder.matches(oldPassword == null ? "" : oldPassword, user.getPasswordHash())) {
            throw BizException.badRequest("原密码不正确");
        }
        if (newPassword == null || newPassword.length() < 6) {
            throw BizException.badRequest("新密码至少 6 位");
        }
        user.setPasswordHash(encoder.encode(newPassword));
        user.setPasswordChangedAt(Instant.now());
        user.bumpTokenEpoch();
        UserEntity saved = users.save(user);
        return new AuthResp(jwt.issue(saved.getUsername(), saved.getRole(), saved.epoch()), saved.getUsername(), saved.getRole());
    }

    @Transactional(readOnly = true)
    public UserView me(String username) {
        UserEntity user =
                users.findByUsername(username).orElseThrow(() -> BizException.unauthorized("用户不存在"));
        return new UserView(user.getUsername(), user.getRole(), com.travel.spot.SpotTags.parse(user.getPreferenceTags()));
    }
}
