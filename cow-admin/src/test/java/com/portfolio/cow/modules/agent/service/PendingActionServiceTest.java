package com.portfolio.cow.modules.agent.service;

import com.portfolio.cow.common.BizException;
import com.portfolio.cow.modules.agent.entity.AgentSession;
import com.portfolio.cow.modules.agent.entity.PendingAction;
import com.portfolio.cow.modules.agent.mapper.AgentSessionMapper;
import com.portfolio.cow.modules.agent.mapper.PendingActionMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 智能体写操作审批下沉（PENDING_ACTION）：注册绑定发起人、批准人=发起人、
 * 过期作废、重复审批 409、执行前状态/摘要校验。
 */
@ExtendWith(MockitoExtension.class)
class PendingActionServiceTest {

    @Mock
    private PendingActionMapper pendingActionMapper;
    @Mock
    private AgentSessionMapper sessionMapper;

    @InjectMocks
    private PendingActionService pendingActionService;

    private static final Map<String, Object> PARAMS = Map.of(
            "type", "VET_CHECK", "cow_id", "COW-0042", "description", "跛行复核");

    private AgentSession sessionOf(String username) {
        AgentSession s = new AgentSession();
        s.setSessionId("sess-0001");
        s.setUsername(username);
        return s;
    }

    private PendingAction actionOf(String status, String username, LocalDateTime expireAt) {
        PendingAction a = new PendingAction();
        a.setId(1L);
        a.setActionId("act-0001");
        a.setSessionId("sess-0001");
        a.setUsername(username);
        a.setTool("create_work_order");
        a.setParamsDigest(ActionDigest.ofToolParams(PARAMS));
        a.setStatus(status);
        a.setExpireAt(expireAt);
        a.setCreatedAt(LocalDateTime.now());
        return a;
    }

    @Test
    void registerBindsInitiatorFromAgentSession() {
        // 发起人取自 agent_session（svc-agent 无法伪造），有效期 120s，参数摘要落库
        when(sessionMapper.selectOne(any())).thenReturn(sessionOf("vet"));

        PendingAction action = pendingActionService.register("sess-0001", "create_work_order", PARAMS);

        ArgumentCaptor<PendingAction> captor = ArgumentCaptor.forClass(PendingAction.class);
        verify(pendingActionMapper).insert(captor.capture());
        PendingAction saved = captor.getValue();
        assertEquals("vet", saved.getUsername());
        assertEquals(PendingAction.STATUS_PENDING, saved.getStatus());
        assertEquals(ActionDigest.ofToolParams(PARAMS), saved.getParamsDigest());
        assertEquals(PendingActionService.TTL_SECONDS,
                ChronoUnit.SECONDS.between(saved.getCreatedAt(), saved.getExpireAt()));
        assertEquals(action.getActionId(), saved.getActionId());
    }

    @Test
    void registerUnknownSessionRejected() {
        when(sessionMapper.selectOne(any())).thenReturn(null);
        BizException e = assertThrows(BizException.class,
                () -> pendingActionService.register("ghost", "create_work_order", PARAMS));
        assertEquals(400, e.getCode());
    }

    @Test
    void confirmByNonInitiatorForbidden() {
        // 批准人≠发起人 → 403，且不发生状态迁移
        when(pendingActionMapper.selectOne(any()))
                .thenReturn(actionOf(PendingAction.STATUS_PENDING, "admin", LocalDateTime.now().plusSeconds(60)));

        BizException e = assertThrows(BizException.class,
                () -> pendingActionService.resolveForConfirm("sess-0001", true, "vet"));
        assertEquals(403, e.getCode());
    }

    @Test
    void confirmExpiredActionVoided() {
        // 超期 PENDING 审批 → 置 EXPIRED 并拒绝
        when(pendingActionMapper.selectOne(any()))
                .thenReturn(actionOf(PendingAction.STATUS_PENDING, "admin", LocalDateTime.now().minusSeconds(1)));

        BizException e = assertThrows(BizException.class,
                () -> pendingActionService.resolveForConfirm("sess-0001", true, "admin"));
        assertEquals(400, e.getCode());
        verify(pendingActionMapper).update(isNull(), any()); // PENDING→EXPIRED 条件更新
    }

