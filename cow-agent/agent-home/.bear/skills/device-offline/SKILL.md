---
name: device-offline
description: 设备离线排查 SOP：查心跳与待补传数 → 算断网时长 → 给处置建议
when_to_use: 用户询问摄像头/边缘节点离线、设备断网、数据补传，或排查 DEVICE_OFFLINE 类事件时使用
user-invocable: true
---

# 设备离线排查 SOP

收到设备离线排查请求时，按以下步骤执行：

1. **查设备列表**：`list_devices()`，找到目标设备的 `onlineStatus`（60s 心跳阈值计算属性）、
   `offlineSeconds`（断网时长）、`pendingCount`（本地待补传事件数）、`lastHeartbeatAt`。
2. **查离线事件**：`list_events(event_type="DEVICE_OFFLINE", device_id=...)` 与
   `DEVICE_RECOVERED`，确认离线发生的准确时间与是否已恢复。
3. **给处置建议**：
   - 断网时长 < 10 分钟且 pendingCount 正常增长：多为网络抖动，观察即可
     （边缘侧有 ≥72h 本地缓存，数据不丢）；
   - 长时间离线：建议现场检查边缘节点供电 / 网络；
   - 恢复后 pendingCount 应逐步归零（按 HIGH 优先补传），未归零说明补传异常；
   - 需要派人处理时，说明理由后调用
     `create_work_order(type="DEVICE_REPAIR", device_id=..., source_event_id=...)`
     （写操作，等用户确认）。
