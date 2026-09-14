package com.portfolio.cow.modules.agent.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/** 牧场智能体消息审计：user / assistant 逐条落库，含 token 用量 */
@Data
@TableName("agent_message")
public class AgentMessage {

    public static final String ROLE_USER = "user";
    public static final String ROLE_ASSISTANT = "assistant";

    @TableId(type = IdType.AUTO)
    private Long id;
    private String sessionId;
    private String role;
    private String content;
    private Integer tokensInput;
    private Integer tokensOutput;
    private LocalDateTime createTime;
}
