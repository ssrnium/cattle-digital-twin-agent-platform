# 面试问答手册：奶牛数字孪生平台 · Agent 工程化设计

所有答案均以仓库真实代码为依据，括注出处。验收口径：admin 单测 43 项全绿、cow-agent pytest 16 项、
浏览器主链路 15/15、写操作确认 7/7（见 `验收报告_20260914.md` / `PROJECT_STATUS.md` / `acceptance/`）。

## 一、设计思路

### 为什么 Agent 只做不确定任务，确定性逻辑全部留在 cow-admin？

系统的职责切分原则是：**确定性归业务系统，不确定性归 Agent**。

- 确定性链路（事件接入幂等去重、孪生状态更新、告警工单生成、状态机流转）全部在 cow-admin 用规则实现：
  `EventIngestService` 固定「schema 校验 → event_id 幂等去重 → 落库 → TwinUpdater + TaskRuleEngine」四步
  （`cow-admin/.../event/service/EventIngestService.java:24-34`）。这些逻辑必须可测试、可复现、可审计，
  用 LLM 做只会引入随机性。
- Agent 负责的是规则覆盖不了的**不确定任务**：事件排查、多源数据交叉分析、SOP 复核、给场长的自然语言汇报。
  这一点直接写进了系统提示词：「平台侧已保证确定性（event_id 幂等去重、工单状态机、乐观锁），
  你负责分析 / 排查 / 建议类不确定任务，不要承诺替人做最终处置决定」
  （`cow-agent/app/cow_agent.py:27-28`）。
- 写操作的最终决定权永远在人：Agent 只能提议 `create_work_order`，真正的执行要过前端审批，
  再由 cow-admin 的确定性代码落库。

这样拆的好处：Agent 幻觉最坏的结果是"一条建议没被采纳"，而不是"业务数据被改坏"。

## 二、技术选型

### 为什么用 MQTT 而不是 Kafka？

- 场景是**边缘设备上行**：摄像头/边缘节点→服务端的小包高频事件流，MQTT 是为弱网、低带宽、
  设备侧发布订阅设计的物联网标准协议，边缘侧用 Python paho 几行就能发；Kafka 客户端对边缘节点太重。
- 可靠性没有靠 broker 堆，而是**在边缘侧自己做**：断网时事件写本地 SQLite（wal_buffer），恢复后按
  HIGH/LOW 优先级补传，服务端确认成功才删本地记录（`cow-edge/simulator.py`，README「断网恢复机制」）。
  这套机制 72 小时离线缓存是验收标准之一，Kafka 解决不了"边缘节点本身离线"的问题。
- 服务端的最终一致性防线是 `unified_event.event_id` 数据库唯一约束幂等去重
  （`schema.sql:91`，`EventIngestService.java:58-64`），不依赖消息队列的 exactly-once 语义。

### 为什么用 FastAPI 包装 BearCode Agent Runtime？

- Runtime 是自研 Python 代码（`cow-agent/bear/agents/`），异步 agent loop 与 FastAPI 的 asyncio 模型天然契合——
  写操作确认 park 用的就是 `asyncio.Future`（`agent_manager.py:87-100`），换成同步框架这件事会很别扭。
- FastAPI 只承担薄壳职责：三个端点（`/chat`、`/confirm`、`/sessions`）+ 启动 lifespan
  （`cow-agent/app/main.py`），业务复杂度全部在 Runtime 和领域工具层。
- 与 cow-ai（同为 FastAPI）技术栈一致，团队维护成本低；OpenAI 兼容协议接 LLM，DeepSeek / Kimi 可切换
  （`cow-agent/app/config.py:11-13`）。

### 为什么是 per-session Agent 实例池，而不是全局单例或无状态重建？

- Agent 实例持有会话上下文（消息历史、记忆），且**非并发安全**——多请求并发进同一个实例会污染上下文。
  所以 `AgentManager` 每个 session 一个实例 + 每实例一把 `asyncio.Lock` 串行化
  （`cow-agent/app/agent_manager.py:1-7、53-69`）。
- 不做无状态重建的原因：多轮对话（"它今天什么情况" → "那要不要安排配种"）依赖连续上下文，
  每轮重建会丢失 Memory 与 Skills 命中状态，且重建成本高。
- 写操作确认 park 也依赖实例常驻：chat 请求阻塞等待 Future，`/sessions` 把 pending 暴露给前端轮询，
  `/confirm` 放行后同一实例继续执行（`agent_manager.py:71-100`）。

## 三、常见追问 10 问

### Q1. Agent 和 workflow（如工单状态机）的区别是什么？为什么不让 Agent 直接驱动流程？

