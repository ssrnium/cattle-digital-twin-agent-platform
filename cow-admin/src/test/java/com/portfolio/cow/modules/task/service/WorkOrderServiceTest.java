package com.portfolio.cow.modules.task.service;

import com.portfolio.cow.common.BizException;
import com.portfolio.cow.modules.task.entity.WorkOrder;
import com.portfolio.cow.modules.task.mapper.WorkOrderMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.OptimisticLockingFailureException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class WorkOrderServiceTest {

    @Mock
    private WorkOrderMapper workOrderMapper;

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
        when(workOrderMapper.updateById(any())).thenReturn(0); // 并发已被改，更新 0 行
        assertThrows(OptimisticLockingFailureException.class,
                () -> workOrderService.assign(1L, 2L, 0));
    }

    @Test
    void assignTransitionsNewToDispatched() {
        WorkOrder o = orderAt(WorkOrder.STATE_NEW);
        when(workOrderMapper.selectById(1L)).thenReturn(o);
        when(workOrderMapper.updateById(any())).thenReturn(1);
        WorkOrder result = workOrderService.assign(1L, 2L, 0);
        assertEquals(WorkOrder.STATE_DISPATCHED, result.getState());
        assertEquals(2L, result.getAssigneeId());
    }

    @Test
    void missingVersionRejected() {
        when(workOrderMapper.selectById(1L)).thenReturn(orderAt(WorkOrder.STATE_NEW));
        assertThrows(BizException.class, () -> workOrderService.assign(1L, 2L, null));
    }
}
