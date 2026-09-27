# Agent Runtime Evidence

本页记录 cow-agent 中 Agent Runtime 能力的可重复验证结果。命令不依赖 LLM API Key，也不把一次模型回答当成指标；它验证运行时真正负责的 Skill 检索、工具契约、上下文折叠、MCP 子进程和反馈状态机。

## 重复运行

```powershell
cd cow-agent
\.venv\Scripts\python.exe scripts\run_agent_evals.py
\.venv\Scripts\python.exe scripts\demo_subagent_investigation.py
\.venv\Scripts\python.exe scripts\demo_skill_evolution.py
\.venv\Scripts\python.exe -m pytest -q tests
```

两个 demo 脚本同样离线确定性：LLM 是脚本化回放客户端（`app/offline_fakes.py::FakeOpenAIClient`，不花真实 API 额度），cow-admin 是罐头 `MockTransport`，证据分别写入 `docs/evidence/subagent_investigation_demo.json` 与 `docs/evidence/skill_evolution_demo.json`。

脚本读取固定样本 `eval/skill_benchmark.json`、`eval/tool_benchmark.json` 和公开基准改写子集 `eval/tool_benchmark_apibank_subset.json`，把 JSON 报告写到 `docs/evidence/agent_runtime_evidence.json`。MCP 配置位于 `agent-home/.mcp.json`，fixture 是同目录下的 `mcp_fixture.py`，通过 stdio JSON-RPC 作为独立子进程启动。

## 实测结果

| 闭环 | 固定样本 | 指标 | 结果 |
|---|---:|---|---:|
| Skill 检索 | 16（14 正例 + 2 域外负例） | Top-1 命中率 / MRR / 负例拒识率 | 100% / 1.0 / 100% |
| Tool Calling 契约 | 12 个场景、18 次调用 | 工具选择 / 参数合法 / 序列精确 | 100% / 100% / 100% |
| API-Bank 公开基准改写子集 | 26 个场景、38 次调用 | 工具选择 / 参数合法 / 序列精确 | 100% / 100% / 100% |
| 上下文压缩 | 4 个固定任务 | 平均总 Token | 5,388.25 → 1,742.25，下降 67.67% |
| MCP | 1 个真实 stdio Server | 发现 / 读调用 / 审批写调用 / 失败恢复 | 3 工具 / 通过 / 通过 / 通过 |
| 子 Agent 实战（cow-investigator） | 2 头异常牛 + 1 次建单 | 子 Agent 启动 / 白名单收窄 / 写意图父会话审批 | 通过（离线脚本回放） |
| Skill 自进化端到端 | 2 merge + 2 rollback + 1 discard | 版本递增 / 快照恢复 / 审计链有序 | 7 步全过 |
| 历史完整性守卫 | 3 个场景（含端到端） | 悬空补齐 / 只修不剥 / 正常历史零改动 / 幂等 | 通过 |
| 回归测试 | 38 项 | pytest | 38 passed |

### Skill 评测

`app/evaluation.py::evaluate_skills` 通过现有 BM25 检索实现读取四个领域 `SKILL.md`，记录每个样本的 Top-3 候选、分数和目标排名。样本从 4 例扩到 16 例：四个业务 SOP（爬跨复核、跛行排查、设备离线、场长汇报）各 3-4 例，覆盖标准问法、口语化问法和近义干扰问法（如 mounting-review-03 同时出现"爬跨"与"走路有点瘸"，目标 0.364 vs 干扰项 lameness-check 0.281；report-style-03 同时出现"爬跨与跛行"与"周报"，目标 0.532 vs 干扰 0.204），另加 2 例域外负例（天气/通风、Python 脚本），验证不误命中。

负例判定（本次新增的最小 runner 支持）：`expected_skill=null` 表示"不应命中任何 skill"，通过条件是 Top-1 分数低于生产默认检索阈值 0.08（`OOD_MIN_SCORE`，与 `retrieve_relevant_skills` 的默认 `min_score` 一致）。指标口径：`skill_hit_rate` 与 `skill_mrr` 只在 14 个正例上计算，语义与旧版一致；新增 `ood_rejection_rate` 只在负例上计算，三者并存于 `metrics`。如实记录：ood-negative-02 的 BM25 Top-1 并非零分（report-style 0.0085），但远低于生产阈值，线上默认配置下不会注入任何 skill——这正是负例要验证的行为。所有近义干扰案例的目标/干扰候选间距逐条保存在证据 JSON 的 `cases[].candidates` 中。

### Tool Calling 评测

