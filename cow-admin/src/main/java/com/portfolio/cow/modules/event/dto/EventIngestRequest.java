package com.portfolio.cow.modules.event.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 事件上报契约（边缘/AI 侧 → 平台）。
 * 字段名与边缘模拟器、规划书事件契约保持一致（snake_case）；
 * 与平台对前端的 camelCase API 不同——仅本 DTO 用 @JsonProperty 显式映射。
 */
@Data
public class EventIngestRequest {

    @NotBlank(message = "schema_version 不能为空")
    @JsonProperty("schema_version")
    private String schemaVersion;

    @JsonProperty("tenant_id")
    private String tenantId;

    @JsonProperty("farm_id")
    private String farmId;

    @NotBlank(message = "event_id 不能为空")
    @JsonProperty("event_id")
    private String eventId;

    @JsonProperty("cow_id")
    private String cowId;

    @JsonProperty("device_id")
    private String deviceId;

    @NotBlank(message = "event_type 不能为空")
    @JsonProperty("event_type")
    private String eventType;

    @NotNull(message = "event_time 不能为空")
    @JsonProperty("event_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime eventTime;

    @JsonProperty("ingest_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime ingestTime;

    private String quality;
    private Double confidence;

    @JsonProperty("model_version")
    private String modelVersion;

    @JsonProperty("evidence_ref")
    private String evidenceRef;

    private Map<String, Object> raw;
}
