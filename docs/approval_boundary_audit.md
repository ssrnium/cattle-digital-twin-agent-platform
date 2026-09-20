# 智能体写操作审批边界审计（2026-09-20）

> 审计问题：`svc-agent` 是否能够绕过用户确认，直接调用创建工单接口？
> 结论：**能。** 审批关卡当时只存在于 cow-agent 工具层（`confirm_fn` park），cow-admin 不对 `POST /api/v1/tasks` 校验"是否已获用户批准"。本文记录边界事实、现有防线与下沉方案。
> **2026-09-21 更新：下沉方案已实施（见第五节），svc-agent 直连建单已被后端强制拦截（无 X-Action-Id → 403，伪造凭证 → 403，实证见下）。**

## 一、现状事实（代码为据）

| 事实 | 位置 |
| --- | --- |
| 建单接口要求 `task:create` 权限 | `cow-admin/.../task/controller/WorkOrderController.java:37-40`（`@PreAuthorize("hasAuthority('task:create')")`） |
| `svc-agent` 的 SERVICE 角色**含 `task:create`**（设计如此：智能体获批后需用该账号落单；vet/breeder 只有 `task:handle`，普通用户无） | `cow-admin/.../config/DataInitializer.java:69-72` |
| 因此持 svc-agent JWT 直接 `POST /api/v1/tasks` 即可建单，**无需任何批准凭证**；与"获批后执行"的合法调用在 admin 侧无法区分 | 同上 |
| 智能体侧审批关：写工具调用被 `confirm_fn` park 到 `asyncio.Future`，每 session 单 pending，用户批准才放行，120s 超时自动拒绝 | `cow-agent/app/agent_manager.py:48,89-100` |
| 批准动作 exactly-once（agent 层）：Future 只 resolve 一次；已完成/不存在的 pending 再调 `/confirm` 返回 404（验收证据：写操作确认 7/7，超时后 confirm 404） | `cow-agent/app/agent_manager.py:114-115`；`acceptance/cow_d2_agent_confirm.py` |
| 全量审计：对话与审批经 admin 代理落 `agent_session`/`agent_message` 表并绑定发起用户名 | `cow-admin/.../agent/controller/AgentController.java:45-63` |

## 二、今天已经成立的防线

1. **权限面收敛**：全系统只有 admin 与 svc-agent 能建单；vet/breeder/普通用户直接调 `POST /tasks` 返回 403。
2. **agent 层审批闭环**：模型无法自行放行——放行只能来自前端 `/confirm`（需登录用户且持 `agent:chat`）；超时与拒绝都会留下文字建议而非执行。
3. **可追责**：谁在何时问了什么、智能体回了什么、token 用量，全部落库。
4. **批准不重复**：同一 pending 只能被 resolve 一次（超时 404 实证）。

## 三、存在的缺口（如实记录）

1. **审批未下沉**：admin 不校验建单是否携带有效批准。绕过路径 = 拿到 svc-agent JWT 直接调接口。该账号密码目前为演示默认值（README 已标注生产必须更换），风险等级取决于部署形态；本地演示可接受，公网部署不可接受。
2. **admin 层无幂等键**：同一内容重复 `POST /tasks` 会建多张单（网络重试/双击场景）。agent 层 exactly-once 只覆盖"批准动作"，不覆盖"建单动作"。
3. **批准与发起人未在后端绑定**：approve 只认 session_id，admin 不校验"批准人即发起人"（当前批准经 admin 代理转发时已落用户名，具备追溯，但无强制校验）。

## 四、下沉方案（第二轮实施，本文档先行备案）

```text
Agent 决定建单
  → admin 创建 PENDING_ACTION（工具名/参数摘要/发起人/有效期 120s/状态）
  → 前端展示，用户本人 JWT 调 /agent/actions/{id}/approve|reject
  → 后端校验：状态=PENDING 且未过期 且 批准人=发起人 且 参数摘要一致
  → 后端事务内创建工单并标记 action=EXECUTED（action_id 唯一约束 → 天然幂等）
  → 审计落库；拒绝/超时仅留文字建议
svc-agent 直连 POST /tasks 的路径同步收敛：
  方案 A：svc-agent 建单必须携带 EXECUTED 状态的 action_id（外键/唯一），无凭证即 403；
  方案 B：直接收回 SERVICE 角色的 task:create，工单只能经 PENDING_ACTION 由 admin 本人事务创建。
```

配套测试（第二轮）：正常批准/拒绝/120s 超时/非发起人批准 403/重复批准 409/参数被改拒绝/直连无凭证 403/重启后 pending 可查/批准成功响应中断后重试仍一单（exactly-once 业务效果）。

