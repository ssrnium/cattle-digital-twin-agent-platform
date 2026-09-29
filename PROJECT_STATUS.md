# PROJECT_STATUS — 单牛数字孪生与健康繁殖任务管理平台

> 更新日期：2026-09-29 ｜ 当前版本：**v0.3.0-env-closed-loop**（环境遥测与设备维护知识接入闭环，在线验收 19/19 + 9.29 补证 24 项）

## 状态速览

| 项 | 当前状态 |
|---|---|
| 范围 | 20号牛棚 / 103 头奶牛 / 爬跨（MOUNTING）+ 跛行（LAMENESS）两类事件 / 告警工单闭环 / 断网缓存恢复 / 牧场智能体 |
| AI 模型 | **mock 推理**（cow-ai 返回确定性伪随机结果；第一阶段真实权重待接） |
| 智能体 LLM | 真实：DeepSeek `deepseek-flash`（OpenAI 兼容），写操作需人工确认 |
| 已验证运行环境 | Windows 11 本地：便携 PostgreSQL 16.10 + Redis 5.0.14 + **Mosquitto 2.0.22**（1883）+ JDK 17.0.2 + Node 24 + Python 3.9 venv；Docker 未安装，compose 未验证 |
| 已通过测试 | 浏览器主链路 **15/15**（acceptance/cow_d1_main.py）；写操作确认机制 **7/7**（cow_d2_agent_confirm.py，审批下沉后复跑）；cow-admin 单测 **64 项**（事件幂等/状态机/乐观锁/迟到事件/规则引擎/心跳在线翻转/JWT/智能体审计/审批下沉强制点等，mvn test）；cow-agent pytest **79 passed**；admin BUILD SUCCESS；web `npm run build` 绿（vue-tsc type-check 0 错误，已接入 build 前置） |
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
20. **Agent Runtime 闭环 + 评测广度扩展（2026-09-27，cow-agent）**：运行时闭环已落地——MCP stdio 子进程（发现/只读放行/写审批/失败恢复）、FeedbackLedger 反馈状态机（candidate→add/merge/discard+快照回滚）、子 Agent 权限继承修复（default 不再隐式升级 bypassPermissions）。本轮把离线确定性评测从"能用"扩到"能拿出手"：**Skill 检索基准 4→16 例**（4 个领域 SOP 各 3-4 例：标准/口语化/近义干扰问法 + 2 例域外负例，`evaluate_skills` 新增 `expected_skill=null` 负例判定——Top-1 分数须低于生产默认阈值 0.08），**Tool 契约基准 4→12 例**（覆盖全部 7 个领域工具：单工具、2-3 步序列、可选参数省略、cow_id 格式、顺序敏感），另从母版 **API-Bank level-1-api 选 26 条改写成领域兼容格式**（`eval/tool_benchmark_apibank_subset.json`，文件内 `_meta` 记录来源与映射规则，母版只读未复制）。复跑结果（全部真实、未凑分）：Skill Top-1 14/14、MRR 1.0、**OOD 负例拒识 2/2**；Tool 选择/参数合法/序列精确三项 12/12 与 API-Bank 子集 26/26 均 100%；近义干扰案例的候选间距逐条记录在证据 JSON（如 mounting-review-03 目标 0.364 vs 干扰 0.281）。证据：`cow-agent/docs/evidence/agent_runtime_evidence.json`、`cow-agent/docs/agent_runtime_evidence.md`；cow-agent pytest 30 项全绿。
21. **子 Agent 实战落地 + 自进化端到端演示（2026-09-27，cow-agent）**：补齐两个证据缺口。**缺口一**：子 Agent 机制此前只有权限修复没有业务实战——新增领域子代理类型 `cow-investigator`（单牛排查专员，`app/cow_agent.py::CowAgent._execute_agent_tool` 按母版 launch 机制在 app 层特化，母版零改动；agent 工具 type 枚举经 `cow_agent_tools()` 拷贝扩展），场景「ZONE-B 异常的几头牛都什么情况」：主 Agent `list_events` 圈定 COW-0042/COW-0057 → 逐头启动子 Agent（真实 `CowAgent.run_once` 独立循环，只挂 6 个只读领域工具、不可递归 agent 工具、继承父 permission_mode+confirm_fn）→ 汇总报告；`run_once` 响应新增 `subagent_runs` 结构化证据（tools_granted/tool_trace/tokens/report/权限字段）。权限边界由测试证明：子 Agent 脚本尝试 `create_work_order` 时确认请求 park 到父会话同一 confirm_fn，拒绝后罐头后端零建单，被拒意图留 `denied_tool_calls` 证据（`tests/test_subagent_investigation.py` 3 例）。**缺口二**：`scripts/demo_skill_evolution.py` 在 agent-home skills 临时副本上重放自进化全生命周期——双 merge（0.1.0→0.1.1→0.1.2，merge 前快照逐字节等于旧版本）→ rollback 恢复最近快照 → 重复 rollback 幂等边界（快照 append-only 不弹栈）→ discard 零改动 → JSONL 审计链有序性校验，7 步结构化证据 + agent-home 整树指纹零污染校验。两演示 LLM 均为脚本化回放（`app/offline_fakes.py`，不花真实 API 额度）、cow-admin 为罐头 MockTransport，离线可复跑。证据：`docs/evidence/subagent_investigation_demo.json`、`docs/evidence/skill_evolution_demo.json`；cow-agent pytest **30→35 项全绿**。
22. **会话毒化修复：历史完整性守卫（2026-09-27，cow-agent）**：真实 DeepSeek 评测（`scripts/run_live_model_eval.py`，主 agent 编写的线上评测脚本，本轮纳入跟踪）实锤——某轮异常在历史留下悬空 tool_calls（assistant 带 tool_calls 但无对应 tool 结果），DeepSeek 下一轮起对该会话一律 400（tool_calls must be followed by tool messages），会话永久毒化。修复落点 `app/patch.py::repair_dangling_tool_calls`：`_call_openai_stream` 包装链路发送前扫描历史（先于既有 id 成对重写），缺失配对处**只修不剥**注入合成错误 tool 消息（`[runtime] tool result missing: repaired by history integrity guard`），WARNING 记录 `repaired N dangling tool_calls (session=…, ids=[…])`；修复在落盘历史生效故幂等，正常历史零改动零日志，id 重写行为无回归。新增 `tests/test_history_integrity_guard.py` 3 例（部分缺失/整组悬空/跨 user 消息的位置与现场保留断言、健康历史零改动、端到端毒化→修复→第二轮幂等），文档补「历史完整性守卫」一节；cow-agent pytest **35→38 项全绿**，run_agent_evals 与两个 demo 脚本复跑不受影响。
23. **真实模型线上评测终版收口（2026-09-27，AutoDL 服务器实证，`scripts/run_live_model_eval.py` 终版入库）**：DeepSeek deepseek-flash 真实调用、经 admin 代理 chat，与离线回放分开报告。**终版 deterministic 5/6 通过**（不凑 6/6）：query-cow / mounting-review（会话复用语义断言修正）/ device-offline / follow-up 全过；**write-confirm 通过且为确认机制线上闭环实证**——模型真实调用 create_work_order → park 挂起（日志 `waiting confirm: create_work_order (action=…)`）→ 评测并发轮询 pending → 拒绝 → 无工单产生，另有 120s auto-denied 记录；**no-such-cow 按空响应如实计失败**——长会话 7 轮中 2 轮空响应，单点探针复核（新会话）该任务回复 680 字且诚实（"20 号牛棚没有 COW-9999 这头牛"附证据表）、zone-summary 3500 字，判定为小模型长会话偶发输出异常而非系统 bug。**重大正向发现**：zone-summary 探针中真实模型**自发调用子 Agent 机制 8 次**（trace `agent`×8、"逐头下发排查子 Agent"）——cow-investigator 在真实模型真实任务中自然发生。**守卫线上验证通过**：复跑不再 400 级联，follow-up 正常。评测脚本本轮改动（write-confirm 并发轮询审批流程，修复同步等待超时）一并入库；证据：服务器侧 `docs/evidence/live_model_eval.json` + 探针记录，文档「真实模型线上评测」一节。
24. **受控数据读写入口：大结果回读 + 业务范围长期记忆（2026-09-27，cow-agent，私有分支）**：权限收紧（read_file 等通用工具关闭）后补两个缺口，全部 app 层实现（`app/agent_io.py`），bear/ 母版零改动。**缺口一**：母版大结果持久化（>30KB 落盘 tool-results/、上下文只留预览）原指引模型"用 read_file 回读"已不可达——新增 `read_tool_result`（只读自动放行）：文件名白名单 + `..`/绝对路径/符号链接逃逸拒绝（resolve 后必须落在目录内）+ 单页 100KB 分页（页边界不截断 UTF-8）+ 目录缺失友好错误；`app/patch.py` 运行期包装 `_persist_large_result` 仅替换引导句文案（read_file → read_tool_result）。**缺口二**：业务范围长期记忆 `.bear/cow-memory/<scope>.json`——`memory_note`（写）与 create_work_order 走同一 confirm 审批通道（patch.py COW_WRITE_TOOLS），但属本地文件写故不注册 admin PENDING_ACTION；scope 白名单仅 COW-<数字>/farm（天然免疫路径逃逸），append-only 原子写，单条 2000 字符/单 scope 200 条上限，记录来源 session_id（ContextVar 注入）；`memory_recall`（只读）关键词命中 + 时间倒序，scope 隔离。子 Agent 只继承两个只读入口。测试 `tests/test_agent_io.py` 16 例（回读边界、写→确认→落库→召回、确认拒绝不落库、越权 scope 拒绝）；cow-agent pytest **52→68 项全绿**，run_agent_evals 复跑 exit=0；文档补「受控数据读写入口」一节。

