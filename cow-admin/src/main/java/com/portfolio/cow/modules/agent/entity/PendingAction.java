package com.portfolio.cow.modules.agent.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 智能体写操作待审批动作：审批下沉到后端后的强制凭证。
 * cow-agent park 时注册（PENDING，120s 有效），用户本人审批后置 APPROVED/REJECTED，
 * svc-agent 建单携带 X-Action-Id，事务内建单并置 EXECUTED（exactly-once）。
 */
@Data
@TableName("pending_action")
public class PendingAction {

    public static final String STATUS_PENDING = "PENDING";
    public static final String STATUS_APPROVED = "APPROVED";
    public static final String STATUS_REJECTED = "REJECTED";
    public static final String STATUS_EXECUTED = "EXECUTED";
    public static final String STATUS_EXPIRED = "EXPIRED";

    @TableId(type = IdType.AUTO)
    private Long id;
    private String actionId;
    private String sessionId;
    private String username;
    private String tool;
    private String paramsJson;
    private String paramsDigest;
    private String status;
    private LocalDateTime expireAt;
    private LocalDateTime createdAt;
    private LocalDateTime executedAt;
    private Long workOrderId;
}
