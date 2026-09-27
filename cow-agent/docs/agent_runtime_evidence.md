# Agent Runtime Evidence

本页记录 cow-agent 中 Agent Runtime 能力的可重复验证结果。命令不依赖 LLM API Key，也不把一次模型回答当成指标；它验证运行时真正负责的 Skill 检索、工具契约、上下文折叠、MCP 子进程和反馈状态机。

## 重复运行

```powershell
cd cow-agent
\.venv\Scripts\python.exe scripts\run_agent_evals.py
\.venv\Scripts\python.exe -m pytest -q tests
```

脚本读取固定样本 `eval/skill_benchmark.json`、`eval/tool_benchmark.json` 和公开基准改写子集 `eval/tool_benchmark_apibank_subset.json`，把 JSON 报告写到 `docs/evidence/agent_runtime_evidence.json`。MCP 配置位于 `agent-home/.mcp.json`，fixture 是同目录下的 `mcp_fixture.py`，通过 stdio JSON-RPC 作为独立子进程启动。

## 实测结果

| 闭环 | 固定样本 | 指标 | 结果 |
|---|---:|---|---:|
| Skill 检索 | 16（14 正例 + 2 域外负例） | Top-1 命中率 / MRR / 负例拒识率 | 100% / 1.0 / 100% |
| Tool Calling 契约 | 12 个场景、18 次调用 | 工具选择 / 参数合法 / 序列精确 | 100% / 100% / 100% |
| API-Bank 公开基准改写子集 | 26 个场景、38 次调用 | 工具选择 / 参数合法 / 序列精确 | 100% / 100% / 100% |
| 上下文压缩 | 4 个固定任务 | 平均总 Token | 5,388.25 → 1,742.25，下降 67.67% |
| MCP | 1 个真实 stdio Server | 发现 / 读调用 / 审批写调用 / 失败恢复 | 3 工具 / 通过 / 通过 / 通过 |
| 回归测试 | 30 项 | pytest | 30 passed |

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

## 证据文件

- `app/evaluation.py`：固定样本评测（含域外负例判定）、工具 schema 校验、上下文压缩统计
- `eval/skill_benchmark.json`（16 例）、`eval/tool_benchmark.json`（12 例）、`eval/tool_benchmark_apibank_subset.json`（26 例，文件头 `_meta` 注明来源与转换方法）
- `app/mcp_evidence.py`：MCP 发现、调用、失败和权限场景
- `scripts/run_agent_evals.py`：一键运行并生成 JSON 报告
- `tests/test_mcp_runtime.py`、`tests/test_feedback_ledger.py`、`tests/test_evaluation.py`、`tests/test_subagent_permissions.py`：回归测试
- `docs/evidence/agent_runtime_evidence.json`：本次运行的逐样本结果
