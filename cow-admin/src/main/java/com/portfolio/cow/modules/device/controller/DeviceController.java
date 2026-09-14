package com.portfolio.cow.modules.device.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.device.entity.Device;
import com.portfolio.cow.modules.device.mapper.DeviceMapper;
import com.portfolio.cow.modules.device.service.DeviceService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/devices")
@RequiredArgsConstructor
public class DeviceController {

    /** 心跳间隔阈值：60s 内有心跳视为在线（计算属性，不入库） */
    private static final long ONLINE_THRESHOLD_SECONDS = 60;

    private final DeviceMapper deviceMapper;
    private final DeviceService deviceService;

    /** 设备心跳：body 含 device_id + deviceKey + pending_count + last_sync_at */
    @PostMapping("/heartbeat")
    public Result<Map<String, Object>> heartbeat(@RequestBody Map<String, Object> body) {
        String deviceId = (String) body.get("device_id");
        String deviceKey = (String) body.get("deviceKey");
        if (deviceId == null) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(), "device_id 不能为空");
        }
        Integer pendingCount = body.get("pending_count") == null
                ? null : Integer.valueOf(String.valueOf(body.get("pending_count")));
        LocalDateTime lastSyncAt = body.get("last_sync_at") == null
                ? null : LocalDateTime.parse(String.valueOf(body.get("last_sync_at"))
                .replace('T', ' ').substring(0, 19),
                java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));

        Device device = deviceService.heartbeat(deviceId, deviceKey, pendingCount, lastSyncAt);
        Map<String, Object> data = new HashMap<>();
        data.put("device_id", device.getDeviceId());
        data.put("server_time", LocalDateTime.now().toString());
        return Result.ok(data);
    }

    /** 设备列表：在线状态为计算属性（60s 阈值），不入库 */
    @GetMapping
    public Result<List<Map<String, Object>>> list() {
        List<Device> devices = deviceMapper.selectList(
                new LambdaQueryWrapper<Device>().orderByAsc(Device::getDeviceId));
        return Result.ok(devices.stream().map(this::toView).toList());
    }

    @GetMapping("/{deviceId}")
    public Result<Map<String, Object>> detail(@PathVariable String deviceId) {
        Device device = deviceMapper.selectOne(
                new LambdaQueryWrapper<Device>().eq(Device::getDeviceId, deviceId));
        if (device == null) {
            throw new BizException(ResultCode.NOT_FOUND);
        }
        return Result.ok(toView(device));
    }

    private Map<String, Object> toView(Device d) {
        Map<String, Object> view = new HashMap<>();
        view.put("id", d.getId());
        view.put("deviceId", d.getDeviceId());
        view.put("type", d.getType());
        view.put("name", d.getName());
        view.put("barnId", d.getBarnId());
        view.put("lastHeartbeatAt", d.getLastHeartbeatAt());
        view.put("lastSyncAt", d.getLastSyncAt());
        view.put("pendingCount", d.getPendingCount());
        view.put("meta", d.getMeta());

        LocalDateTime now = LocalDateTime.now();
        boolean online = d.getLastHeartbeatAt() != null
                && Duration.between(d.getLastHeartbeatAt(), now).getSeconds() < ONLINE_THRESHOLD_SECONDS;
        view.put("onlineStatus", online ? "ONLINE" : "OFFLINE");
        // 断网时长（秒）：离线时 = 当前时间 - 最后心跳
        view.put("offlineSeconds", online || d.getLastHeartbeatAt() == null
                ? 0 : Duration.between(d.getLastHeartbeatAt(), now).getSeconds());
        return view;
    }
}
