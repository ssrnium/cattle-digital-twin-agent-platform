# PROJECT_STATUS — 单牛数字孪生与健康繁殖任务管理平台

> 更新日期：2026-09-20 ｜ 当前版本：**v0.2.0-acceptance**（首场验证版切片，全链路验收通过）

## 状态速览

| 项 | 当前状态 |
|---|---|
| 范围 | 20号牛棚 / 103 头奶牛 / 爬跨（MOUNTING）+ 跛行（LAMENESS）两类事件 / 告警工单闭环 / 断网缓存恢复 / 牧场智能体 |
| AI 模型 | **mock 推理**（cow-ai 返回确定性伪随机结果；第一阶段真实权重待接） |
| 智能体 LLM | 真实：DeepSeek `deepseek-flash`（OpenAI 兼容），写操作需人工确认 |
| 已验证运行环境 | Windows 11 本地：便携 PostgreSQL 16.10 + Redis 5.0.14 + **Mosquitto 2.0.22**（1883）+ JDK 17.0.2 + Node 24 + Python 3.9 venv；Docker 未安装，compose 未验证 |
| 已通过测试 | 浏览器主链路 **15/15**（acceptance/cow_d1_main.py）；写操作确认机制 **7/7**（cow_d2_agent_confirm.py，审批下沉后复跑）；cow-admin 单测 **64 项**（事件幂等/状态机/乐观锁/迟到事件/规则引擎/心跳在线翻转/JWT/智能体审计/审批下沉强制点等，mvn test）；cow-agent pytest **21 passed**；admin BUILD SUCCESS；web `npm run build` 绿（vue-tsc type-check 0 错误，已接入 build 前置） |
| 下一阶段入口 | 真实爬跨/跛行模型权重接入（第一阶段资产）、断网 72h 长时演示、Docker 全栈 |

## 已完成（全部有运行验证证据）

