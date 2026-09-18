package com.portfolio.cow.modules.twin;

import com.portfolio.cow.modules.cow.entity.CowTimeline;
import com.portfolio.cow.modules.cow.entity.TwinState;
import com.portfolio.cow.modules.cow.mapper.CowProfileMapper;
import com.portfolio.cow.modules.cow.mapper.CowTimelineMapper;
import com.portfolio.cow.modules.cow.mapper.TwinStateMapper;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * TwinUpdater 单元测试：验证事件 → 数字孪生状态的映射规则、
 * 迟到事件不回退、以及乐观锁冲突重试。
 */
@ExtendWith(MockitoExtension.class)
class TwinUpdaterTest {

    @Mock
    private TwinStateMapper twinStateMapper;
    @Mock
    private CowTimelineMapper cowTimelineMapper;
    @Mock
    private CowProfileMapper cowProfileMapper;

    @InjectMocks
    private TwinUpdater twinUpdater;

    private UnifiedEvent event(String type, Double confidence, LocalDateTime eventTime) {
        UnifiedEvent e = new UnifiedEvent();
        e.setEventId("EVT-1");
        e.setCowId("COW-0001");
        e.setFarmId("FARM-1");
        e.setEventType(type);
        e.setConfidence(confidence);
        e.setEventTime(eventTime);
        return e;
    }

    private TwinState existingState(LocalDateTime eventTime) {
        TwinState ts = new TwinState();
        ts.setCowId("COW-0001");
        Map<String, Object> state = new HashMap<>();
        state.put("estrus_status", "NORMAL");
        state.put("health_status", "NORMAL");
        ts.setState(state);
        ts.setStateNature("INFERRED");
        ts.setEventTime(eventTime);
        ts.setVersion(0);
        return ts;
    }

    @Test
    void mountingHighConfidenceSetsSuspectedHeat() {
        // MOUNTING 且置信度 >= 0.8 → estrus_status 置 SUSPECTED_HEAT，并写牛只时间线
        LocalDateTime now = LocalDateTime.now();
        when(twinStateMapper.selectById("COW-0001")).thenReturn(existingState(now.minusMinutes(5)));
        when(twinStateMapper.updateById(any(TwinState.class))).thenReturn(1);

        twinUpdater.apply(event(UnifiedEvent.TYPE_MOUNTING, 0.9, now));

        ArgumentCaptor<TwinState> captor = ArgumentCaptor.forClass(TwinState.class);
        verify(twinStateMapper).updateById(captor.capture());
        assertEquals("SUSPECTED_HEAT", captor.getValue().getState().get("estrus_status"));
        assertEquals("INFERRED", captor.getValue().getStateNature());
        assertEquals("EVT-1", captor.getValue().getSourceEventId());
        verify(cowTimelineMapper).insert(any(CowTimeline.class));
    }

    @Test
    void mountingLowConfidenceKeepsEstrusStatus() {
        // MOUNTING 但置信度 < 0.8 → 不更新 estrus_status（仍追加时间线留痕）
        twinUpdater.apply(event(UnifiedEvent.TYPE_MOUNTING, 0.5, LocalDateTime.now()));

        verify(cowTimelineMapper).insert(any(CowTimeline.class));
        verify(twinStateMapper, never()).selectById(any());
        verify(twinStateMapper, never()).updateById(any(TwinState.class));
    }

    @Test
    void lamenessSetsLamenessRisk() {
        // LAMENESS → health_status 置 LAMENESS_RISK
        LocalDateTime now = LocalDateTime.now();
        when(twinStateMapper.selectById("COW-0001")).thenReturn(existingState(now.minusMinutes(5)));
        when(twinStateMapper.updateById(any(TwinState.class))).thenReturn(1);

        twinUpdater.apply(event(UnifiedEvent.TYPE_LAMENESS, 0.7, now));

        ArgumentCaptor<TwinState> captor = ArgumentCaptor.forClass(TwinState.class);
        verify(twinStateMapper).updateById(captor.capture());
        assertEquals("LAMENESS_RISK", captor.getValue().getState().get("health_status"));
        verify(cowTimelineMapper).insert(any(CowTimeline.class));
    }

    @Test
    void deviceOfflineWithoutCowIdDoesNotTouchCowTwin() {
        // DEVICE_OFFLINE 无 cowId → 与牛只无关：不改牛状态、不写牛时间线
        UnifiedEvent e = event(UnifiedEvent.TYPE_DEVICE_OFFLINE, null, LocalDateTime.now());
        e.setCowId(null);
        e.setDeviceId("DEV-01");

        twinUpdater.apply(e);

        verifyNoInteractions(twinStateMapper, cowTimelineMapper, cowProfileMapper);
    }

    @Test
    void syncStateDoesNotChangeTwinState() {
        // SYNC_STATE → 不改孪生当前状态（代码按设计仍追加一条时间线，但不触碰 twin_state）
        twinUpdater.apply(event(UnifiedEvent.TYPE_SYNC_STATE, null, LocalDateTime.now()));

        verify(cowTimelineMapper).insert(any(CowTimeline.class));
        verifyNoInteractions(twinStateMapper, cowProfileMapper);
    }

    @Test
    void lateEventAppendsTimelineOnlyWithoutRollback() {
        // 迟到事件（event_time 早于 twin_state 当前 event_time）→ 只追加时间线，状态不回退
        LocalDateTime now = LocalDateTime.now();
        TwinState current = existingState(now);
        when(twinStateMapper.selectById("COW-0001")).thenReturn(current);

        twinUpdater.apply(event(UnifiedEvent.TYPE_MOUNTING, 0.95, now.minusHours(1)));

        verify(cowTimelineMapper).insert(any(CowTimeline.class));
        verify(twinStateMapper, never()).updateById(any(TwinState.class));
        // 当前状态与事件时间保持原值，未被迟到事件回退
        assertEquals("NORMAL", current.getState().get("estrus_status"));
        assertEquals(now, current.getEventTime());
    }

    @Test
    void optimisticLockConflictRetriesUntilSuccess() {
        // @Version 冲突（updateById 返回 0）→ 重新读取并重试，第二次成功
        LocalDateTime now = LocalDateTime.now();
        when(twinStateMapper.selectById("COW-0001"))
                .thenReturn(existingState(now.minusMinutes(1)))
                .thenReturn(existingState(now.minusMinutes(1)));
        when(twinStateMapper.updateById(any(TwinState.class))).thenReturn(0, 1);

        twinUpdater.apply(event(UnifiedEvent.TYPE_MOUNTING, 0.9, now));

        verify(twinStateMapper, times(2)).selectById("COW-0001");
        verify(twinStateMapper, times(2)).updateById(any(TwinState.class));
    }
}
