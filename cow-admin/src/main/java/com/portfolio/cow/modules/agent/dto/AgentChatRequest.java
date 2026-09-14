package com.portfolio.cow.modules.agent.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class AgentChatRequest {

    /** 为空则 cow-agent 新建会话 */
    private String sessionId;

    @NotBlank(message = "message 不能为空")
    private String message;
}