1. 七服务本地启动互联：admin(8081) / ai(8001) / agent(8003) / web(5174) / PostgreSQL / Redis / Mosquitto；
2. 登录与 JWT 鉴权（admin/vet/breeder/svc-agent；未登录重定向、错误 deviceKey 401）；
3. **MQTT 事件接入**：edge 模拟器 → Mosquitto → admin 入站订阅 `farm/+/event`（真实 broker 实测收发）；
4. **event_id 幂等去重**：同一 event_id 重复上报 → duplicated=true，绝不重复落库/告警（单测 + HTTP + 断网恢复重发三重证据，重复告警=0）；
5. **迟到事件处理**：event_time 早于当前状态只追加时间线不回退状态（DB 实测）；
6. **数字孪生状态管理**：MOUNTING(≥0.8)→SUSPECTED_HEAT、LAMENESS→LAMENESS_RISK，牛棚二维图 5s 轮询变色（15 头异常色圆点实测）；
7. **工单状态机 + 乐观锁**：NEW→DISPATCHED→PROCESSING→PENDING_REVIEW→CLOSED 全流转，非法流转拒绝，version 冲突 409（浏览器逐步操作 + DB version=4 递增）；
8. **断网缓存与恢复补传**：offline 模式 SQLite 缓存（HIGH/LOW 优先级）→ reconnect 按优先级补传 → 重发同批 event_id 演示"重复告警 0"；
9. **牧场智能体**：多轮对话（上下文记忆实测）、只读工具查询（档案/时间线/事件/孪生/工单/设备）、SOP 命中（mounting-review 等）、**高风险写操作人工确认**（模型提意图 → 系统拦截 park → 前端弹窗 → 批准执行 → 工单落库）；
10. 操作审计：智能体对话落 agent_session/agent_message 表；
11. 平台单测与构建全绿；git 建仓。
12. 面试官视角强化（2026-09-18）：**cow-admin 核心机制单测补齐至 43 项**（TwinUpdater 迟到不回退/置信度门控/乐观锁重试、TaskRuleEngine 24h 收敛与设备去重、Outbox 降级，新增设备 60s 心跳在线翻转/401 凭证、JWT 签发/过期/篡改、智能体审计落库与审批转发、MQTT 批量隔离，mvn test 全绿）；README 挂 4 张真实运行截图与验收记录索引；断网心跳 OFFLINE/ONLINE 翻转完成浏览器实证（60s 窗口，截图留证）；验收脚本入库 acceptance/；新增 GitHub Actions CI（admin mvn test / agent·ai pytest / web build 含 vue-tsc 前置）。
13. 前端全面升级与翻转实证（2026-09-20，参考高保真样稿 smart-ranch-digital-twin 仿写）：**全局暗色大屏设计体系**（设计 token + Element Plus 暗色变量 + 玻璃拟态侧边栏/顶栏，权限过滤与路由守卫零改动）、**Dashboard 重构**（KPI/事件趋势/健康环图/异常预警/Agent 会话面板，全部真实接口数据，无虚构）、**登录页换壳**（品牌叙事+玻璃登录卡，真实登录逻辑保留）、**AI 助手气泡升级**（trace-step 工具轨迹 + thinking 动画，审批弹窗与轮询不动）、**牛棚孪生页 Three.js 3D 升级**（InstancedMesh 承载 103 头牛按轮询实时变色，OrbitControls+Raycaster 选牛弹个体卡片跳详情，WebGL 降级保留 SVG，three 路由级动态加载不进主 chunk）、request 拦截器 silent 静默请求抛光（装饰性调用不再弹错误 toast）；**设备心跳翻转全流程实证**（`acceptance/cow_device_flip.py`：OFFLINE(161719s)→心跳→ONLINE→停跳 75s→OFFLINE 并累计断网时长，API 断言 + 页面截图双证据）；新增实证截图 4 张入 docs/screenshots/（暗色看板/3D 孪生/离线翻转/AI 助手），浏览器逐页自检 0 console error。
14. 审批边界审计与离线生命周期实证（2026-09-20 晚）：**审批边界审计**（`docs/approval_boundary_audit.md`）——确认 svc-agent 可绕过 agent 层审批直连建单（SERVICE 角色含 task:create），审批关卡当前在 cow-agent 工具层；现有四层防线（权限收敛/agent 层闭环/审计落库/批准 exactly-once）与三项缺口如实记录，PENDING_ACTION 下沉方案完成设计备案；**设备离线完整生命周期实证**（`acceptance/cow_offline_lifecycle.py`，10/10）——断网缓存（周期性 DEVICE_OFFLINE HIGH + 心跳 3 连败停用）→ 恢复补传（DEDUP DEMO 重发 13 条全部去重）→ 2 条离线事件只建 1 张 HIGH 维修单 → 状态机全流转关闭 → 再次离线产生新一轮工单 → 同 event_id 重发 duplicated=true 不出单。
15. 72h 离线缓存容量口径与实测（2026-09-20 深夜）：`docs/offline_cache_72h.md` 定义容量口径——1 设备 × 1 事件/5s × 72h = **51,840 条**，SQLite ≈ 31.4MB（≈636 B/条），演示规模无容量压力故 `wal_buffer` 不设上限，生产多设备按公式线性放大；实测（`acceptance/cow_72h_capacity.py` + `cow-edge/drain_buffer.py`）——等量灌库 51,840 条（HIGH 10,368 / LOW 41,472）→ 断点续传（补传进程 kill 后重跑，"成功才删"语义下无丢失）→ **服务端精确 51,840 条且 `count(DISTINCT event_id)` = 51,840（零重复）** → 抽样 20 个 event_id 重发全部 `duplicated=true`；补传吞吐：16 线程并发 drain 44,980 条用时 308s（146 条/s，0 失败），本地 pending 清零。
16. **审批下沉后端强制（PENDING_ACTION）**（2026-09-21 凌晨，9bb7e89+a69b7a3，文档 `docs/approval_boundary_audit.md` 第五节）：新表 `pending_action`（action_id 唯一约束、PENDING/APPROVED/REJECTED/EXECUTED/EXPIRED 五态、120s 有效期）；cow-agent park 前注册动作（发起人按 agent_session 绑定，注册失败 fail-closed 拒绝写操作）；`/agent/confirm` 先落审批状态（批准人=发起人 403 / 过期作废 / 重复审批 409）再转发，转发失败补偿作废；**强制点**：SERVICE 角色建单必须携带 `X-Action-Id`（存在/APPROVED/未过期/参数摘要一致），同事务内建单 + APPROVED→EXECUTED 条件更新保证 **exactly-once**（重复 409 回滚）；svc-agent 无凭证/伪造凭证直连建单均 403（HTTP 实证）；d2 写操作确认流 7/7 复跑全绿（断言未放松）；**admin 单测 43→64、agent pytest 16→21 全绿**——审计三缺口（审批未下沉/无幂等键/批准人未绑定）全部关闭。
17. MQTT 与 HTTP 统一幂等入口实证（2026-09-21 凌晨，`acceptance/cow_mqtt_http_dedup.py`，4/4）：同一 event_id 先经 Mosquitto → MQTT 消费入库，再经 HTTP 补传 → `duplicated=true` 不重复落库；反向先 HTTP 后 MQTT 同样不重复——**传输方式不同，业务幂等边界统一由 event_id 保证**。
16. **智能体写操作审批下沉为后端强制（PENDING_ACTION）**（2026-09-21，`docs/approval_boundary_audit.md` 第五节）：新表 `pending_action`（action_id 唯一约束，PENDING/APPROVED/REJECTED/EXECUTED/EXPIRED 状态机，120s 有效期）——cow-agent park 前向 admin 注册（发起人按 agent_session 绑定不可伪造，注册失败 fail-closed 拒绝写操作）；`/agent/confirm` 先落审批状态（**批准人=发起人**校验、过期作废、重复审批 409）再转发 cow-agent，转发失败补偿作废；**强制点** `WorkOrderController.create`：SERVICE 角色必须携带 `X-Action-Id`（存在/APPROVED/未过期/参数摘要一致），同事务内建单 + APPROVED→EXECUTED 条件更新（**exactly-once**，重复提交 409 只一张单）；120s 超时 cow-agent 自动拒绝并同步作废凭证。实证：svc-agent 无凭证直连建单 **403**、伪造凭证 **403**；cow-admin 单测 **43→64**、cow-agent pytest **16→21**、`acceptance/cow_d2_agent_confirm.py` **7/7** 复跑全绿（断言未放松）。