25. **反馈学习链路：对话纠正 → 方法提炼 → 评测门 → 人工确认 → 复用验证（2026-09-27，cow-agent，私有分支）**：补齐评审指出的缺口——此前只有"人直接提交 lesson"，没有验证模型从对话反馈中提炼方法的能力，也没有新旧版本固定任务对比与新会话复用验证。全部 app 层实现（`app/feedback_learning.py`），bear/ 母版零改动。**Extractor**：输入"任务+上轮回答+用户纠正"三元组产出结构化候选（skill_name/lesson/rationale/evidence_refs），LLM client 可注入（`OpenAIChatExtractorClient` 适配真实 OpenAI 兼容 client），无 client 走确定性规则兜底（指令词提取规则句 + BM25 匹配已有领域 skill，命中优先 merge、不匹配才 add），离线可跑；硬约束 evidence_refs 必填且为对话原文逐字片段，LLM 输出非 JSON/缺字段/凭空证据一律拒绝。**Maintainer**：确定性重复度/覆盖面判断给出 add/merge/discard 建议并写入候选记录（`FeedbackLedger.annotate`）。**评测门**：决策 merge 前自动跑固定任务新旧对比——回归集 skill_benchmark 全集（含域外负例）+ 候选自带 1-2 条验证任务做改进证明；门内改动先应用再恢复，champion 版本号仅记录不覆盖使用中 skill；只有 improved 且 no_regression 才进入人工确认，否则自动 discard 写明原因。**复用验证**：merge 后在新会话上下文（清缓存无历史）断言检索命中且注入内容含新规则，产出 reuse_verified。端到端演示 `scripts/demo_feedback_learning.py`（离线确定性，规则兜底零 LLM 调用）：「日报没区分观察事实与待复核推断」纠正走通全链路（人工确认版本+1=champion 0.1.1、快照齐全、reuse_verified），退化候选被评测门拦截自动 discard 且 skill 文件逐字节不变，8 步证据 `docs/evidence/feedback_learning_demo.json` + agent-home 整树指纹零污染校验；新增 `tests/test_feedback_learning.py` 11 例，cow-agent pytest **68→79 项全绿**，run_agent_evals 复跑 exit=0；文档补「反馈学习链路」一节。

