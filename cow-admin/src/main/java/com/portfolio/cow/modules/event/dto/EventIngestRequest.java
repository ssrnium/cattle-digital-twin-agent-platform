package com.portfolio.cow.modules.event.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 事件上报契约（边缘/AI 侧 → 平台）。
 * 字段名与边缘模拟器、规划书事件契约保持一致。
 */
@Data
public class EventIngestRequest {

    @NotBlank(message = "schema_version 不能为空")
    private String schemaVersion;

    private String tenantId;
    private String farmId;

    @NotBlank(message = "event_id 不能为空")
    private String eventId;

    private String cowId;
    private String deviceId;

    @NotBlank(message = "event_type 不能为空")
    private String eventType;

    @NotNull(message = "event_time 不能为空")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime eventTime;

    private String quality;
    private Double confidence;
    private String modelVersion;
    private String evidenceRef;
    private Map<String, Object> raw;
}