18. **爬跨推理实装 YOLOv8m + 连续帧会话化**（2026-09-22）：`cow-ai/app/routers/infer.py` 的 `infer_mounting()` 从 mock 占位实装为真实推理——采购 YOLOv8m 行为权重（10 类含 mounting），**按 model.names 类别名过滤 mounting（不写死 class index）**，权重路径经 `MOUNTING_WEIGHTS_PATH` 配置、不随仓库分发；ultralytics/torch **懒导入 + 进程级缓存**，缺权重/缺依赖自动回落 mock（`mocked=True`）；torch/ultralytics 不进 requirements.txt，单独 `cow-ai/requirements-vision.txt`（注明 CPU 源，仅真实推理主机安装）。新增会话化模块 `app/services/behavior_session.py`（`sessionize`：连续 ≥3 帧超 0.4 开窗、连续 ≥5 帧低于阈值关窗，聚合 peak/avg/best_bbox，**一个窗口 = 一个事件**，解决同一行为几十帧产生几十个重复告警）与新端点 `POST /api/v1/infer/mounting/clip`（≤300 帧逐帧推理 → sessionize，mock 模式按伪置信度跑同一逻辑保证演示可复现）。**cow-ai pytest 4→17 全绿**（新增 sessionize 7 例 + 真实/mock 分支与类别名过滤 3 例 + clip 契约与帧数校验 3 例，（在无 torch 环境验证通过）。
19. **采购视觉权重端到端验证（2026-09-22，AutoDL 服务器实证）**：权重部署服务器 `/root/autodl-tmp/models/cow-behavior/`（**不入库**，`MOUNTING_WEIGHTS_PATH` 引用）；单帧真实推理：正样本 conf=0.717/2 检出、负样本 0 检出（`mocked=false`，`model_version=yolov8m-behavior-10cls-1.0`）；**会话化真实验证**：负×5+正×8+负×7 帧序列 → 恰好 **1 个行为窗口**（f5-f12，peak=0.826，avg=0.746）；窗口事件经设备凭证接入 → 幂等接受 → **孪生 COW-0043 `estrus_status=SUSPECTED_HEAT`**（event_time 与窗口一致）→ 规则引擎 24h 收敛正确跳过重复建单——**"真实视频识别 → 业务事件 → 孪生/工单"链路闭环**（torch 2.14.0+cpu + torchvision 0.29.0+cpu + ultralytics 8.4.158，32 核 CPU 推理）。

  **适用边界（如实记录）**：采购权重对真实高位俯拍机位视频（白天+夜视，63 帧抽测）在 conf≥0.05 下全零检出，判定其训练域（平视侧拍特写）不适用该机位；演示素材改用数据集帧的真实检出（`docs/screenshots/vision-mounting-demo.gif`，mounting 峰值 0.90，框为采购模型真实输出）。

