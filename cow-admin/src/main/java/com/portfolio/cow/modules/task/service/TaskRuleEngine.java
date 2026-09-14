package com.portfolio.cow.modules.task.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import com.portfolio.cow.modules.event.service.OutboxPublisher;
import com.portfolio.cow.modules.task.entity.WorkOrder;
import com.portfolio.cow.modules.task.mapper.WorkOrderMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 告警工单规则引擎：
 * - MOUNTING      → BREEDING_REVIEW（配种复查），同一头牛 24h 内已有未关闭同类型工单则不重复生成
 * - LAMENESS      → VET_CHECK（兽医检查），同牛 24h 去重
 * - DEVICE_OFFLINE→ DEVICE_REPAIR（设备维修），同设备未关闭去重
 * 工单生成后通过 OutboxPublisher 下发 MQTT 通知。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class TaskRuleEngine {

    private static final List<String> OPEN_STATES =
            List.of(WorkOrder.STATE_NEW, WorkOrder.STATE_DISPATCHED,
                    WorkOrder.STATE_PROCESSING, WorkOrder.STATE_PENDING_REVIEW);

    private final WorkOrderMapper workOrderMapper;
    private final OutboxPublisher outboxPublisher;

    public void evaluate(UnifiedEvent event) {
        switch (event.getEventType()) {
            case UnifiedEvent.TYPE_MOUNTING -> createCowOrder(event, WorkOrder.TYPE_BREEDING_REVIEW,
                    "AI 检测到爬跨行为（置信度 " + conf(event) + "），请安排配种复查");
            case UnifiedEvent.TYPE_LAMENESS -> createCowOrder(event, WorkOrder.TYPE_VET_CHECK,
                    "AI 检测到跛行风险（置信度 " + conf(event) + "），请安排兽医检查");
            case UnifiedEvent.TYPE_DEVICE_OFFLINE -> createDeviceOrder(event);
            default -> {
                // DEVICE_RECOVERED / SYNC_STATE 不触发工单
            }
        }
    }

    private void createCowOrder(UnifiedEvent event, String type, String description) {
        if (event.getCowId() == null) {
            return;
        }
        // 同牛 24h 内已有未关闭同类型工单 → 不重复生成（告警收敛）
        Long open = workOrderMapper.selectCount(new LambdaQueryWrapper<WorkOrder>()
                .eq(WorkOrder::getCowId, event.getCowId())
                .eq(WorkOrder::getType, type)
                .in(WorkOrder::getState, OPEN_STATES)
                .ge(WorkOrder::getCreateTime, LocalDateTime.now().minusHours(24)));
        if (open > 0) {
            log.info("open {} order already exists for cow {} within 24h, skip", type, event.getCowId());
            return;
        }
        WorkOrder order = baseOrder(event, type, description);
        order.setCowId(event.getCowId());
        workOrderMapper.insert(order);
        outboxPublisher.publishOrderCreated(order, event.getFarmId());
    }

    private void createDeviceOrder(UnifiedEvent event) {
        if (event.getDeviceId() == null) {
            return;
        }
        Long open = workOrderMapper.selectCount(new LambdaQueryWrapper<WorkOrder>()
                .eq(WorkOrder::getDeviceId, event.getDeviceId())
                .eq(WorkOrder::getType, WorkOrder.TYPE_DEVICE_REPAIR)
                .in(WorkOrder::getState, OPEN_STATES));
        if (open > 0) {
            log.info("open DEVICE_REPAIR order already exists for device {}, skip", event.getDeviceId());
            return;
        }
        WorkOrder order = baseOrder(event, WorkOrder.TYPE_DEVICE_REPAIR,
                "设备 " + event.getDeviceId() + " 离线，请现场检查网络与供电");
        order.setDeviceId(event.getDeviceId());
        order.setPriority("HIGH");
        workOrderMapper.insert(order);
        outboxPublisher.publishOrderCreated(order, event.getFarmId());
    }

    private WorkOrder baseOrder(UnifiedEvent event, String type, String description) {
        WorkOrder order = new WorkOrder();
        order.setOrderNo(nextOrderNo());
        order.setType(type);
        order.setSourceEventId(event.getEventId());
        order.setState(WorkOrder.STATE_NEW);
        order.setPriority("NORMAL");
        order.setDescription(description);
        order.setCreateTime(LocalDateTime.now());
        order.setUpdateTime(LocalDateTime.now());
        return order;
    }

    private String conf(UnifiedEvent event) {
        return event.getConfidence() == null ? "unknown"
                : String.format("%.2f", event.getConfidence());
    }

    private String nextOrderNo() {
        return "WO" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss"))
                + String.format("%05d", ThreadLocalRandom.current().nextInt(100000));
    }
}
