package com.portfolio.cow.modules.event.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.cow.modules.task.entity.WorkOrder;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.integration.mqtt.support.MqttHeaders;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.util.HashMap;
import java.util.Map;

/**
 * 出站通知（工单生成 → MQTT 下发，供边缘/大屏订阅）。
 * mqtt.enabled=false 时通道不存在，自动降级为仅记日志。
 */
@Slf4j
@Component
public class OutboxPublisher {

    private final MessageChannel mqttOutboundChannel;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public OutboxPublisher(@Autowired(required = false)
                           @Qualifier("mqttOutboundChannel") MessageChannel mqttOutboundChannel) {
        this.mqttOutboundChannel = mqttOutboundChannel;
    }

    public void publishOrderCreated(WorkOrder order, String farmId) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("notify_type", "WORK_ORDER_CREATED");
        payload.put("order_no", order.getOrderNo());
        payload.put("type", order.getType());
        payload.put("cow_id", order.getCowId());
        payload.put("device_id", order.getDeviceId());
        payload.put("priority", order.getPriority());
        payload.put("source_event_id", order.getSourceEventId());
        String topic = "farm/" + (StringUtils.hasText(farmId) ? farmId : "default") + "/task";

        if (mqttOutboundChannel == null) {
            log.info("[outbox-log-only] topic={} payload={}", topic, payload);
            return;
        }
        try {
            mqttOutboundChannel.send(MessageBuilder
                    .withPayload(objectMapper.writeValueAsString(payload))
                    .setHeader(MqttHeaders.TOPIC, topic)
                    .build());
        } catch (Exception e) {
            log.warn("mqtt outbox publish failed: {}", e.getMessage());
        }
    }
}