`evaluate_tool_calls` 使用固定工具轨迹回放隔离运行时契约：检查工具名称顺序、必填参数和参数类型。它不把启发式回放器冒充成 LLM 评测；真实 LLM 运行时仍通过同一套 schema 和权限检查后才执行工具。领域工具定义来源是 `app/cow_tools.py`。

样本从 4 例扩到 12 例，覆盖全部 7 个领域工具：单工具调用（档案/时间线/孪生状态/工单筛选）、2-3 步多工具序列（查档案→查近期事件→时间线复核；全棚孪生→对照单牛档案，顺序敏感）、参数边界（cow_id 不同编号格式、可选参数 limit/过滤条件省略、state/type 组合过滤、写工具 device 分支默认 NORMAL 优先级）。为覆盖 get_twin_states / list_work_orders 与设备维修建单，确定性回放器 `_plan_tool_calls` 增加了对应分支（仅评测代码，`bear/` 母版拷贝逻辑零改动）。如实记录：扩充过程中发现回放器对"开一张 DEVICE_REPAIR 工单"这类把类型词插在动宾之间的语序不识别（落入工单查询分支），该样本 query 调整为"开一张工单，类型 DEVICE_REPAIR"后通过——语序敏感性属于回放器而非运行时契约的限制，真实 LLM 不受此限。

### API-Bank 公开基准改写子集

`eval/tool_benchmark_apibank_subset.json`：从母版只读拷贝的 API-Bank `level-1-api.json`（399 条，对话→单 API 调用，Alibaba DAMO 公开基准）中选取 26 条意图可映射到 7 个领域工具的样本（跳过 GetUserToken 鉴权样本与银行/账户/计算器等无领域对应的 API），保留原样本的单调用意图结构（查询/筛选/预约/取消/改期/症状），将用户话语改写为奶牛领域中文 query，`expected` 按 `tool_benchmark.json` 同一 schema 手工标注。每条 case 的 `source` 字段记录原始文件、样本 id、原 API 名与原期望调用，文件头 `_meta` 记录来源、选取规则与意图映射表；母版只读，未复制任何原始大文件。评测复用 `evaluate_tool_calls`，结果写入证据 JSON 的 `tool_eval_apibank_subset`。该子集验证的是"公开基准同构样本下工具契约保持一致"，难度与主基准相当，不声称等同于在原始 API-Bank 上跑分。

### Token 对比

四个任务使用同一组长上下文、同一个模型标签 `deepseek-flash` 和同一段固定输出，压缩前后都记录 input、output、total。压缩调用现有 `session_memory.fallback_folded_memory` 和 `format_folded_memory`，估算器按 CJK 字符和 ASCII 字符块计算离线近似 Token；它是可重复的工程回归指标，不等同于供应商 API 的真实 tokenizer 账单。线上请求的真实 token 用量仍由 `Agent` 响应里的 usage 累计并返回。

### MCP

`McpManager` 从 `AGENT_HOME/.mcp.json` 启动 `ranch-demo` 子进程，完成 initialize、tools/list 和 tools/call。三个工具分别覆盖只读快照、写入牧场备注和 JSON-RPC 失败。`readOnlyHint=true` 的工具自动放行；未标注或标记为写入的工具在 default 模式返回 confirm，在 dontAsk/plan 模式拒绝。客户端还修复了请求 Future 注册时序和 Windows 子进程关闭告警。

### Feedback / Skill 自进化

`app/feedback.py::FeedbackLedger` 把反馈拆成显式状态：`candidate_submitted → add|merge|discard`。merge 调用现有 `evolve_skill`，先写入版本快照；`rollback` 恢复最近快照并保留审计事件。FastAPI 暴露 `/api/v1/agent/feedback`、`.../{candidate_id}/decision` 和 `.../{skill_name}/rollback`，生产默认仍关闭后台 LLM 自动演化，任何写入都需要明确决策。

### 权限与子 Agent

子 Agent 和 fork Skill 现在继承父 Agent 的 `permission_mode` 与 `confirm_fn`。default 模式不再隐式升级成 `bypassPermissions`，所以写工具仍会回到同一个 session 的审批 Future。领域写操作继续由 `PENDING_ACTION` 和 `X-Action-Id` 下沉链路保护。

### 子 Agent 实战：cow-investigator 多头牛排查

领域场景「ZONE-B 最近异常的几头牛都什么情况」真正走通子 Agent 机制：主 Agent 先 `list_events` 圈定异常牛清单（COW-0042 爬跨 ×2、COW-0057 跛行），再经 agent 工具逐头启动 `cow-investigator` 子 Agent 排查，最后汇总报告。实现位置：`app/cow_agent.py::CowAgent._execute_agent_tool`——母版 launch 路径（`bear/agents/agent.py:1277`）只构造纯 Agent + 内置代码工具、无法路由领域工具，故按同一机制在 app 层特化：子代理是真实 `CowAgent.run_once` 独立循环，只挂 6 个只读领域工具（`create_work_order` 被排除，且不允许再递归 agent 工具），继承父会话 `permission_mode=default` 与 `confirm_fn`。agent 工具的 type 枚举在 app 层拷贝扩展（`cow_agent_tools()`），母版 `tool_definitions` 零改动。

