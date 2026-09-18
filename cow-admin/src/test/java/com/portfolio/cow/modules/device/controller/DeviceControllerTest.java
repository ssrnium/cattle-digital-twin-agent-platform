package com.portfolio.cow.modules.device.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.modules.device.entity.Device;
import com.portfolio.cow.modules.device.mapper.DeviceMapper;
import com.portfolio.cow.modules.device.service.DeviceService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * 设备在线为计算属性（60s 心跳阈值），不入库——断网心跳翻转卖点的判定逻辑。
 */
@ExtendWith(MockitoExtension.class)
class DeviceControllerTest {

    @Mock
    private DeviceMapper deviceMapper;
    @Mock
    private DeviceService deviceService;

    @InjectMocks
    private DeviceController deviceController;

    private Device deviceWithHeartbeat(LocalDateTime heartbeatAt) {
        Device d = new Device();
        d.setId(1L);
        d.setDeviceId("edge-node-01");
        d.setType(Device.TYPE_EDGE_NODE);
        d.setLastHeartbeatAt(heartbeatAt);
        return d;
    }

    @Test
    void heartbeatWithin60sIsOnline() {
        when(deviceMapper.selectList(any(LambdaQueryWrapper.class)))
                .thenReturn(List.of(deviceWithHeartbeat(LocalDateTime.now().minusSeconds(30))));
        List<Map<String, Object>> views = deviceController.list().getData();
        assertEquals("ONLINE", views.get(0).get("onlineStatus"));
        assertEquals(0L, views.get(0).get("offlineSeconds"));
    }

    @Test
    void heartbeatBeyond60sFlipsOffline() {
        // 断网 1 小时无心跳 → OFFLINE，offlineSeconds 给出断网时长
        when(deviceMapper.selectList(any(LambdaQueryWrapper.class)))
                .thenReturn(List.of(deviceWithHeartbeat(LocalDateTime.now().minusSeconds(3600))));
        List<Map<String, Object>> views = deviceController.list().getData();
        assertEquals("OFFLINE", views.get(0).get("onlineStatus"));
        long offlineSeconds = (Long) views.get(0).get("offlineSeconds");
        assertTrue(offlineSeconds >= 3590, "offlineSeconds 应约等于断网时长, actual=" + offlineSeconds);
    }

    @Test
    void neverHeartbeatIsOfflineWithoutDuration() {
        when(deviceMapper.selectList(any(LambdaQueryWrapper.class)))
                .thenReturn(List.of(deviceWithHeartbeat(null)));
        List<Map<String, Object>> views = deviceController.list().getData();
        assertEquals("OFFLINE", views.get(0).get("onlineStatus"));
        assertEquals(0L, views.get(0).get("offlineSeconds"));
    }

    @Test
    void heartbeatMissingDeviceIdBadRequest() {
        Map<String, Object> body = new HashMap<>();
        body.put("deviceKey", "secret-key-01");
        BizException e = assertThrows(BizException.class, () -> deviceController.heartbeat(body));
        assertEquals(400, e.getCode());
    }

    @Test
    void detailOfUnknownDeviceNotFound() {
        when(deviceMapper.selectOne(any(LambdaQueryWrapper.class))).thenReturn(null);
        BizException e = assertThrows(BizException.class, () -> deviceController.detail("ghost-device"));
        assertEquals(404, e.getCode());
    }
}
