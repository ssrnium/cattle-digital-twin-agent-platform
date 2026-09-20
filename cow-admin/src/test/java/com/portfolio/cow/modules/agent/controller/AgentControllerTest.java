package com.portfolio.cow.modules.agent.controller;

import com.portfolio.cow.common.BizException;
import com.portfolio.cow.modules.agent.dto.AgentActionRegisterRequest;
import com.portfolio.cow.modules.agent.dto.AgentChatRequest;
import com.portfolio.cow.modules.agent.dto.AgentConfirmRequest;
import com.portfolio.cow.modules.agent.entity.AgentMessage;
import com.portfolio.cow.modules.agent.entity.AgentSession;
import com.portfolio.cow.modules.agent.entity.PendingAction;
import com.portfolio.cow.modules.agent.mapper.AgentMessageMapper;
import com.portfolio.cow.modules.agent.mapper.AgentSessionMapper;
import com.portfolio.cow.modules.agent.service.AgentServiceClient;
import com.portfolio.cow.modules.agent.service.PendingActionService;
import com.portfolio.cow.security.LoginUser;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 智能体代理入口：会话/消息审计落库 + 写操作审批转发。
 * park/120s 超时拒绝在 cow-agent（Python）侧实现，由 cow-agent pytest 与
 * acceptance/cow_d2_agent_confirm.py 覆盖；本类只覆盖 admin 侧可测行为。
 */
@ExtendWith(MockitoExtension.class)
class AgentControllerTest {

    @Mock
    private AgentServiceClient agentServiceClient;
    @Mock
    private AgentSessionMapper sessionMapper;
    @Mock
    private AgentMessageMapper messageMapper;
    @Mock
    private PendingActionService pendingActionService;

    @InjectMocks
    private AgentController agentController;

    @BeforeEach
    void setUpSecurityContext() {
        LoginUser loginUser = new LoginUser();
        loginUser.setId(1L);
        loginUser.setUsername("admin");
        Authentication auth = mock(Authentication.class);
        // confirm/sessions 不读 principal，故 lenient 避免 UnnecessaryStubbing
        org.mockito.Mockito.lenient().when(auth.getPrincipal()).thenReturn(loginUser);
        SecurityContextHolder.getContext().setAuthentication(auth);
    }

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void chatCreatesSessionAndAuditsBothMessages() {
        // 新会话：sessionId 为空 → 预生成 UUID 落 agent_session；user/assistant 两条消息落 agent_message
        AgentChatRequest request = new AgentChatRequest();
        request.setMessage("COW-0001 现在什么状态？");
        when(agentServiceClient.chat(any())).thenReturn(Map.of(
                "reply", "COW-0001 疑似发情",
                "tokens", Map.of("input", 120, "output", 36)));

        agentController.chat(request);

        ArgumentCaptor<AgentSession> sessionCaptor = ArgumentCaptor.forClass(AgentSession.class);
        verify(sessionMapper).insert(sessionCaptor.capture());
        assertEquals("admin", sessionCaptor.getValue().getUsername());

        ArgumentCaptor<AgentMessage> messageCaptor = ArgumentCaptor.forClass(AgentMessage.class);
        verify(messageMapper, times(2)).insert(messageCaptor.capture());
        List<AgentMessage> messages = messageCaptor.getAllValues();
        assertEquals(AgentMessage.ROLE_USER, messages.get(0).getRole());
        assertEquals(AgentMessage.ROLE_ASSISTANT, messages.get(1).getRole());
        assertEquals(120, messages.get(1).getTokensInput());
        assertEquals(36, messages.get(1).getTokensOutput());
        // 两条消息挂在同一个预生成会话上
        assertEquals(messages.get(0).getSessionId(), messages.get(1).getSessionId());
        verify(sessionMapper).updateById(any(AgentSession.class));
    }

    @Test
    void chatReusesExistingSession() {
        AgentSession existing = new AgentSession();
        existing.setId(9L);
        existing.setSessionId("sess-0001");
        existing.setUsername("admin");
        when(sessionMapper.selectOne(any())).thenReturn(existing);
        when(agentServiceClient.chat(any())).thenReturn(Map.of("reply", "ok"));

        AgentChatRequest request = new AgentChatRequest();
        request.setSessionId("sess-0001");
        request.setMessage("继续");
        agentController.chat(request);

        verify(sessionMapper, never()).insert(any(AgentSession.class));
        ArgumentCaptor<Map<String, Object>> payloadCaptor = ArgumentCaptor.forClass(Map.class);
        verify(agentServiceClient).chat(payloadCaptor.capture());
        assertEquals("sess-0001", payloadCaptor.getValue().get("session_id"));
    }

