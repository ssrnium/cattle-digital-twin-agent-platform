package com.portfolio.cow.modules.agent.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class AgentConfirmRequest {

    @NotBlank(message = "sessionId 不能为空")
    private String sessionId;

    @NotNull(message = "approved 不能为空")
    private Boolean approved;
}
