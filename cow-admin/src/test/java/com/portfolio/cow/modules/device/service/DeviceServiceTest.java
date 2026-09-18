package com.portfolio.cow.modules.device.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.modules.device.entity.Device;
import com.portfolio.cow.modules.device.mapper.DeviceMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeviceServiceTest {

    @Mock
    private DeviceMapper deviceMapper;

    @InjectMocks
    private DeviceService deviceService;

    private Device edgeNode() {
        Device d = new Device();
        d.setId(1L);
        d.setDeviceId("edge-node-01");
        d.setDeviceKey("secret-key-01");
        d.setType(Device.TYPE_EDGE_NODE);
        return d;
    }

    @Test
    void missingDeviceKeyRejected401() {
        BizException e = assertThrows(BizException.class,
                () -> deviceService.checkDeviceKey("edge-node-01", null));
        assertEquals(401, e.getCode());
    }

    @Test
    void wrongDeviceKeyRejected401() {
        when(deviceMapper.selectOne(any(LambdaQueryWrapper.class))).thenReturn(edgeNode());
        BizException e = assertThrows(BizException.class,
                () -> deviceService.checkDeviceKey("edge-node-01", "bad-key"));
        assertEquals(401, e.getCode());
    }

    @Test
    void unknownDeviceRejected401() {
        when(deviceMapper.selectOne(any(LambdaQueryWrapper.class))).thenReturn(null);
        BizException e = assertThrows(BizException.class,
                () -> deviceService.checkDeviceKey("ghost-device", "secret-key-01"));
        assertEquals(401, e.getCode());
    }

    @Test
    void heartbeatUpdatesPendingCountAndPersists() {
        // 断网恢复后的心跳携带 pending_count：服务端落库，设备页据此展示缓存积压
        when(deviceMapper.selectOne(any(LambdaQueryWrapper.class))).thenReturn(edgeNode());
        Device d = deviceService.heartbeat("edge-node-01", "secret-key-01", 7, null);
        assertEquals(7, d.getPendingCount());
        assertNotNull(d.getLastHeartbeatAt());
        verify(deviceMapper).updateById(d);
    }
}