    @Test
    void confirmForwardsApprovalResult() {
        // 前端弹窗点「批准」→ admin 原样转发 session_id + approved 给 cow-agent 放行 park 中的写操作
        when(agentServiceClient.confirm(any())).thenReturn(Map.of("status", "executed"));
        AgentConfirmRequest request = new AgentConfirmRequest();
        request.setSessionId("sess-0001");
        request.setApproved(true);

        agentController.confirm(request);

        ArgumentCaptor<Map<String, Object>> payloadCaptor = ArgumentCaptor.forClass(Map.class);
        verify(agentServiceClient).confirm(payloadCaptor.capture());
        assertEquals("sess-0001", payloadCaptor.getValue().get("session_id"));
        assertEquals(true, payloadCaptor.getValue().get("approved"));
    }

    @Test
    void confirmResolvesPendingActionBeforeForwarding() {
        // 审批下沉：先落 PENDING_ACTION 状态（批准人=发起人），再转发 cow-agent 放行
        PendingAction action = new PendingAction();
        action.setActionId("act-0001");
        when(pendingActionService.resolveForConfirm("sess-0001", true, "admin")).thenReturn(action);
        when(agentServiceClient.confirm(any())).thenReturn(Map.of("ok", true));

        AgentConfirmRequest request = new AgentConfirmRequest();
        request.setSessionId("sess-0001");
        request.setApproved(true);
        agentController.confirm(request);

        verify(pendingActionService).resolveForConfirm("sess-0001", true, "admin");
        verify(agentServiceClient).confirm(any());
        verify(pendingActionService, never()).voidIfApproved(any());
    }

    @Test
    void confirmForwardFailureVoidsApprovedAction() {
        // cow-agent 侧 park 已消失（超时）→ 转发失败时 APPROVED 凭证同步作废
        PendingAction action = new PendingAction();
        action.setActionId("act-0001");
        when(pendingActionService.resolveForConfirm("sess-0001", true, "admin")).thenReturn(action);
        when(agentServiceClient.confirm(any())).thenThrow(new BizException(502, "cow-agent 调用失败"));

        AgentConfirmRequest request = new AgentConfirmRequest();
        request.setSessionId("sess-0001");
        request.setApproved(true);
        assertThrows(BizException.class, () -> agentController.confirm(request));
        verify(pendingActionService).voidIfApproved("act-0001");
    }

    @Test
    void registerActionReturnsActionId() {
        // cow-agent park 时注册待审批动作（svc-agent 专用），返回 action_id 作为执行凭证
        PendingAction action = new PendingAction();
        action.setActionId("act-0001");
        action.setStatus(PendingAction.STATUS_PENDING);
        action.setExpireAt(java.time.LocalDateTime.now().plusSeconds(120));
        when(pendingActionService.register(any(), any(), any())).thenReturn(action);

        AgentActionRegisterRequest request = new AgentActionRegisterRequest();
        request.setSessionId("sess-0001");
        request.setTool("create_work_order");
        request.setParams(Map.of("type", "VET_CHECK", "description", "跛行复核"));

        Map<String, Object> data = agentController.registerAction(request).getData();
        assertEquals("act-0001", data.get("action_id"));
        assertEquals(PendingAction.STATUS_PENDING, data.get("status"));
        verify(pendingActionService).register("sess-0001", "create_work_order", request.getParams());
    }

    @Test
    void sessionsPassthroughForPendingConfirmPoll() {
        // 前端轮询会话列表拿待确认写操作（park 状态由 cow-agent 返回）
        Map<String, Object> agentResp = Map.of("sessions", List.of(
                Map.of("session_id", "sess-0001", "pending_confirm", Map.of("tool", "create_work_order"))));
        when(agentServiceClient.sessions()).thenReturn(agentResp);
        assertEquals(agentResp, agentController.sessions().getData());
    }
}
