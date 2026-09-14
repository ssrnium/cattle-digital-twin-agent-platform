package com.portfolio.cow.modules.system.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("sys_operation_log")
public class SysOperationLog {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String title;
    private String username;
    private String method;
    private String requestUri;
    private String requestIp;
    private String params;
    private String status;
    private String errorMsg;
    private LocalDateTime operateTime;
}
