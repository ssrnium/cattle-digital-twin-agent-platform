---
name: lameness-check
description: 跛行排查 SOP：查事件证据 → 时间线对比 → 建议兽医检查项
when_to_use: 用户询问某头牛的跛行事件、走路异常、蹄病，或要求排查 LAMENESS 类事件时使用
user-invocable: true
---

# 跛行排查 SOP

收到跛行（LAMENESS）排查请求时，按以下步骤执行：

1. **查事件证据**：`list_events(event_type="LAMENESS", cow_id=...)`，记录每次事件的
   event_id、置信度、`evidence_ref`（视频/图像证据位置），低置信度事件要标注出来。
2. **查档案与孪生状态**：`query_cow_profile(cow_id)`，确认 `health_status` 当前推断值。
3. **时间线对比**：`query_cow_timeline(cow_id)`，判断跛行是首次出现还是反复发作，
   是否伴随采食/活动量下降等其他异常记录。
4. **输出建议**：
   - 建议兽医检查项（蹄部检查、步态评分、体温等）；
   - 如需兽医到场，说明理由后调用 `create_work_order(type="VET_CHECK", ...)`（写操作，等用户确认）；
   - 所有结论必须引用 cow_id 与 event_id；证据不足时明说，不要臆测病因。
