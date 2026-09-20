# 智能体写操作审批边界审计（2026-09-20）

> 审计问题：`svc-agent` 是否能够绕过用户确认，直接调用创建工单接口？
> 结论：**能。** 审批关卡目前只存在于 cow-agent 工具层（`confirm_fn` park），cow-admin 不对 `POST /api/v1/tasks` 校验"是否已获用户批准"。本文记录边界事实、现有防线与下沉方案。

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
