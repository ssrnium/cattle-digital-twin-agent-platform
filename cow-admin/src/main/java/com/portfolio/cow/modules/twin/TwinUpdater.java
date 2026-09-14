package com.portfolio.cow.modules.twin;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.modules.cow.entity.CowProfile;
import com.portfolio.cow.modules.cow.entity.CowTimeline;
import com.portfolio.cow.modules.cow.entity.TwinState;
import com.portfolio.cow.modules.cow.mapper.CowProfileMapper;
import com.portfolio.cow.modules.cow.mapper.CowTimelineMapper;
import com.portfolio.cow.modules.cow.mapper.TwinStateMapper;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 数字孪生状态更新器。
 * 规则：
 * - MOUNTING 高置信（>=0.8） → state.estrus_status = SUSPECTED_HEAT
 * - LAMENESS                 → state.health_status = LAMENESS_RISK
 * - DEVICE_*                 → 不改变牛只状态
 * - 迟到事件（event_time 早于当前状态的事件时间）只追加 timeline，不回退当前状态
 * - 每个牛只相关事件都写 CowTimeline
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class TwinUpdater {

    private static final double MOUNTING_HIGH_CONFIDENCE = 0.8;

    private final TwinStateMapper twinStateMapper;
    private final CowTimelineMapper cowTimelineMapper;
    private final CowProfileMapper cowProfileMapper;

    public void apply(UnifiedEvent event) {
        if (!StringUtils.hasText(event.getCowId())) {
            return; // 设备类事件与牛只无关
        }

        // 每个牛只相关事件都追加时间线（AI 推断 → INFERRED）
        appendTimeline(event);

        if (UnifiedEvent.TYPE_SYNC_STATE.equals(event.getEventType())) {
            return; // 同步状态事件不改孪生
        }

        boolean mounting = UnifiedEvent.TYPE_MOUNTING.equals(event.getEventType())
                && event.getConfidence() != null
                && event.getConfidence() >= MOUNTING_HIGH_CONFIDENCE;
        boolean lameness = UnifiedEvent.TYPE_LAMENESS.equals(event.getEventType());
        if (!mounting && !lameness) {
            return;
        }

        // 乐观锁更新，冲突时有限重试（孪生写入并发低，3 次足够）
        for (int attempt = 0; attempt < 3; attempt++) {
            TwinState current = twinStateMapper.selectById(event.getCowId());
            if (current == null) {
                current = initState(event);
                try {
                    twinStateMapper.insert(current);
                } catch (Exception e) {
                    continue; // 并发插入同一 cow_id，下一轮重试读已有记录
                }
                return;
            }

            // 迟到事件：只追加 timeline（上面已写），不回退当前状态
            if (current.getEventTime() != null && event.getEventTime() != null
                    && event.getEventTime().isBefore(current.getEventTime())) {
                log.info("late event {} for cow {}, timeline only, state not rolled back",
                        event.getEventId(), event.getCowId());
                return;
            }

            Map<String, Object> state = current.getState() == null
                    ? new HashMap<>() : new HashMap<>(current.getState());
            if (mounting) {
                state.put("estrus_status", "SUSPECTED_HEAT");
            }
            if (lameness) {
                state.put("health_status", "LAMENESS_RISK");
            }
            current.setState(state);
            current.setStateNature("INFERRED");
            current.setSourceEventId(event.getEventId());
            current.setEventTime(event.getEventTime());
            current.setUpdatedAt(LocalDateTime.now());
            if (twinStateMapper.updateById(current) > 0) {
                return; // @Version 校验通过
            }
            log.warn("twin_state optimistic lock conflict on cow {}, retry {}/3",
                    event.getCowId(), attempt + 1);
        }
        log.error("twin_state update failed after retries, cow={}", event.getCowId());
    }

    private TwinState initState(UnifiedEvent event) {
        TwinState ts = new TwinState();
        ts.setCowId(event.getCowId());
        Map<String, Object> state = new HashMap<>();
        state.put("posture", "UNKNOWN");
        state.put("health_status", UnifiedEvent.TYPE_LAMENESS.equals(event.getEventType())
                ? "LAMENESS_RISK" : "NORMAL");
        state.put("estrus_status",
                (UnifiedEvent.TYPE_MOUNTING.equals(event.getEventType())
                        && event.getConfidence() != null
                        && event.getConfidence() >= MOUNTING_HIGH_CONFIDENCE)
                        ? "SUSPECTED_HEAT" : "NORMAL");
        CowProfile cow = cowProfileMapper.selectOne(new LambdaQueryWrapper<CowProfile>()
                .eq(CowProfile::getCowId, event.getCowId()));
        state.put("zone", cow != null ? cow.getZone() : "UNKNOWN");
        ts.setState(state);
        ts.setStateNature("INFERRED");
        ts.setSourceEventId(event.getEventId());
        ts.setEventTime(event.getEventTime());
        ts.setUpdatedAt(LocalDateTime.now());
        return ts;
    }

    private void appendTimeline(UnifiedEvent event) {
        CowTimeline tl = new CowTimeline();
        tl.setCowId(event.getCowId());
        tl.setEventId(event.getEventId());
        tl.setEventType(event.getEventType());
        tl.setTitle(titleOf(event));
        Map<String, Object> detail = new HashMap<>();
        detail.put("confidence", event.getConfidence());
        detail.put("quality", event.getQuality());
        detail.put("model_version", event.getModelVersion());
        detail.put("evidence_ref", event.getEvidenceRef());
        detail.put("device_id", event.getDeviceId());
        tl.setDetail(detail);
        tl.setStateNature("INFERRED");
        tl.setEventTime(event.getEventTime());
        tl.setCreateTime(LocalDateTime.now());
        cowTimelineMapper.insert(tl);
    }

    private String titleOf(UnifiedEvent event) {
        return switch (event.getEventType()) {
            case UnifiedEvent.TYPE_MOUNTING -> "检测到爬跨行为（疑似发情）";
            case UnifiedEvent.TYPE_LAMENESS -> "检测到跛行风险";
            case UnifiedEvent.TYPE_SYNC_STATE -> "边缘状态同步";
            default -> "事件 " + event.getEventType();
        };
    }
}
