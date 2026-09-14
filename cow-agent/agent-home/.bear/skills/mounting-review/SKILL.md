---
name: mounting-review
description: 爬跨 / 疑似发情事件复核 SOP：查档案 → 查近期爬跨事件 → 查历史记录 → 给复核建议
when_to_use: 用户询问某头牛的爬跨事件、疑似发情、是否需要配种复核，或要求复核 MOUNTING 类事件时使用
user-invocable: true
---

# 爬跨 / 疑似发情复核 SOP

收到爬跨（MOUNTING）事件复核请求时，严格按以下步骤执行，每步都要用工具取数，禁止跳步下结论：

1. **查档案**：`query_cow_profile(cow_id)`，确认牛只状态（ACTIVE 与否）、所在区域、当前孪生状态中的
   `estrus_status` / `health_status` 推断值。
2. **查近期爬跨事件**：`list_events(event_type="MOUNTING", cow_id=...)`，关注：
   - 事件数量与时间分布（21 天左右的发情周期是否复现）；
   - `confidence` 置信度（低置信度需提醒人工查看 evidence_ref 视频片段）。
3. **查时间线**：`query_cow_timeline(cow_id)`，对照历史爬跨 / 配种 / 妊检记录，
   判断本次是否符合发情周期规律。
4. **给复核建议**，必须包含：
   - 结论（疑似发情成立 / 证据不足 / 疑似误报）及引用的 cow_id、event_id 列表；
   - 建议动作（如：安排繁育员现场查情、创建 BREEDING_REVIEW 工单）；
   - 如需创建工单，先说明理由，再调用 `create_work_order`（写操作，等用户确认）。
