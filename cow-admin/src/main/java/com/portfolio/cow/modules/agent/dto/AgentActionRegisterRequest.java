package com.portfolio.cow.modules.agent.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.Map;

/** cow-agent park 写操作时向 admin 注册待审批动作的请求 */
@Data
public class AgentActionRegisterRequest {

    @NotBlank
    private String sessionId;

    @NotBlank
    private String tool;

    /** 工具入参（create_work_order 的 snake_case 参数），用于参数摘要防篡改 */
    private Map<String, Object> params;
}