26. **长程任务折叠对照实验：普通摘要 vs 结构化三段式（2026-09-28，cow-agent，私有分支）**：补齐评审缺口——长程任务的验收应是"折叠后还能把任务做完"，且需同任务对比普通摘要与结构化折叠的完成率/关键状态保留/重复无效调用/Token 消耗。侦察结论：母版折叠产物本身已是结构化三段式（episode/working/tool memory，LLM side_query 生成，失败退化为 `fallback_folded_memory` 纯文本摘要），故不做运行时改动，直接用母版结构做对照——普通摘要 = 母版 fallback 真实退化路径，结构化 = 同 schema 确定性离线替身（经母版 parse/format 链路校验）。实验（`app/longtask_fold.py` + `scripts/demo_longtask_fold.py`，离线确定性可复跑）：10 头牛逐头排查（档案+近 30 天事件），第 6 头注入工具失败（days=30 超时），任务中段强制折叠一次，折叠后仅凭折叠产物续跑到产出汇总报告，两模式共用同一确定性续跑算法。**真实数字**：任务完成率两模式 10/10 打平；关键状态保留——目标牛清单 10/10 打平、已完成牛结构化 5/5 vs 普通摘要 1/5（中段 4 条完成记录被 6000 字符裁剪丢弃）、失败牛与失败参数均保留；重复无效调用结构化 0 vs 普通摘要 1（无派生规则→原参数重发再超时），另有冗余重查 0 vs 8；折叠后 Token 总消耗（estimate_tokens 离线估算，工程回归指标）4,986 vs 9,505。4 项断言全过，证据 `docs/evidence/longtask_fold_demo.json`（含折叠点前后 transcript 快照与两模式折叠产物全文）；新增 `tests/test_longtask_fold.py` 7 例，cow-agent pytest **79→86 项全绿**，run_agent_evals 复跑 exit=0，已有 demo 脚本不受影响；文档补「长程任务折叠对照」一节。

