package com.portfolio.cow.modules.agent.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class AgentConfirmRequest {

    /** 前端/Agent 侧字段为 session_id（snake_case） */
    @JsonProperty("session_id")
    @NotBlank(message = "sessionId 不能为空")
    private String sessionId;

    @NotNull(message = "approved 不能为空")
    private Boolean approved;
}
