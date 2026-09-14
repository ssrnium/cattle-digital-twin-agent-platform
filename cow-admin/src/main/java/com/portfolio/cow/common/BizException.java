package com.portfolio.cow.common;

import lombok.Getter;

@Getter
public class BizException extends RuntimeException {

    private final int code;

    public BizException(String message) {
        this(ResultCode.ERROR.getCode(), message);
    }

    public BizException(ResultCode rc) {
        this(rc.getCode(), rc.getMessage());
    }

    public BizException(int code, String message) {
        super(message);
        this.code = code;
    }
}
