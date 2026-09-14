package com.portfolio.cow.modules.event.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.PageResult;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.modules.device.service.DeviceService;
import com.portfolio.cow.modules.event.dto.EventIngestRequest;
import com.portfolio.cow.modules.event.dto.IngestResponse;
import com.portfolio.cow.modules.event.entity.UnifiedEvent;
import com.portfolio.cow.modules.event.mapper.UnifiedEventMapper;
import com.portfolio.cow.modules.event.service.EventIngestService;
import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/api/v1/events")
@RequiredArgsConstructor
public class EventController {

    private final EventIngestService eventIngestService;
    private final UnifiedEventMapper eventMapper;
    private final DeviceService deviceService;
    private final ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule());

    /**
     * 边缘事件上报（单条对象或数组批量）。
     * 安全链上简化放行，凭证校验在这里做：X-Device-Key 头 + body 内 device_id。
     */
    @PostMapping
    public Result<List<IngestResponse>> report(@RequestHeader(value = "X-Device-Key", required = false) String deviceKey,
                                               @RequestBody JsonNode body) throws Exception {
        List<IngestResponse> results = new ArrayList<>();
        if (body.isArray()) {
            for (JsonNode item : body) {
                results.add(ingestOne(item, deviceKey));
            }
        } else {
            results.add(ingestOne(body, deviceKey));
        }
        return Result.ok(results);
    }

    private IngestResponse ingestOne(JsonNode node, String deviceKey) throws Exception {
        EventIngestRequest req = objectMapper.treeToValue(node, EventIngestRequest.class);
        // 设备凭证校验（SYNC_STATE 等设备类事件也必须来自合法设备）
        if (StringUtils.hasText(req.getDeviceId())) {
            deviceService.checkDeviceKey(req.getDeviceId(), deviceKey);
        } else if (!StringUtils.hasText(deviceKey)) {
            throw new BizException(401, "缺少设备凭证 X-Device-Key");
        }
        return eventIngestService.ingest(req);
    }

    @GetMapping
    public Result<PageResult<UnifiedEvent>> page(@RequestParam(defaultValue = "1") long page,
                                                 @RequestParam(defaultValue = "10") long size,
                                                 @RequestParam(required = false) String eventType,
                                                 @RequestParam(required = false) String cowId,
                                                 @RequestParam(required = false) String deviceId) {
        LambdaQueryWrapper<UnifiedEvent> wrapper = new LambdaQueryWrapper<UnifiedEvent>()
                .eq(StringUtils.hasText(eventType), UnifiedEvent::getEventType, eventType)
                .eq(StringUtils.hasText(cowId), UnifiedEvent::getCowId, cowId)
                .eq(StringUtils.hasText(deviceId), UnifiedEvent::getDeviceId, deviceId)
                .orderByDesc(UnifiedEvent::getEventTime);
        return Result.ok(PageResult.of(eventMapper.selectPage(new Page<>(page, size), wrapper)));
    }
}
