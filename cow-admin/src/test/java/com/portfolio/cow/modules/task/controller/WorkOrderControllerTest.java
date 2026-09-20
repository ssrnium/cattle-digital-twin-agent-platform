package com.portfolio.cow.modules.task.controller;

import com.portfolio.cow.modules.task.entity.WorkOrder;
import com.portfolio.cow.modules.task.mapper.WorkOrderMapper;
import com.portfolio.cow.modules.task.service.WorkOrderService;
import com.portfolio.cow.security.LoginUser;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 建单强制点分流：SERVICE 角色（svc-agent）必须走 PENDING_ACTION 审批凭证，
 * 人工角色（admin 等）不受 X-Action-Id 约束。
 */
@ExtendWith(MockitoExtension.class)
class WorkOrderControllerTest {

    @Mock
    private WorkOrderMapper workOrderMapper;
    @Mock
    private WorkOrderService workOrderService;

    @InjectMocks
    private WorkOrderController workOrderController;

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    private void loginAs(String username, List<String> roles) {
        LoginUser loginUser = new LoginUser();
        loginUser.setId(1L);
        loginUser.setUsername(username);
        loginUser.setRoles(roles);
        Authentication auth = mock(Authentication.class);
        lenient().when(auth.getPrincipal()).thenReturn(loginUser);
        SecurityContextHolder.getContext().setAuthentication(auth);
    }

    private WorkOrder newOrder() {
        WorkOrder o = new WorkOrder();
        o.setType(WorkOrder.TYPE_VET_CHECK);
        o.setDescription("跛行复核");
        return o;
    }

    @Test
    void serviceAccountMustGoThroughActionValidation() {
        // svc-agent 即使不带 X-Action-Id，也被分流到 createByAgent（凭证校验在 service 层强制）
        loginAs("svc-agent", List.of("SERVICE"));
        workOrderController.create(newOrder(), null);
        verify(workOrderService).createByAgent(any(WorkOrder.class), isNull());
        verify(workOrderService, never()).create(any(WorkOrder.class));
    }

    @Test
    void humanAdminCreatesWithoutActionId() {
        // 人工角色建单不受审批凭证约束
        loginAs("admin", List.of("ADMIN"));
        workOrderController.create(newOrder(), null);
        verify(workOrderService).create(any(WorkOrder.class));
        verify(workOrderService, never()).createByAgent(any(WorkOrder.class), any());
    }
}
