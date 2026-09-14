package com.portfolio.cow.modules.device.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

@Data
@TableName(value = "device", autoResultMap = true)
public class Device {

    public static final String TYPE_CAMERA = "CAMERA";
    public static final String TYPE_EDGE_NODE = "EDGE_NODE";

    @TableId(type = IdType.AUTO)
    private Long id;
    private String deviceId;
    /** 设备凭证（心跳 / HTTP 事件上报校验），不入响应序列化 */
    private String deviceKey;
    private String type;
    private String name;
    private String barnId;
    private LocalDateTime lastHeartbeatAt;
    private LocalDateTime lastSyncAt;
    private Integer pendingCount;
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> meta;
}