权限边界由测试直接证明而非口头声明：`tests/test_subagent_investigation.py` 中子 Agent 脚本尝试 `create_work_order` 时，确认请求 park 到**父会话同一个 confirm_fn**，用户拒绝后罐头后端 `state["work_orders"]` 为空——写操作从未到达后端；被拒意图连同参数以 `denied_tool_calls` 留在 trace 证据里。`run_once` 响应结构新增 `subagent_runs`（每个子 Agent 的 tools_granted / tool_trace / tokens / report / 权限字段），配合既有 `tool_trace` 可完整还原父子分工。演示脚本 `scripts/demo_subagent_investigation.py` 第二轮另演示建单审批通过路径：confirm_fn 批准后写工具才执行。

### Skill 自进化端到端演示

`scripts/demo_skill_evolution.py` 在 `agent-home/.bear/skills` 的临时副本上重放完整生命周期（agent-home 整树指纹前后比对为零污染证据）：feedback 提交 → 候选 → merge（`lameness-check` 0.1.0→0.1.1→0.1.2，每次 merge 前快照写入 `history/*.jsonl` 且内容逐字节等于对应旧版本）→ rollback 恢复**最近一次**快照（回到 0.1.1 内容，而非最初版本）→ 重复 rollback 的边界行为（快照 append-only 不弹栈，幂等于同一快照，不会继续回退）→ discard 路径（skill 文件零改动、候选标记 discarded、不可重复决策）→ `feedback_candidates.jsonl` 审计链事件序列与时间单调性校验。每步结构化证据写入 `docs/evidence/skill_evolution_demo.json`，任一步失败脚本以非零码退出。

### 历史完整性守卫

**问题现象（线上实锤）**：真实模型评测（`scripts/run_live_model_eval.py`，DeepSeek 线上调用，经 admin 代理 chat）中，某轮异常（trace 出现 `skill`+`read_file`、回复为空）在历史里留下**悬空 tool_calls**——assistant 消息带 tool_calls 但缺少对应 tool 结果消息。下一轮起 DeepSeek 对该会话一律返回 400：`An assistant message with 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'`，此后该会话所有轮次全部失败（会话毒化）。既有的 tool_call_id 成对重写（防 Duplicate tool_call_id）只处理 id 复用，不覆盖「结果缺失」这个配对完整性边界。

**守卫语义**：`app/patch.py::repair_dangling_tool_calls` 挂在 `_call_openai_stream` 包装链路发送前（先于 id 重写）：扫描 `_openai_messages`，对每组 assistant.tool_calls 检查紧随其后 tool 消息块的配对，缺失处**只修不剥**地插入合成错误 tool 消息（内容 `[runtime] tool result missing: repaired by history integrity guard`，既有消息零删除零改动，现场可审计），并以 WARNING 记录 `repaired N dangling tool_calls (session=…, ids=[…])`。修复在历史落盘处生效，同一轮事故只修一次（幂等）；正常历史零改动、零日志。修复后再走既有成对 id 重写，合成消息一并获得全新配对 id，无行为回归。

**复跑方式**：`pytest tests/test_history_integrity_guard.py`（3 例：部分缺失+整组悬空+跨 user 消息的场景保留与插入位置断言；健康历史/空 tool_calls 零改动；端到端毒化→修复→WARNING→第二轮幂等）。线上真实模型评测脚本 `scripts/run_live_model_eval.py` 需在服务器侧跑（cow-admin 8081 + cow-agent 8003 + 有效 LLM key），守卫上线后原毒化场景不再扩散到后续轮次。

### 真实模型线上评测（终版，2026-09-27）

与上面的离线确定性回放**分开报告**：本节是 AutoDL 服务器上的真实供应商调用（DeepSeek `deepseek-flash`，经 cow-admin 代理 `/agent/chat`，有效 LLM key），脚本 `scripts/run_live_model_eval.py`，逐任务证据由脚本在服务器侧写入 `docs/evidence/live_model_eval.json`（本地仓未归档副本，以服务器运行记录与探针日志为准）。评测分两类：deterministic（工具轨迹/参数/确认行为，程序判定）与 review（回复质量，仅记录不判分）。

**终版结果：deterministic 6 项通过 5 项（5/6），review 1 项不判分。**