workflow 是**预定义的确定性状态迁移**：`WorkOrderService.TRANSITIONS` 写死
`NEW → DISPATCHED → PROCESSING → PENDING_REVIEW → CLOSED`，非法流转直接报错，并发用乐观锁
（README「工单状态机与并发控制」）。Agent 是**运行时才决定下一步做什么**的推理循环：
看数据 → 想 → 选工具 → 再看结果 → 再想。前者保证"流程不可能走错"，后者解决"事先写不出规则的问题"。
本项目里两者是协作关系：Agent 通过 `create_work_order` 把单子**送进**状态机入口（NEW），
之后的流转完全由 workflow 接管，Agent 不参与。

### Q2. 为什么需要 LLM，用规则引擎不行吗？

规则引擎已经在用了——告警收敛、工单触发就是 TaskRuleEngine 做的。但有三类事规则做不了：

1. **开放式问答**："COW-0042 今天什么情况"需要动态组合档案/事件/时间线三个数据源再组织成自然语言，
   查询组合是开放的，没法枚举成规则。
2. **SOP 情景推理**：mounting-review 要求对照 21 天发情周期、置信度、历史配种记录综合判断
   "疑似发情成立 / 证据不足 / 疑似误报"（`mounting-review/SKILL.md`），这是带权衡的推理，不是 if-else。
3. **自然语言交互与汇报**：面向场长/兽医/繁育员三种角色的表达（report-style SOP）。

反过来，LLM 做不了规则做的事：幂等去重、状态机、乐观锁这些确定性保障交给 LLM 就是事故。
所以是"规则管确定性，LLM 管不确定性"，不是二选一。

### Q3. Tool 调用失败了怎么办？

分层兜底，任何一层失败都不会让 Agent 进程崩溃或向用户抛堆栈：

- **连接层**：httpx 超时 10s；连不上 cow-admin 返回「无法连接 cow-admin」友好错误
  （`cow_tools.py:24、67-68`）；service 账号 401 自动重登重试一次（`cow_tools.py:69-71`）。
- **工具层**：业务错误包装成 `ToolError`，`execute()` 统一 catch 后把 `"Error: ..."` **字符串返回给模型**，
  任何未预期异常兜底「Error: 工具执行异常」，绝不抛穿 agent loop（`cow_tools.py:182-194`）。
  模型拿到错误字符串后可以自行换参数重试或如实告知用户。
- **服务层**：cow-agent 整体异常 → HTTP 502「智能体调用失败」（`main.py:57-59`）；
  cow-agent 宕机时 admin 侧降级为 `BizException(502)`，该路径有单测覆盖
  （`AgentServiceClient.java:48、61`，`AgentServiceClientTest.java:73-77`）。

### Q4. 数字孪生模型是怎么设计的？

核心取舍是**"快照 + 时间线"分离**：

- **快照** `twin_state`：一牛一行，JSONB `state` 存 `posture/zone/health_status/estrus_status`，
  带 `state_nature`（MEASURED/INFERRED/MANUAL 标明状态来源可信度）、`source_event_id`（可回溯到触发事件）、
  `version` 乐观锁（`schema.sql:76-84`，`TwinState.java`）。
- **时间线** `cow_timeline`：每个牛只相关事件都追加一条，存 confidence、evidence_ref 等明细，
  回答"为什么现在是这样"（`TwinUpdater.appendTimeline`，`TwinUpdater.java:126-143`）。
- **更新规则**：MOUNTING 高置信（≥0.8）→ `estrus_status=SUSPECTED_HEAT`；LAMENESS → `health_status=LAMENESS_RISK`；
  设备事件不动牛只状态（`TwinUpdater.java:20-28`）。
- **乱序处理**：迟到事件（`event_time` 早于快照对应的事件时间）只追加时间线、不回退快照
  （`TwinUpdater.java:73-79`）——断网补传场景下旧事件不能覆盖实时状态。这是事件驱动孪生的经典坑，
  用"event_time 比较 + 只追加"解决，代价是时间线可能与快照短暂不一致，但快照永远反映最新已知状态。

### Q5. 如何保证 Agent 可控、不会乱改业务数据？

四道防线，层层独立：

1. **权限分级**：7 个领域工具里 6 个只读自动放行，唯一写工具 `create_work_order` 被 patch 进
   confirm 流程（`patch.py:61-75`）——即使模型想直接调，Runtime 也会拦截。
2. **人工确认闭环**：写操作 park 到 `asyncio.Future`，前端展示工具名/参数/理由，批准才执行；
   120 秒未审批自动拒绝（`agent_manager.py:87-100`，`config.py:24`）。验收实测 7/7。
