package com.portfolio.cow.modules.stats.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.modules.cow.entity.CowProfile;
import com.portfolio.cow.modules.cow.mapper.CowProfileMapper;
import com.portfolio.cow.modules.device.entity.Device;
import com.portfolio.cow.modules.device.mapper.DeviceMapper;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import com.portfolio.cow.modules.event.mapper.UnifiedEventMapper;
import com.portfolio.cow.modules.task.entity.WorkOrder;
import com.portfolio.cow.modules.task.mapper.WorkOrderMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/stats")
@RequiredArgsConstructor
public class StatsController {

    private final CowProfileMapper cowProfileMapper;
    private final UnifiedEventMapper eventMapper;
    private final WorkOrderMapper workOrderMapper;
    private final DeviceMapper deviceMapper;

    /** 牛棚总览：牛总数、健康状态分布、今日事件数、未关闭工单数、设备在线率 */
    @GetMapping("/barn")
    public Result<Map<String, Object>> barn() {
        Map<String, Object> data = new HashMap<>();

        Long totalCows = cowProfileMapper.selectCount(null);
        data.put("totalCows", totalCows);

        // 健康状态分布（jsonb group by）；无孪生记录的牛计入 UNKNOWN
        List<Map<String, Object>> healthDist = cowProfileMapper.selectHealthDistribution();
        data.put("healthDistribution", healthDist);

        Long todayEvents = eventMapper.selectCount(new LambdaQueryWrapper<UnifiedEvent>()
                .ge(UnifiedEvent::getEventTime, LocalDate.now().atStartOfDay()));
        data.put("todayEvents", todayEvents);

        // 近 7 天事件趋势（dashboard 折线图）
        List<Map<String, Object>> eventTrend = eventMapper.selectEventTrend(7);
        data.put("eventTrend", eventTrend);

        Long openOrders = workOrderMapper.selectCount(new LambdaQueryWrapper<WorkOrder>()
                .in(WorkOrder::getState, WorkOrder.STATE_NEW, WorkOrder.STATE_DISPATCHED,
                        WorkOrder.STATE_PROCESSING, WorkOrder.STATE_PENDING_REVIEW));
        data.put("openOrders", openOrders);

        Long totalDevices = deviceMapper.selectCount(null);
        Long onlineDevices = deviceMapper.selectCount(new LambdaQueryWrapper<Device>()
                .ge(Device::getLastHeartbeatAt, LocalDateTime.now().minusSeconds(60)));
        double onlineRate = totalDevices == 0 ? 0.0 : onlineDevices * 1.0 / totalDevices;
        data.put("totalDevices", totalDevices);
        data.put("onlineDevices", onlineDevices);
        data.put("deviceOnlineRate", Math.round(onlineRate * 1000) / 10.0); // 百分比，保留 1 位

        return Result.ok(data);
    }
}
