package com.portfolio.cow.modules.agent.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class AgentChatRequest {

    /** 为空则 cow-agent 新建会话；前端/Agent 侧字段为 session_id（snake_case） */
    @JsonProperty("session_id")
    private String sessionId;

    @NotBlank(message = "message 不能为空")
    private String message;
}