3. **最小权限账号**：Agent 回调业务系统走 `svc-agent` service 账号，仅有业务查询和手工建单权限，
   没有系统管理权限（README「默认账号」）；即使 Agent 完全被攻破，能做的事也有限。
4. **全链路审计**：所有对话经 cow-admin 代理，user/assistant 消息、token 用量落 `agent_session` /
   `agent_message`（`AgentController.java:46-63`）；审批动作本身带 `@OperLog` 操作日志
   （`AgentController.java:69`）。事后可完整回溯"谁、什么时候、批了什么"。

### Q6. 确认等待期间 chat 请求一直阻塞，会不会把连接挂死？超时怎么配合？

会有长连接，这是刻意设计：chat 请求阻塞等待确认，前端同时轮询 `/sessions` 拿 `pending_confirmation`
弹审批框（`agent_manager.py:121-136`）。超时链条是配平的：confirm park 120s（`config.py:24`）<
admin RestClient read 超时 150s（`AgentServiceClient.java:25`），所以正常路径下一定是 agent 先返回
（批准执行完 or 超时自动拒绝），admin 不会先断。超时拒绝后工具结果回写模型，Agent 继续生成
"操作已取消，建议是……"的文字回复，会话不受影响（真实日志：park 15:47:41.996 → 自动拒绝
15:49:41.996，恰好 120s，见 `docs/agent_trace.md`）。

### Q7. 多用户同时用 AI 助手，会话怎么隔离？

per-session 实例池：每个 session_id 一个独立 Agent 实例 + 一把 `asyncio.Lock`，同一会话的请求串行、
不同会话完全并行（`agent_manager.py:36-69`）。审计侧 admin 按 session_id 落库且有唯一约束
（`schema.sql:152`），sessionId 为空时由 admin 预生成 UUID 前 12 位传给 cow-agent，避免审计表冲突
（`AgentController.java:92-97`）。代价是内存随活跃会话数增长——目前 MVP 单棚场景可接受，
扩容方向是实例池加 LRU 淘汰 + 会话持久化恢复（Runtime 已有 `save_session` / 记忆折叠能力）。

### Q8. Agent 的回答怎么防止"编数据"？

三层措施：

1. **提示词约束**：工作准则第 1、2 条——"先查数据再下结论，禁止凭空编造数据；结论必须引用具体
   cow_id 与 event_id"（`cow_agent.py:19-22`）。
2. **工具结果即证据**：所有数据类回答的素材来自工具回调的真实 REST 响应，且 `CowAgent` 把每轮
   工具调用的名称/参数/结果预览记入 `tool_trace` 随响应返回，前端可折叠展示取数过程
   （`cow_agent.py:50-61`）——用户能直接看到 Agent 查了哪几张表。
3. **不确定就说不知道**：准则第 3 条要求说明缺什么数据、用哪个工具补查（`cow_agent.py:22-23`），
   把"诚实"写进系统提示词而不是依赖模型自觉。

### Q9. 上下文变长了怎么办？LLM 的 tool_call_id 兼容性问题怎么处理？

- Runtime 支持上下文压缩：`_check_and_compact` 在上下文将满时自动折叠会话记忆
  （`bear/agents/agent.py:847-858`，`bear/agents/session_memory.py`），模型侧也有 `compact_context`
  工具可主动触发；轮次上限 `AGENT_MAX_TURNS=12` 兜底（`config.py:14`）。
- 实战中遇到过一个真实兼容性问题：DeepSeek V4.1 Flash 在并行/多轮工具调用时复用 `tool_call_id`，
  下一轮请求被 400 拒绝。修复方式是在每次发请求前把历史消息里的调用/结果 id 成对重写为全新唯一值
  （`patch.py:80-134`）——这些 id 只在单次请求内起配对作用，重写不影响跨轮语义。
  这是"Runtime 自研"的复利：问题出在协议适配层，自己掌控代码才能精准 patch。

### Q10. 如果要把这套 Agent 能力复制到别的业务（比如设备预测性维护），要改什么？

领域层与 Runtime 层是分离的，复制成本集中在三块：

1. **工具层**：新增领域工具 = 在 `TOOL_DEFS` 加 schema + `TOOL_HANDLERS` 加 httpx 回调
   （`cow_tools.py`），写工具加进 `WRITE_TOOLS` 即自动获得确认拦截。
2. **SOP 层**：在 `agent-home/.bear/skills/` 下放新的 SKILL.md（frontmatter 声明 name/description/
   when_to_use），系统提示词里登记一句即可。
3. **提示词层**：换 `SYSTEM_PROMPT` 的场景描述与工作准则。

Runtime 本身（agent loop、权限检查、confirm park、memory、审计链路）零改动。
mounting-review / lameness-check / device-offline / report-style 四个 SOP 已经验证了这个扩展模式。
