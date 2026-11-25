package com.travel.common;

import jakarta.validation.ConstraintViolationException;
import java.util.Map;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * 统一错误出口。
 *
 * <p>只暴露 {@code {"detail": "..."}} 一个字段：前端（含旧的 Python 版本）都是按
 * {@code detail} 取错误文案的，换成 Spring 默认的 {@code {timestamp, path, error}}
 * 会让所有错误提示变成 undefined。堆栈只进日志，不回给客户端。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BizException.class)
    public ResponseEntity<Map<String, String>> onBiz(BizException e) {
        return ResponseEntity.status(e.status()).body(Map.of("detail", e.getMessage()));
    }

    /** 参数校验失败：把字段名带上，否则用户只知道「参数错误」 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, String>> onInvalid(MethodArgumentNotValidException e) {
        String msg =
                e.getBindingResult().getFieldErrors().stream()
                        .map(f -> f.getField() + " " + f.getDefaultMessage())
                        .collect(Collectors.joining("；"));
        return ResponseEntity.badRequest().body(Map.of("detail", msg.isBlank() ? "参数不合法" : msg));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<Map<String, String>> onConstraint(ConstraintViolationException e) {
        return ResponseEntity.badRequest().body(Map.of("detail", e.getMessage()));
    }

    @ExceptionHandler(NoHandlerFoundException.class)
    public ResponseEntity<Map<String, String>> onNotFound(NoHandlerFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("detail", "Not Found"));
    }

    /**
     * 静态资源找不到（Spring 6.1 起是 {@link NoResourceFoundException}，不再走
     * {@code NoHandlerFoundException}）。
     *
     * <p>不单独处理的话会掉进下面的 {@code Exception} 兜底，返回 <b>500</b> 并打一条
     * ERROR 堆栈——手打错一个网址、或者浏览器请求 /favicon.ico 就能刷满日志。
     * 缺失的资源是 404，不是服务器故障。
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<Map<String, String>> onNoResource(NoResourceFoundException e) {
        log.debug("资源不存在: {}", e.getResourcePath());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("detail", "Not Found"));
    }

    /**
     * 请求体读不出来：空 body、不是 JSON、JSON 类型对不上。
     *
     * <p>不单独处理的话会掉进下面的 {@code Exception} 兜底，返回 <b>500</b> 并打一条
     * ERROR 堆栈 —— 而扫描器扫登录接口时发的就是空 POST，等于让任何路过的人
     * 把日志刷满、还让监控以为服务在崩。请求方的问题就是 400，不是服务器故障。
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, String>> onUnreadable(HttpMessageNotReadableException e) {
        log.debug("请求体不可解析: {}", e.getMessage());
        return ResponseEntity.badRequest().body(Map.of("detail", "请求体不是合法的 JSON"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, String>> onAny(Exception e) {
        log.error("未处理异常", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Map.of("detail", "服务器内部错误，请稍后重试"));
    }
}
