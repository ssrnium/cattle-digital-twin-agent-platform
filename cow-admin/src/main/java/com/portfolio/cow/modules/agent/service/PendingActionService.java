package com.portfolio.cow.modules.agent.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.agent.entity.AgentSession;
import com.portfolio.cow.modules.agent.entity.PendingAction;
import com.portfolio.cow.modules.agent.mapper.AgentSessionMapper;
import com.portfolio.cow.modules.agent.mapper.PendingActionMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

/**
 * 智能体写操作审批（后端强制）：注册 → 用户本人审批 → svc-agent 持凭证执行。
 * 状态机：PENDING → APPROVED/REJECTED/EXPIRED，APPROVED → EXECUTED（条件更新，exactly-once）。
 * 所有状态迁移都是"当前状态=前置状态"的条件更新，天然防并发重复。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PendingActionService {

    /** 与 cow-agent CONFIRM_TIMEOUT_SECONDS 保持一致 */
    public static final long TTL_SECONDS = 120;

    private final PendingActionMapper pendingActionMapper;
    private final AgentSessionMapper sessionMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /** cow-agent park 时注册：发起人从 agent_session 绑定（svc-agent 无法伪造） */
    public PendingAction register(String sessionId, String tool, Map<String, Object> params) {
        AgentSession session = sessionMapper.selectOne(new LambdaQueryWrapper<AgentSession>()
                .eq(AgentSession::getSessionId, sessionId));
        if (session == null) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(),
                    "未知会话，无法注册待审批操作: " + sessionId);
        }
        PendingAction action = new PendingAction();
        action.setActionId(UUID.randomUUID().toString().replace("-", ""));
        action.setSessionId(sessionId);
        action.setUsername(session.getUsername());
        action.setTool(tool);
        action.setParamsJson(toJson(params));
        action.setParamsDigest(ActionDigest.ofToolParams(params));
        action.setStatus(PendingAction.STATUS_PENDING);
        action.setCreatedAt(LocalDateTime.now());
        action.setExpireAt(action.getCreatedAt().plusSeconds(TTL_SECONDS));
        pendingActionMapper.insert(action);
        log.info("pending action registered: {} tool={} session={} user={}",
                action.getActionId(), tool, sessionId, session.getUsername());
        return action;
    }

    /**
     * 用户审批：批准人必须=发起人；过期置 EXPIRED；条件更新防重复审批。
     * 返回被迁移的 action（该会话无 PENDING 登记时返回 null，保持纯转发行为）。
     */
    public PendingAction resolveForConfirm(String sessionId, boolean approved, String approver) {
        PendingAction action = pendingActionMapper.selectOne(new LambdaQueryWrapper<PendingAction>()
                .eq(PendingAction::getSessionId, sessionId)
                .eq(PendingAction::getStatus, PendingAction.STATUS_PENDING)
                .orderByDesc(PendingAction::getId)
                .last("LIMIT 1"));
        if (action == null) {
            return null;
        }
        if (!action.getUsername().equals(approver)) {
            throw new BizException(ResultCode.FORBIDDEN.getCode(),
                    "批准人必须是操作发起人（" + action.getUsername() + "）");
        }
        if (action.getExpireAt().isBefore(LocalDateTime.now())) {
            transition(action.getActionId(), PendingAction.STATUS_PENDING, PendingAction.STATUS_EXPIRED, null);
            throw new BizException(ResultCode.BAD_REQUEST.getCode(),
                    "审批已过期（" + TTL_SECONDS + "s 内未处理），操作已作废");
        }
        String target = approved ? PendingAction.STATUS_APPROVED : PendingAction.STATUS_REJECTED;
        int rows = transition(action.getActionId(), PendingAction.STATUS_PENDING, target, null);
        if (rows == 0) {
            throw new BizException(ResultCode.CONFLICT.getCode(), "该操作已被审批，请勿重复提交");
        }
        return action;
    }

    /** cow-agent 超时自动拒绝路径：把仍 PENDING 的凭证作废 */
    public void expireIfPending(String actionId) {
        transition(actionId, PendingAction.STATUS_PENDING, PendingAction.STATUS_EXPIRED, null);
    }

    /** 审批转发 cow-agent 失败（如 park 已超时消失）时的补偿：APPROVED 凭证同步作废，不留悬空 */
    public void voidIfApproved(String actionId) {
        transition(actionId, PendingAction.STATUS_APPROVED, PendingAction.STATUS_EXPIRED, null);
    }

    /** 执行前校验：存在 / 状态=APPROVED / 未过期 / 参数摘要一致 */
    public PendingAction validateExecutable(String actionId, String paramsDigest) {
        PendingAction action = pendingActionMapper.selectOne(new LambdaQueryWrapper<PendingAction>()
                .eq(PendingAction::getActionId, actionId));
        if (action == null) {
            throw new BizException(ResultCode.FORBIDDEN.getCode(), "无效审批凭证（X-Action-Id）");
        }
        if (PendingAction.STATUS_EXECUTED.equals(action.getStatus())) {
            throw new BizException(ResultCode.CONFLICT.getCode(), "该审批已执行过，禁止重复建单");
        }
        if (action.getExpireAt().isBefore(LocalDateTime.now())) {
            if (PendingAction.STATUS_PENDING.equals(action.getStatus())) {
                transition(actionId, PendingAction.STATUS_PENDING, PendingAction.STATUS_EXPIRED, null);
            }
            throw new BizException(ResultCode.FORBIDDEN.getCode(), "审批已过期");
        }
        if (!PendingAction.STATUS_APPROVED.equals(action.getStatus())) {
            throw new BizException(ResultCode.FORBIDDEN.getCode(),
                    "写操作未获批准，当前状态: " + action.getStatus());
        }
        if (!action.getParamsDigest().equals(paramsDigest)) {
            throw new BizException(ResultCode.FORBIDDEN.getCode(), "参数与审批摘要不一致，疑似被篡改");
        }
        return action;
    }

    /** 同事务内 APPROVED→EXECUTED 条件更新；返回 0 行 = 并发重复执行，调用方应回滚 */
    public int markExecuted(String actionId, Long workOrderId) {
        return transition(actionId, PendingAction.STATUS_APPROVED, PendingAction.STATUS_EXECUTED, workOrderId);
    }

    private int transition(String actionId, String from, String to, Long workOrderId) {
        UpdateWrapper<PendingAction> wrapper = new UpdateWrapper<>();
        wrapper.eq("action_id", actionId)
                .eq("status", from)
                .set("status", to)
                .set(workOrderId != null, "work_order_id", workOrderId)
                .set(PendingAction.STATUS_EXECUTED.equals(to), "executed_at", LocalDateTime.now());
        return pendingActionMapper.update(null, wrapper);
    }

    private String toJson(Map<String, Object> params) {
        try {
            return objectMapper.writeValueAsString(params == null ? Map.of() : params);
        } catch (Exception e) {
            return "{}";
        }
    }
}
