# PROJECT_STATUS — 单牛数字孪生与健康繁殖任务管理平台

> 更新日期：2026-09-18 ｜ 当前版本：**v0.2.0-acceptance**（首场验证版切片，全链路验收通过）

## 状态速览

| 项 | 当前状态 |
|---|---|
| 范围 | 20号牛棚 / 103 头奶牛 / 爬跨（MOUNTING）+ 跛行（LAMENESS）两类事件 / 告警工单闭环 / 断网缓存恢复 / 牧场智能体 |
| AI 模型 | **mock 推理**（cow-ai 返回确定性伪随机结果；第一阶段真实权重待接） |
| 智能体 LLM | 真实：DeepSeek `deepseek-flash`（OpenAI 兼容），写操作需人工确认 |
| 已验证运行环境 | Windows 11 本地：便携 PostgreSQL 16.10 + Redis 5.0.14 + **Mosquitto 2.0.22**（1883）+ JDK 17.0.2 + Node 24 + Python 3.9 venv；Docker 未安装，compose 未验证 |
| 已通过测试 | 浏览器主链路 **15/15**（acceptance/cow_d1_main.py）；写操作确认机制 **7/7**（cow_d2_agent_confirm.py）；cow-admin 单测 **43 项**（事件幂等/状态机/乐观锁/迟到事件/规则引擎/心跳在线翻转/JWT/智能体审计等，mvn test）；cow-agent pytest **16 passed**；admin BUILD SUCCESS；web `npm run build` 绿（vue-tsc type-check 0 错误，已接入 build 前置） |
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

## 正在开发（下一阶段）

1. **真实模型权重接入**（第一阶段资产：爬跨 YOLOv8n、跛行 YOLOv11+RTMPose+XGBoost，cow-ai 的 infer 接口留插入点）；
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
mvn -s tools/settings.xml package                     # cow-admin（含 43 项单测）
cow-agent/.venv/Scripts/python -m pytest tests/       # 16 项
npm run build                                         # cow-web
# 验收
tools/pw-venv/Scripts/python acceptance/cow_d1_main.py           # 浏览器主链路 15 项
tools/pw-venv/Scripts/python acceptance/cow_d2_agent_confirm.py  # 写操作确认机制 7 项
# 断网演示
cow-edge/.venv/Scripts/python simulator.py --mode offline --duration 60 --interval 2
cow-edge/.venv/Scripts/python simulator.py --mode reconnect
```
