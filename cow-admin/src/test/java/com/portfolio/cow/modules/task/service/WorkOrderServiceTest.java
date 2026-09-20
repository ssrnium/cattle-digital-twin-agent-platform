package com.portfolio.cow.modules.task.service;

import com.portfolio.cow.common.BizException;
import com.portfolio.cow.modules.agent.service.PendingActionService;
import com.portfolio.cow.modules.task.entity.WorkOrder;
import com.portfolio.cow.modules.task.mapper.WorkOrderMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.OptimisticLockingFailureException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class WorkOrderServiceTest {

    @Mock
    private WorkOrderMapper workOrderMapper;
    @Mock
    private PendingActionService pendingActionService;

    @InjectMocks
    private WorkOrderService workOrderService;

    private WorkOrder orderAt(String state) {
        WorkOrder o = new WorkOrder();
        o.setId(1L);
        o.setState(state);
        o.setVersion(0);
        return o;
    }

    @Test
    void illegalTransitionThrowsBizException() {
        // NEW 不能直接 → PROCESSING
        when(workOrderMapper.selectById(1L)).thenReturn(orderAt(WorkOrder.STATE_NEW));
        assertThrows(BizException.class, () -> workOrderService.start(1L, 0));
    }

    @Test
    void closedOrderRejectsAnyTransition() {
        when(workOrderMapper.selectById(1L)).thenReturn(orderAt(WorkOrder.STATE_CLOSED));
        assertThrows(BizException.class, () -> workOrderService.assign(1L, 2L, 0));
    }

    @Test
    void versionConflictThrowsOptimisticLock() {
        WorkOrder o = orderAt(WorkOrder.STATE_NEW);
        when(workOrderMapper.selectById(1L)).thenReturn(o);
        when(workOrderMapper.updateById(any(WorkOrder.class))).thenReturn(0); // 并发已被改，更新 0 行
        assertThrows(OptimisticLockingFailureException.class,
                () -> workOrderService.assign(1L, 2L, 0));
    }

    @Test
    void assignTransitionsNewToDispatched() {
        WorkOrder o = orderAt(WorkOrder.STATE_NEW);
        when(workOrderMapper.selectById(1L)).thenReturn(o);
        when(workOrderMapper.updateById(any(WorkOrder.class))).thenReturn(1);
        WorkOrder result = workOrderService.assign(1L, 2L, 0);
        assertEquals(WorkOrder.STATE_DISPATCHED, result.getState());
        assertEquals(2L, result.getAssigneeId());
    }

    @Test
    void missingVersionRejected() {
        when(workOrderMapper.selectById(1L)).thenReturn(orderAt(WorkOrder.STATE_NEW));
        assertThrows(BizException.class, () -> workOrderService.assign(1L, 2L, null));
    }

    // ============ 智能体建单强制审批（PENDING_ACTION 下沉） ============

    private WorkOrder newOrder() {
        WorkOrder o = new WorkOrder();
        o.setType(WorkOrder.TYPE_VET_CHECK);
        o.setCowId("COW-0042");
        o.setPriority("NORMAL");
        o.setDescription("跛行复核");
        return o;
    }

    @Test
    void createByAgentWithoutActionIdForbidden() {
        // svc-agent 无 X-Action-Id 直连 → 403，不落库
        BizException e = assertThrows(BizException.class,
                () -> workOrderService.createByAgent(newOrder(), null));
        assertEquals(403, e.getCode());
        verify(workOrderMapper, never()).insert(any(WorkOrder.class));
    }

    @Test
    void createByAgentApprovedCreatesAndMarksExecuted() {
        // 正常路径：凭证有效 → 建单 + 同事务置 EXECUTED
        when(pendingActionService.markExecuted(anyString(), isNull())).thenReturn(1);

        WorkOrder created = workOrderService.createByAgent(newOrder(), "act-0001");

        verify(pendingActionService).validateExecutable(eq("act-0001"), anyString());
        verify(workOrderMapper).insert(any(WorkOrder.class));
        verify(pendingActionService).markExecuted("act-0001", null);
        assertNotNull(created.getOrderNo());
        assertEquals(WorkOrder.STATE_NEW, created.getState());
    }

    @Test
    void createByAgentRejectedActionForbidden() {
        // 凭证未获批（REJECTED/PENDING）→ validateExecutable 抛 403，建单被拦
        doThrow(new BizException(403, "写操作未获批准，当前状态: REJECTED"))
                .when(pendingActionService).validateExecutable(anyString(), anyString());

        BizException e = assertThrows(BizException.class,
                () -> workOrderService.createByAgent(newOrder(), "act-0001"));
        assertEquals(403, e.getCode());
        verify(workOrderMapper, never()).insert(any(WorkOrder.class));
    }

    @Test
    void createByAgentDigestMismatchForbidden() {
        // 批准后参数被改 → 摘要不符 403
        doThrow(new BizException(403, "参数与审批摘要不一致，疑似被篡改"))
                .when(pendingActionService).validateExecutable(anyString(), anyString());

        BizException e = assertThrows(BizException.class,
                () -> workOrderService.createByAgent(newOrder(), "act-0001"));
        assertEquals(403, e.getCode());
        verify(workOrderMapper, never()).insert(any(WorkOrder.class));
    }

    @Test
    void createByAgentDuplicateExecutionConflict() {
        // 并发重复执行：APPROVED→EXECUTED 条件更新 0 行 → 409（事务回滚，只一张单）
        when(pendingActionService.markExecuted(anyString(), isNull())).thenReturn(0);

        BizException e = assertThrows(BizException.class,
                () -> workOrderService.createByAgent(newOrder(), "act-0001"));
        assertEquals(409, e.getCode());
    }
}