> 口径说明：本审计把"agent 层已有审批"与"后端强制审批"分开陈述。面试表述应为：**审批闭环已在智能体运行时层实现并验收（7/7），后端强制下沉已审计出边界并完成方案设计**——不声称后端已强制。

## 五、下沉实现（2026-09-21 已落地，方案 A 变体）

审批强制点从"cow-agent 工具层"下沉为 **cow-admin 后端强制**：svc-agent 建单必须携带用户本人批准过的 `X-Action-Id` 凭证，同事务内建单并把凭证置 EXECUTED。

### 链路（实现后）

```text
Agent 决定建单 → cow-agent park 前向 admin 注册 PENDING_ACTION（POST /api/v1/agent/actions，
  发起人由 admin 按 agent_session 绑定，svc-agent 无法伪造；注册失败 = fail-closed 直接拒绝该写操作）
  → 前端弹窗，用户本人调 /agent/confirm：admin 先落 PENDING_ACTION 状态
    （批准人=发起人校验 / 过期置 EXPIRED / 条件更新防重复审批 409），再转发 cow-agent 放行；
    转发失败（park 已超时消失）时 APPROVED 凭证补偿作废，不留悬空
  → cow-agent 执行 create_work_order 时携带 X-Action-Id（ContextVar 同 task 透传）
  → WorkOrderController 强制点：SERVICE 角色必须携带凭证；校验 存在/状态=APPROVED/未过期/参数摘要一致，
    同事务内建单 + APPROVED→EXECUTED 条件更新（0 行 = 并发重复 → 409 回滚，exactly-once）
120s 超时：cow-agent 自动拒绝并调 /agent/actions/{id}/expire 同步作废凭证
```

### 落点

| 项 | 位置 |
| --- | --- |
| `pending_action` 表（action_id 唯一约束） | `cow-admin/src/main/resources/db/schema.sql`（启动自动建表） |
| 实体 / Mapper / 注册·审批·校验服务 | `cow-admin/.../modules/agent/{entity/PendingAction, mapper/PendingActionMapper, service/PendingActionService, service/ActionDigest}.java` |
| 注册/作废端点 + confirm 审批下沉 | `cow-admin/.../agent/controller/AgentController.java`（`/agent/actions`、`/agent/actions/{id}/expire`、`/agent/confirm`） |
| **强制点**：SERVICE 角色建单凭证校验 + 事务内 EXECUTED | `cow-admin/.../task/controller/WorkOrderController.java#create` + `task/service/WorkOrderService.java#createByAgent` |
| cow-agent：park 注册（fail-closed）/ X-Action-Id 透传 / 超时 expire | `cow-agent/app/agent_manager.py#_park_confirm`、`cow-agent/app/cow_tools.py`（`register_action`/`expire_action`/`current_action_id`） |

### 三项缺口的关闭情况

1. **审批未下沉** → 已关闭：svc-agent 无 `X-Action-Id` 直连 `POST /tasks` → 403「智能体建单必须携带审批凭证」；伪造凭证 → 403「无效审批凭证」（HTTP 实证）。
2. **admin 层无幂等键** → 已关闭：`action_id` 唯一约束 + APPROVED→EXECUTED 单次条件迁移，重复提交 409 且只一张单。
3. **批准人=发起人未绑定** → 已关闭：`/agent/confirm` 校验当前登录人 = action.username，不匹配 403。

### 测试清单（全绿）

- **cow-admin 单测 64 项**（43 → 64，新增 21：`PendingActionServiceTest` 11 项：注册绑定发起人/未知会话 400/非发起人 403/过期作废/正常批准/重复审批 409/EXECUTED 重放 409/未批准 403/批准后过期 403/摘要不符 403/digest 篡改检测；`WorkOrderServiceTest` +5：无凭证 403/正常建单+EXECUTED/REJECTED 拦截/摘要不符拦截/并发重复 409；`WorkOrderControllerTest` 2：SERVICE 分流/人工不受影响；`AgentControllerTest` +3：confirm 先落状态再转发/转发失败补偿作废/注册端点）；
- **cow-agent pytest 21 项**（16 → 21，新增 5：park 注册+放行凭证写入 ContextVar/注册失败 fail-closed/超时同步 expire/非领域写工具跳过注册/建单请求携带 X-Action-Id 头）；
- **端到端 `acceptance/cow_d2_agent_confirm.py` 7/7**（admin 代理完整确认流复跑，断言未放松）；
- HTTP 实证：svc-agent 无凭证直连 403、伪造凭证 403。
