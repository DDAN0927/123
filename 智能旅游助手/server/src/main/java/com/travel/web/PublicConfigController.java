package com.travel.web;

import jakarta.annotation.PostConstruct;
import java.util.LinkedHashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** 公开配置与健康检查。 */
@RestController
public class PublicConfigController {

    private static final Logger log = LoggerFactory.getLogger(PublicConfigController.class);

    /**
     * 项目自带的高德 Web 端(JS API) Key 与安全密钥，仅用于演示。
     *
     * <p>为什么可以写进仓库：这两个值**本来就要发到浏览器**（JS API 2.0 必须在加载
     * amap 脚本之前注入 {@code window._AMapSecurityConfig}），不是服务端密钥；
     * 真正的访问控制靠高德控制台的域名白名单。自部署者请用环境变量换成自己的 Key。
     *
     * <p>为什么要有默认值：之前只读环境变量、默认空串，于是同一个仓库部署出的两个
     * 站点一个能看地图、一个显示「地图加载失败」，缺的那个还得去平台后台补环境变量。
     * 默认值让「什么都不配」也能跑起来，配了就用配的。
     *
     * <p>为什么不用 {@code @Value("${AMAP_KEY:默认值}")}：环境变量存在但**为空串**
     * 时 Spring 会取空串、默认值失效（docker-compose 里 {@code ${AMAP_KEY:-}} 就是这种
     * 写法）。所以这里自己做 blank 兜底，和 Python 侧 app/config.py 的行为一致。
     */
    private static final String DEFAULT_AMAP_KEY = "88db79732b445f23505ffa0e5acba520";

    private static final String DEFAULT_AMAP_JS_CODE = "9b91cb0707f38ec51dedd85a0a982fe3";

    /** 环境变量名与 .env / docker-compose 统一为 AMAP_SECURITY_JS_CODE；兼容早期的 AMAP_JS_CODE。 */
    @Value("${AMAP_KEY:}")
    private String amapKey;

    @Value("${AMAP_SECURITY_JS_CODE:${AMAP_JS_CODE:}}")
    private String amapJsCode;

    private String resolvedKey;
    private String resolvedJsCode;

    /**
     * 高德 Key 运行时下发：写死在前端就没法让自部署者换成自己的 Key。
     */
    @GetMapping("/api/config")
    public Map<String, Object> config() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("amap_key", resolvedKey);
        out.put("amap_security_js_code", resolvedJsCode);
        return out;
    }

    @GetMapping("/api/health")
    public Map<String, Object> health() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("status", "ok");
        out.put("server", "spring-boot");
        return out;
    }

    /** 启动时解析一次（/api/config 每个页面都会调，不能在里面打日志）。 */
    @PostConstruct
    void resolve() {
        resolvedKey = pick(amapKey, DEFAULT_AMAP_KEY);
        resolvedJsCode = pick(amapJsCode, DEFAULT_AMAP_JS_CODE);
        if (!DEFAULT_AMAP_KEY.equals(resolvedKey)) {
            log.info("高德 Key 使用环境变量提供的值，请确认控制台域名白名单包含当前访问域名");
        }
    }

    /** 环境变量没配或配成空串时回落到项目默认值（空串会让地图直接不可用，比默认值更糟）。 */
    private static String pick(String configured, String fallback) {
        return (configured == null || configured.isBlank()) ? fallback : configured.trim();
    }
}
