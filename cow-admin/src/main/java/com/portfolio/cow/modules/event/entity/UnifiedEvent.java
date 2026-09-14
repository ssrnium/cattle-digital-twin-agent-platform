package com.portfolio.cow.modules.event.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 统一事件模型（对应规划书完整事件契约的 MVP 子集）。
 * event_id 全局唯一，是幂等去重键；重复 event_id 绝不重复落库、绝不重复告警。
 */
@Data
@TableName(value = "unified_event", autoResultMap = true)
public class UnifiedEvent {

    public static final String TYPE_MOUNTING = "MOUNTING";
    public static final String TYPE_LAMENESS = "LAMENESS";
    public static final String TYPE_DEVICE_OFFLINE = "DEVICE_OFFLINE";
    public static final String TYPE_DEVICE_RECOVERED = "DEVICE_RECOVERED";
    public static final String TYPE_SYNC_STATE = "SYNC_STATE";

    @TableId(type = IdType.AUTO)
    private Long id;
    private String schemaVersion;
    private String tenantId;
    private String farmId;
    private String eventId;
    private String cowId;
    private String deviceId;
    private String eventType;
    private LocalDateTime eventTime;
    private LocalDateTime ingestTime;
    private String quality;
    private Double confidence;
    private String modelVersion;
    private String evidenceRef;
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> raw;
}