## 正在开发（下一阶段）

1. **真实模型权重接入**（第一阶段资产：爬跨 YOLOv8m 已接入并会话化，剩余跛行 YOLOv11+RTMPose+XGBoost 推理链，cow-ai 的 infer 接口留插入点）；
2. 断网 72h 长时缓存演示（验收口径：结构化事件离线缓存 ≥72h、补传 ≤6h）；
3. 设备离线告警链路演示（60s 心跳超时 → DEVICE_OFFLINE 事件 → 维修工单）；
4. Docker compose 全栈（mosquitto/chromadb 等镜像编排）。

## 后续规划（企业规划书的后续阶段，不在首场验证版）

- 牛群/牧场级孪生分析、多租户集团运营、预测智能（产奶/疾病预测）、Three.js 三维、第二牧场复制。

## 已知问题

| # | 问题 | 影响 | 状态 |
|---|---|---|---|
| 1 | AI 推理为 mock（置信度伪随机） | 演示事件为模拟器产生 | 下一阶段接真实权重 |
| 2 | 智能体对建单较谨慎（需两轮对话/明确指令） | 演示话术需按 README 脚本走 | 机制已验证；话术已写入演示脚本 |
| 3 | DB 宕机时接口阻塞 ~30s（Hikari）才返回 500 | 极端场景体验 | 可接受，恢复自动可用 |
| 4 | MQTT 用 Mosquitto 便携版（本地），compose 用 eclipse-mosquitto 镜像 | 部署差异 | compose 未验证 |
| 5 | cow-agent 嵌入 BearCode 副本（cow-agent/bear/）相对母版有 2 处 bugfix（见验收报告"已修复问题"4/5） | 母版目录零改动；嵌入副本 2 处修复已在验收报告列明 | 已在文档声明 |

## 验证命令速查

```bash
# 构建/测试
mvn -s tools/settings.xml package                     # cow-admin（含 64 项单测）
cow-agent/.venv/Scripts/python -m pytest tests/       # 21 项
npm run build                                         # cow-web
# 验收
tools/pw-venv/Scripts/python acceptance/cow_d1_main.py           # 浏览器主链路 15 项
tools/pw-venv/Scripts/python acceptance/cow_d2_agent_confirm.py  # 写操作确认机制 7 项
# 断网演示
cow-edge/.venv/Scripts/python simulator.py --mode offline --duration 60 --interval 2
cow-edge/.venv/Scripts/python simulator.py --mode reconnect
```
