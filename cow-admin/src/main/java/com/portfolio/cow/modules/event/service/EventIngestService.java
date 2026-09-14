package com.portfolio.cow.modules.event.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.modules.event.dto.EventIngestRequest;
import com.portfolio.cow.modules.event.dto.IngestResponse;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import com.portfolio.cow.modules.event.mapper.UnifiedEventMapper;
import com.portfolio.cow.modules.task.service.TaskRuleEngine;
import com.portfolio.cow.modules.twin.TwinUpdater;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/**
 * 事件统一入口。处理顺序固定：
 * ① schema_version 校验
 * ② event_id 幂等去重（数据库唯一约束冲突 → duplicated=true，绝不重复落库、绝不重复告警）
 * ③ 落库
 * ④ TwinUpdater（孪生状态 + 时间线） + TaskRuleEngine（告警工单）
 *
 * 注意：不在本方法上加 @Transactional —— PostgreSQL 中唯一约束冲突会使整个事务进入
 * aborted 状态，catch 后无法继续写库。落库/孪生/工单各自独立提交，幂等性由
 * uk_unified_event_event_id 唯一约束在并发下兜底。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EventIngestService {

    /** 当前支持的契约版本 */
    private static final Set<String> SUPPORTED_SCHEMA_VERSIONS = Set.of("1.0");

    private final UnifiedEventMapper eventMapper;
    private final TwinUpdater twinUpdater;
    private final TaskRuleEngine taskRuleEngine;

    private final ObjectMapper mqttObjectMapper = new ObjectMapper().registerModule(new JavaTimeModule());

    public IngestResponse ingest(EventIngestRequest req) {
        // ① schema_version 校验
        if (!SUPPORTED_SCHEMA_VERSIONS.contains(req.getSchemaVersion())) {
            throw new BizException(400, "不支持的 schema_version: " + req.getSchemaVersion()
                    + "，支持: " + SUPPORTED_SCHEMA_VERSIONS);
        }

        UnifiedEvent event = toEntity(req);

        // ② + ③ 幂等去重 + 落库：依赖 event_id 唯一约束，重复插入直接判定 duplicated
        try {
            eventMapper.insert(event);
        } catch (DuplicateKeyException e) {
            log.info("duplicated event_id={}, ignored (no re-insert, no re-alert)", req.getEventId());
            return IngestResponse.duplicated(req.getEventId());
        }

        // ④ 下游处理：孪生更新 + 工单规则引擎
        twinUpdater.apply(event);
        taskRuleEngine.evaluate(event);
        return IngestResponse.accepted(req.getEventId());
    }

    /** MQTT 入站：payload 支持单条对象或数组，逐条处理且互不影响 */
    public List<IngestResponse> ingestFromMqtt(String json) {
        List<IngestResponse> results = new ArrayList<>();
        try {
            JsonNode node = mqttObjectMapper.readTree(json);
            if (node.isArray()) {
                for (JsonNode item : node) {
                    results.add(safeIngest(item));
                }
            } else {
                results.add(safeIngest(node));
            }
        } catch (Exception e) {
            log.error("bad mqtt event payload: {}", e.getMessage());
        }
        return results;
    }

    private IngestResponse safeIngest(JsonNode node) {
        String eventId = node.path("event_id").asText("unknown");
        try {
            EventIngestRequest req = mqttObjectMapper.treeToValue(node, EventIngestRequest.class);
            return ingest(req);
        } catch (Exception e) {
            log.warn("ingest mqtt event failed, event_id={}, reason={}", eventId, e.getMessage());
            return new IngestResponse(eventId, false, "rejected: " + e.getMessage());
        }
    }

    private UnifiedEvent toEntity(EventIngestRequest req) {
        UnifiedEvent e = new UnifiedEvent();
        e.setSchemaVersion(req.getSchemaVersion());
        e.setTenantId(StringUtils.hasText(req.getTenantId()) ? req.getTenantId() : "default");
        e.setFarmId(req.getFarmId());
        e.setEventId(req.getEventId());
        e.setCowId(req.getCowId());
        e.setDeviceId(req.getDeviceId());
        e.setEventType(req.getEventType());
        e.setEventTime(req.getEventTime());
        e.setIngestTime(LocalDateTime.now());
        e.setQuality(req.getQuality());
        e.setConfidence(req.getConfidence());
        e.setModelVersion(req.getModelVersion());
        e.setEvidenceRef(req.getEvidenceRef());
        e.setRaw(req.getRaw());
        return e;
    }
}
