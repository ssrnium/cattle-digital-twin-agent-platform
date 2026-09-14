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
        when(eventMapper.insert(any())).thenThrow(new DuplicateKeyException("uk_unified_event_event_id"));
        IngestResponse resp = eventIngestService.ingest(req());
        assertTrue(resp.isDuplicated());
        verify(twinUpdater, never()).apply(any());
        verify(taskRuleEngine, never()).evaluate(any());
    }

    @Test
    void freshEventFlowsToTwinAndRuleEngine() {
        when(eventMapper.insert(any())).thenReturn(1);
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
}
