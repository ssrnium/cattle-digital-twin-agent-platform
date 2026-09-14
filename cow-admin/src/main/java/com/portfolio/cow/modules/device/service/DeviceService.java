package com.portfolio.cow.modules.device.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.modules.device.entity.Device;
import com.portfolio.cow.modules.device.mapper.DeviceMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class DeviceService {

    private final DeviceMapper deviceMapper;

    /** 设备凭证校验：心跳与 HTTP 事件上报共用 */
    public Device checkDeviceKey(String deviceId, String deviceKey) {
        if (!StringUtils.hasText(deviceKey)) {
            throw new BizException(401, "缺少设备凭证 deviceKey");
        }
        Device device = deviceMapper.selectOne(
                new LambdaQueryWrapper<Device>().eq(Device::getDeviceId, deviceId));
        if (device == null || !deviceKey.equals(device.getDeviceKey())) {
            throw new BizException(401, "设备凭证无效: " + deviceId);
        }
        return device;
    }

    public Device heartbeat(String deviceId, String deviceKey,
                            Integer pendingCount, LocalDateTime lastSyncAt) {
        Device device = checkDeviceKey(deviceId, deviceKey);
        device.setLastHeartbeatAt(LocalDateTime.now());
        if (pendingCount != null) {
            device.setPendingCount(pendingCount);
        }
        if (lastSyncAt != null) {
            device.setLastSyncAt(lastSyncAt);
        }
        deviceMapper.updateById(device);
        return device;
    }
}