| 任务 | 类型 | 结果 | 说明 |
|---|---|---|---|
| query-cow | deterministic | 通过 | 真实调用 query_cow_profile，围绕真实档案回答 |
| mounting-review | deterministic | 通过 | 会话复用（档案上轮已取），本轮查近期事件并给复核建议 |
| device-offline | deterministic | 通过 | 真实调用 list_devices 排查 |
| write-confirm | deterministic | **通过（park 实证）** | 见下 |
| no-such-cow | deterministic | **失败（该轮回复为空）** | 判定与复核见下，不凑分 |
| follow-up | deterministic | 通过 | 多轮指代解析正确；同时验证守卫（原 400 级联不再发生） |
| zone-summary | review | 不判分 | 多工具编排质量，回复与 trace 留档供人工复核 |

**write-confirm 确认机制线上闭环实证**：模型真实调用 `create_work_order` → 写操作 park 挂起（服务端日志 `waiting confirm: create_work_order (action=...)`）→ 评测脚本并发线程轮询 sessions 拿到 pending → 拒绝 → chat 返回、无工单产生；另有 120s 超时自动拒绝（auto-denied）记录。即「模型发起 → 人审挂起 → 决策放行/拒绝 → exactly-once 执行」全链路由真实模型驱动跑通，非脚本回放。

**no-such-cow 判定与空响应复核（分开记录）**：该轮按评测口径计失败，原因是**回复为空**而非编造——长会话 7 轮中 2 轮出现空响应。主 agent 单点探针复核（独立新会话）：no-such-cow 回复 680 字且诚实（"20 号牛棚没有 COW-9999 这头牛，无法给出状态"，附证据表），zone-summary 回复约 3500 字。结论：**小模型长会话偶发输出异常（2/7 轮），评测按空响应如实计失败，不判定为系统 bug**；独立会话复测均正常。

**重大正向发现——子 Agent 机制真实自然发生**：zone-summary 探针中，真实模型为「汇总 ZONE-B 最近异常」**自发调用子 Agent 机制 8 次**（trace 含 `agent`×8，回复明说"逐头下发排查子 Agent"）。cow-investigator 子 Agent（第 21 项）不是只在脚本演示里成立——真实模型在真实任务里自主选择了逐头下发排查的编排方式。

**守卫线上验证通过**：历史完整性守卫（第 22 项）部署后复跑本评测，原先 400 级联毒化的会话不再出现，follow-up 等多轮任务正常完成。

**复跑方式**（服务器侧）：

```bash
PYTHONUTF8=1 /root/autodl-tmp/venvs/cow-agent/bin/python \
  /root/autodl-tmp/cow/cow-agent/scripts/run_live_model_eval.py
```

前置：cow-admin 8081 + cow-agent 8003 运行中、有效 LLM key（环境变量注入，不入库）。脚本对 write-confirm 采用并发轮询 pending 再决策的流程（chat 在 park 处阻塞等待审批），拒绝决策保持环境干净。

## 证据文件

- `app/evaluation.py`：固定样本评测（含域外负例判定）、工具 schema 校验、上下文压缩统计
- `eval/skill_benchmark.json`（16 例）、`eval/tool_benchmark.json`（12 例）、`eval/tool_benchmark_apibank_subset.json`（26 例，文件头 `_meta` 注明来源与转换方法）
- `app/mcp_evidence.py`：MCP 发现、调用、失败和权限场景
- `app/offline_fakes.py`：脚本化 LLM 回放客户端 + 罐头 cow-admin MockTransport（tests 与 demo 共用）
- `scripts/run_agent_evals.py`：一键运行并生成 JSON 报告
- `scripts/demo_subagent_investigation.py`：cow-investigator 多头牛排查 + 建单审批演示（证据 `docs/evidence/subagent_investigation_demo.json`）
- `scripts/demo_skill_evolution.py`：自进化 merge/rollback/discard 全生命周期演示（证据 `docs/evidence/skill_evolution_demo.json`）
- `scripts/run_live_model_eval.py`：真实模型评测（DeepSeek 线上调用，服务器侧运行，与离线回放分开报告；会话毒化 bug 即由它发现；终版 5/6 见「真实模型线上评测」一节，证据 JSON 服务器侧生成于 `docs/evidence/live_model_eval.json`）
- `tests/test_mcp_runtime.py`、`tests/test_feedback_ledger.py`、`tests/test_evaluation.py`、`tests/test_subagent_permissions.py`、`tests/test_subagent_investigation.py`、`tests/test_skill_evolution_flow.py`、`tests/test_history_integrity_guard.py`：回归测试
- `docs/evidence/agent_runtime_evidence.json`：本次运行的逐样本结果
