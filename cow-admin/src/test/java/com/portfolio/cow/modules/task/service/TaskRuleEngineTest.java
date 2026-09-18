package com.portfolio.cow.modules.task.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import com.portfolio.cow.modules.event.service.OutboxPublisher;
import com.portfolio.cow.modules.task.entity.WorkOrder;
import com.portfolio.cow.modules.task.mapper.WorkOrderMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * TaskRuleEngine 单元测试：验证告警事件 → 工单的规则映射、
 * 24h 告警收敛去重，以及工单生成后的 Outbox 通知（含 MQTT 关闭降级）。
 */
@ExtendWith(MockitoExtension.class)
class TaskRuleEngineTest {

    @Mock
    private WorkOrderMapper workOrderMapper;
    @Mock
    private OutboxPublisher outboxPublisher;

    @InjectMocks
    private TaskRuleEngine taskRuleEngine;

    private UnifiedEvent cowEvent(String type, String cowId) {
        UnifiedEvent e = new UnifiedEvent();
        e.setEventId("EVT-1");
        e.setFarmId("FARM-1");
        e.setCowId(cowId);
        e.setEventType(type);
        e.setConfidence(0.9);
        e.setEventTime(LocalDateTime.now());
        return e;
    }

    @Test
    void mountingCreatesBreedingReviewOrder() {
        // MOUNTING（疑似发情）→ 生成 BREEDING_REVIEW 配种复查工单，并下发通知
        when(workOrderMapper.selectCount(any(LambdaQueryWrapper.class))).thenReturn(0L);

        taskRuleEngine.evaluate(cowEvent(UnifiedEvent.TYPE_MOUNTING, "COW-0001"));

        ArgumentCaptor<WorkOrder> captor = ArgumentCaptor.forClass(WorkOrder.class);
        verify(workOrderMapper).insert(captor.capture());
        WorkOrder order = captor.getValue();
        assertEquals(WorkOrder.TYPE_BREEDING_REVIEW, order.getType());
        assertEquals("COW-0001", order.getCowId());
        assertEquals(WorkOrder.STATE_NEW, order.getState());
        assertEquals("EVT-1", order.getSourceEventId());
        verify(outboxPublisher).publishOrderCreated(any(WorkOrder.class), eq("FARM-1"));
    }

    @Test
    void lamenessCreatesVetCheckOrder() {
        // LAMENESS（跛行风险）→ 生成 VET_CHECK 兽医检查工单
        when(workOrderMapper.selectCount(any(LambdaQueryWrapper.class))).thenReturn(0L);

        taskRuleEngine.evaluate(cowEvent(UnifiedEvent.TYPE_LAMENESS, "COW-0002"));

        ArgumentCaptor<WorkOrder> captor = ArgumentCaptor.forClass(WorkOrder.class);
        verify(workOrderMapper).insert(captor.capture());
        assertEquals(WorkOrder.TYPE_VET_CHECK, captor.getValue().getType());
        assertEquals("COW-0002", captor.getValue().getCowId());
        verify(outboxPublisher).publishOrderCreated(any(WorkOrder.class), eq("FARM-1"));
    }

    @Test
    void duplicateOpenOrderWithin24hIsSkipped() {
        // 同牛同类型 24h 内已有未关闭工单 → 告警收敛：只查询不新建、不通知
        when(workOrderMapper.selectCount(any(LambdaQueryWrapper.class))).thenReturn(1L);

        taskRuleEngine.evaluate(cowEvent(UnifiedEvent.TYPE_MOUNTING, "COW-0001"));

        verify(workOrderMapper, never()).insert(any(WorkOrder.class));
        verify(outboxPublisher, never()).publishOrderCreated(any(WorkOrder.class), any());
    }

    @Test
    void deviceOfflineCreatesHighPriorityRepairOrder() {
        // DEVICE_OFFLINE → 生成 DEVICE_REPAIR 设备维修工单，优先级 HIGH
        UnifiedEvent e = cowEvent(UnifiedEvent.TYPE_DEVICE_OFFLINE, null);
        e.setDeviceId("DEV-01");
        when(workOrderMapper.selectCount(any(LambdaQueryWrapper.class))).thenReturn(0L);

        taskRuleEngine.evaluate(e);

        ArgumentCaptor<WorkOrder> captor = ArgumentCaptor.forClass(WorkOrder.class);
        verify(workOrderMapper).insert(captor.capture());
        WorkOrder order = captor.getValue();
        assertEquals(WorkOrder.TYPE_DEVICE_REPAIR, order.getType());
        assertEquals("HIGH", order.getPriority());
        assertEquals("DEV-01", order.getDeviceId());
        verify(outboxPublisher).publishOrderCreated(any(WorkOrder.class), eq("FARM-1"));
    }

    @Test
    void duplicateDeviceRepairOrderIsSkipped() {
        // 同设备已有未关闭维修单 → 不重复生成
        UnifiedEvent e = cowEvent(UnifiedEvent.TYPE_DEVICE_OFFLINE, null);
        e.setDeviceId("DEV-01");
        when(workOrderMapper.selectCount(any(LambdaQueryWrapper.class))).thenReturn(2L);

        taskRuleEngine.evaluate(e);

        verify(workOrderMapper, never()).insert(any(WorkOrder.class));
        verify(outboxPublisher, never()).publishOrderCreated(any(WorkOrder.class), any());
    }

    @Test
    void outboxDegradesToLogWhenMqttDisabled() {
        // MQTT 关闭（mqttOutboundChannel 不存在）时 OutboxPublisher 降级为记日志，不抛异常
        OutboxPublisher publisher = new OutboxPublisher(null);
        WorkOrder order = new WorkOrder();
        order.setOrderNo("WO2026091800000000001");
        order.setType(WorkOrder.TYPE_BREEDING_REVIEW);
        order.setCowId("COW-0001");

        assertDoesNotThrow(() -> publisher.publishOrderCreated(order, "FARM-1"));
    }
}