27. **环境遥测与设备维护知识接入闭环（2026-09-28，私有分支 `private/env-telemetry`，AutoDL 在线验收 19/19）**：按《9.28升级》手册定稿链路落地——**cow-edge**：simulator 新增 `ENV_TELEMETRY`（温/湿度，`metric/value/unit/quality/threshold_version` 放 `raw`，不改 UnifiedEvent 主表契约，复用 `farm/+/event` 统一入口，不新增 topic）；**cow-admin**：事件类型白名单受理+event_id 幂等不变、遥测只落库不写 twin_state、`EnvThresholdRule`（演示阈值 env-demo-v1：温度 ≤28/28-30/>30，湿度 ≤70/70-80/>80，文档注明"未现场校准"）单一来源、WARNING/ALERT 落 ENV_ALERT、ALERT 经 24h 收敛生成 HIGH 维修工单（含 source_event_id 溯源）、新增只读接口 `GET /api/v1/env/telemetry/latest?barnId=`（items+active_alerts）；**cow-ai**：3 份规程 Markdown（名称/版本/生效日期/适用设备/阈值/步骤/禁止操作/人工确认项）章节切片+bge-small-zh+Chroma，`POST /api/v1/env/advice` 带 source_id 锚点出处（不伪造页码）、低分拒答（MIN_SIMILARITY=0.55 按 bge 实测定标：无关问题基线 0.4463 会误放行 0.35）；**cow-agent**：只读工具 `query_env_telemetry`（HTTP 查 admin，SUSPECT 数据提示，Agent 不自算阈值）+ `env-check` SOP Skill；**cow-web**：牛棚页环境卡片+温湿度趋势（复用现有事件分页接口，零新依赖）。在线验收（真实 DeepSeek 链路，证据 `cow-agent/docs/evidence/env_alert_e2e_20260928.json`）**19/19 PASS**：32℃ 上报→落库→同 event_id 去重→ENV_ALERT+工单（24h 收敛不重复）→迟到 27℃ 不回退→Agent 经 query_env_telemetry 取数→RAG 命中《牛舍温湿度控制规程》env-sop-v1.2（0.717）→PENDING_ACTION→确认建单→X-Action-Id 重放 409；域外问题拒答文案逐字一致。测试：admin **63→81**、ai 23、agent **86→90** 全绿。
28. **业务 MCP Server + 9.29 验收证据补齐（2026-09-28/29，私有分支）**：**ranch-operations-mcp**（`cow-agent/mcp_servers/ranch_operations/server.py`，真实 stdio JSON-RPC 子进程）——5 只读工具（query_device_status/query_device_telemetry/query_cow_timeline/query_twin_state/search_maintenance_knowledge，readOnlyHint=true 自动放行，知识检索透传 cow-ai 拒答语义不加工）+ 2 写工具（register_work_order/mark_device_for_inspection，走 Runtime 确认→PENDING_ACTION→X-Action-Id→exactly-once 全链复用，**审批逻辑零复制**，职责边界：server 只做 schema/参数/转发/规范化）；在线冒烟 4/4 PASS（tools/list 发现 7 工具、遥测实查 32℃/ALERT、规程检索命中 env-sop-v1.2、建单 208→209+重放 409）；agent pytest **90→108** 全绿。**9.29 补证**（证据 `env_929_gaps_20260929.json`，24 项）：**C** MCP 路径 e2e——真实模型**零引导自主选用** MCP 工具（内置与 MCP 混用 trace），MCP 写工具建单 209→210；**D** 审批凭证四负例全 PASS（无凭证 403/伪造 403/过期 403+TTL 实测 120s/重复 409）；**E** Session 重启续处理同一异常——恢复后记得 32℃/ALERT 上下文，只重查只读遥测、**无重复写动作**；**F** 遥测断网缓存——**曾发现真实缺口**（env 模式直接 publish 不走 wal_buffer），修复为复用 online 模式同一缓存表+补传路径后重测 PASS（断网缓存 2 条零丢失、恢复 FLUSHED=2、全表 event_id 重复行=0，原始 FAIL 痕迹保留于证据）。**RAG 评测口径补齐**：`/env/advice` 新增 device_type/document_version 显式过滤（指定版本可命中旧版存档）；固定评测集 26 条六类分层（标准/口语/设备过滤/版本过滤/近义干扰/域外），真实 bge 跑分（`cow-ai/docs/评测报告_环境规程RAG_20260929.md`）：Top-1 0.778 / Top-3 1.000 / MRR 0.972 / 域外拒答 1.0；**近义干扰误放行 0.5 如实记录 badcase**（bge 中文基线相似度偏高，0.55 阈值对主题近邻分辨不足，改进方向已记录，不调阈值凑数）。

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
mvn -s tools/settings.xml package                     # cow-admin（含 81 项单测）
cow-agent/.venv/Scripts/python -m pytest tests/       # 108 项
cow-ai/.venv/Scripts/python -m pytest tests/          # 26 项（含环境规程 RAG）
npm run build                                         # cow-web
# 验收
tools/pw-venv/Scripts/python acceptance/cow_d1_main.py           # 浏览器主链路 15 项
tools/pw-venv/Scripts/python acceptance/cow_d2_agent_confirm.py  # 写操作确认机制 7 项
tools/pw-venv/Scripts/python acceptance/cow_env_alert_e2e.py     # 环境遥测闭环在线 19 项
tools/pw-venv/Scripts/python acceptance/cow_929_gaps.py          # 9.29 补证（MCP e2e/凭证四负例/Session 续处理/遥测断网补传）24 项
# 断网演示
cow-edge/.venv/Scripts/python simulator.py --mode offline --duration 60 --interval 2
cow-edge/.venv/Scripts/python simulator.py --mode reconnect
```
