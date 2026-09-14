package com.portfolio.cow.modules.agent.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/** 牧场智能体会话审计：记录哪个业务账号发起了哪个 agent 会话 */
@Data
@TableName("agent_session")
public class AgentSession {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String sessionId;
    private String username;
    private LocalDateTime createTime;
    private LocalDateTime lastActiveTime;
}