    @Test
    void confirmApproveTransitionsPendingToApproved() {
        when(pendingActionMapper.selectOne(any()))
                .thenReturn(actionOf(PendingAction.STATUS_PENDING, "admin", LocalDateTime.now().plusSeconds(60)));
        when(pendingActionMapper.update(isNull(), any())).thenReturn(1);

        PendingAction action = pendingActionService.resolveForConfirm("sess-0001", true, "admin");
        assertEquals("act-0001", action.getActionId());
    }

    @Test
    void confirmDuplicateApprovalConflict() {
        // 条件更新 0 行 = 已被并发审批 → 409
        when(pendingActionMapper.selectOne(any()))
                .thenReturn(actionOf(PendingAction.STATUS_PENDING, "admin", LocalDateTime.now().plusSeconds(60)));
        when(pendingActionMapper.update(isNull(), any())).thenReturn(0);

        BizException e = assertThrows(BizException.class,
                () -> pendingActionService.resolveForConfirm("sess-0001", true, "admin"));
        assertEquals(409, e.getCode());
    }

    @Test
    void validateExecutableRejectsReplayWithConflict() {
        // EXECUTED 凭证再提交 → 409（exactly-once 的业务层提示）
        when(pendingActionMapper.selectOne(any()))
                .thenReturn(actionOf(PendingAction.STATUS_EXECUTED, "admin", LocalDateTime.now().plusSeconds(60)));

        BizException e = assertThrows(BizException.class,
                () -> pendingActionService.validateExecutable("act-0001", ActionDigest.ofToolParams(PARAMS)));
        assertEquals(409, e.getCode());
    }

    @Test
    void validateExecutableRejectsUnapproved() {
        // 仍 PENDING（未批准）→ 403
        when(pendingActionMapper.selectOne(any()))
                .thenReturn(actionOf(PendingAction.STATUS_PENDING, "admin", LocalDateTime.now().plusSeconds(60)));

        BizException e = assertThrows(BizException.class,
                () -> pendingActionService.validateExecutable("act-0001", ActionDigest.ofToolParams(PARAMS)));
        assertEquals(403, e.getCode());
    }

    @Test
    void validateExecutableRejectsExpiredApproval() {
        // APPROVED 但已超期 → 403
        when(pendingActionMapper.selectOne(any()))
                .thenReturn(actionOf(PendingAction.STATUS_APPROVED, "admin", LocalDateTime.now().minusSeconds(1)));

        BizException e = assertThrows(BizException.class,
                () -> pendingActionService.validateExecutable("act-0001", ActionDigest.ofToolParams(PARAMS)));
        assertEquals(403, e.getCode());
    }

    @Test
    void validateExecutableRejectsDigestMismatch() {
        // 批准后参数被改 → 摘要不符 403
        when(pendingActionMapper.selectOne(any()))
                .thenReturn(actionOf(PendingAction.STATUS_APPROVED, "admin", LocalDateTime.now().plusSeconds(60)));

        BizException e = assertThrows(BizException.class,
                () -> pendingActionService.validateExecutable("act-0001", "tampered-digest"));
        assertEquals(403, e.getCode());
    }

    @Test
    void digestDetectsParamTamperAndDefaults() {
        String base = ActionDigest.ofToolParams(PARAMS);
        Map<String, Object> tampered = Map.of(
                "type", "VET_CHECK", "cow_id", "COW-0042", "description", "被篡改的描述");
        assertNotEquals(base, ActionDigest.ofToolParams(tampered));
        // priority 缺省与显式 NORMAL 同摘要（cow_tools 默认补 NORMAL，两侧口径一致）
        Map<String, Object> withPriority = Map.of(
                "type", "VET_CHECK", "cow_id", "COW-0042",
                "priority", "NORMAL", "description", "跛行复核");
        assertEquals(base, ActionDigest.ofToolParams(withPriority));
    }
}
