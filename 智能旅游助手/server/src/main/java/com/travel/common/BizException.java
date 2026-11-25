package com.travel.common;

import org.springframework.http.HttpStatus;

/**
 * 业务异常：带 HTTP 状态码，由 {@link GlobalExceptionHandler} 统一转成
 * {@code {"detail": "..."}} —— 与前端（以及原 Python 服务）的约定一致，
 * 前端只读 {@code detail} 一个字段。
 */
public class BizException extends RuntimeException {

    private final HttpStatus status;

    public BizException(String message) {
        this(HttpStatus.BAD_REQUEST, message);
    }

    public BizException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus status() {
        return status;
    }

    public static BizException notFound(String message) {
        return new BizException(HttpStatus.NOT_FOUND, message);
    }

    public static BizException forbidden(String message) {
        return new BizException(HttpStatus.FORBIDDEN, message);
    }

    public static BizException unauthorized(String message) {
        return new BizException(HttpStatus.UNAUTHORIZED, message);
    }

    public static BizException badRequest(String message) {
        return new BizException(HttpStatus.BAD_REQUEST, message);
    }
}
