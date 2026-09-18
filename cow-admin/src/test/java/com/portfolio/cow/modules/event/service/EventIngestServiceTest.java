package com.portfolio.cow.modules.event.service;

import com.portfolio.cow.common.BizException;
import com.portfolio.cow.modules.event.dto.EventIngestRequest;
import com.portfolio.cow.modules.event.dto.IngestResponse;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import com.portfolio.cow.modules.event.mapper.UnifiedEventMapper;
import com.portfolio.cow.modules.task.service.TaskRuleEngine;
import com.portfolio.cow.modules.twin.TwinUpdater;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DuplicateKeyException;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class EventIngestServiceTest {

    @Mock
    private UnifiedEventMapper eventMapper;
    @Mock
    private TwinUpdater twinUpdater;
    @Mock
    private TaskRuleEngine taskRuleEngine;

    @InjectMocks
    private EventIngestService eventIngestService;

    private EventIngestRequest req() {
        EventIngestRequest r = new EventIngestRequest();
        r.setSchemaVersion("1.0");
        r.setEventId("evt-test-0001");
        r.setEventType(UnifiedEvent.TYPE_MOUNTING);
        r.setCowId("COW-0001");
        r.setDeviceId("edge-node-01");
        r.setEventTime(LocalDateTime.now());
        r.setConfidence(0.93);
        return r;
    }

    @Test
    void duplicateEventIdIsIdempotent_noTwinNoOrder() {
        // 重复 event_id：唯一约束冲突 → duplicated=true，绝不触发孪生更新与工单（重复告警 0）
        when(eventMapper.insert(any(UnifiedEvent.class))).thenThrow(new DuplicateKeyException("uk_unified_event_event_id"));
        IngestResponse resp = eventIngestService.ingest(req());
        assertTrue(resp.isDuplicated());
        verify(twinUpdater, never()).apply(any());
        verify(taskRuleEngine, never()).evaluate(any());
    }

    @Test
    void freshEventFlowsToTwinAndRuleEngine() {
        when(eventMapper.insert(any(UnifiedEvent.class))).thenReturn(1);
        IngestResponse resp = eventIngestService.ingest(req());
        assertFalse(resp.isDuplicated());
        verify(twinUpdater).apply(any());
        verify(taskRuleEngine).evaluate(any());
    }

    @Test
    void unsupportedSchemaVersionRejected() {
        EventIngestRequest r = req();
        r.setSchemaVersion("9.9");
        assertThrows(BizException.class, () -> eventIngestService.ingest(r));
    }

    @Test
    void mqttMalformedPayloadReturnsEmpty() {
        // 坏 JSON 不抛出、不产生任何结果，broker 侧不让一条脏消息打挂消费循环
        assertTrue(eventIngestService.ingestFromMqtt("{not a json").isEmpty());
    }

    @Test
    void mqttArrayBadItemRejectedGoodItemAccepted() {
        // 批量数组逐条处理互不影响：坏契约版本被拒绝，正常事件照常落库进孪生/工单
        when(eventMapper.insert(any(UnifiedEvent.class))).thenReturn(1);
        String json = "["
                + "{\"schema_version\":\"1.0\",\"event_id\":\"evt-mqtt-good\",\"event_type\":\"MOUNTING\","
                + "\"cow_id\":\"COW-0001\",\"device_id\":\"edge-node-01\",\"event_time\":\"2026-09-18 10:00:00\",\"confidence\":0.9},"
                + "{\"schema_version\":\"9.9\",\"event_id\":\"evt-mqtt-bad\",\"event_type\":\"MOUNTING\","
                + "\"cow_id\":\"COW-0002\",\"device_id\":\"edge-node-01\",\"event_time\":\"2026-09-18 10:00:00\",\"confidence\":0.9}"
                + "]";
        List<IngestResponse> results = eventIngestService.ingestFromMqtt(json);
        assertEquals(2, results.size());
        assertEquals("accepted", results.get(0).getMessage());
        assertTrue(results.get(1).getMessage().startsWith("rejected:"), results.get(1).getMessage());
        verify(twinUpdater).apply(any());
    }

    @Test
    void deviceEventWithoutCowIdAccepted() {
        // 设备类事件（DEVICE_* / SYNC_STATE）允许无 cow_id：照常幂等落库，
        // TwinUpdater 内部对无 cow_id 事件直接跳过牛只状态更新（TwinUpdaterTest 已覆盖）
        when(eventMapper.insert(any(UnifiedEvent.class))).thenReturn(1);
        EventIngestRequest r = req();
        r.setCowId(null);
        r.setEventType(UnifiedEvent.TYPE_SYNC_STATE);
        IngestResponse resp = eventIngestService.ingest(r);
        assertFalse(resp.isDuplicated());
        assertEquals("accepted", resp.getMessage());
        verify(eventMapper).insert(any(UnifiedEvent.class));
    }
}
