# 奶牛数字孪生 AI Agent 全栈平台

> 面向智慧养殖场景的 AI 全栈应用平台，融合数字孪生、物联网事件处理、自研 Agent Runtime 与智能决策能力，构建从边缘数据采集、状态管理到 AI 辅助决策的完整业务闭环。

## 运行实景（真实运行截取）

| 数据看板 | 牛棚孪生图（103 头牛状态变色） |
| --- | --- |
| ![数据看板](docs/screenshots/cow-02-dashboard.png) | ![牛棚孪生图](docs/screenshots/cow-03-barn.png) |

| 智能体写操作人工确认弹窗 | 设备在线状态（心跳驱动） |
| --- | --- |
| ![写操作确认](docs/screenshots/cow-08b-agent-confirm.png) | ![设备在线](docs/screenshots/cow-device-online.png) |

> 验证记录：浏览器级主链路 15/15、写操作确认机制 7/7、后端单测 43 项全过——详见 `验收报告_20260914.md` 与 `PROJECT_STATUS.md`；验收脚本见 `acceptance/`。

## 项目定位

本项目旨在探索 **AI Agent 在垂直业务场景中的工程化落地方式**。

项目由三个层次组成：

| 层次 | 定位 | 核心职责 |
| --- | --- | --- |
| 奶牛数字孪生平台 | AI 全栈业务应用 | 事件接入、状态管理、告警工单、可视化与人机协同 |
| BearCode Agent Runtime | 自主构建的通用智能体技术底座 | Agent Loop、工具调用、权限边界、Memory、Skills 与会话恢复 |
| cow-agent | 基于 BearCode 的牧场领域智能体服务 | 事件分析、SOP 复核、任务规划与辅助决策 |

这不是一个简单调用大语言模型接口的聊天应用，而是一套由 **自研 Agent Runtime 驱动的智慧牧场 AI Agent 系统**。系统将模型推理、工具调用、权限控制、记忆管理和真实业务流程连接起来，让 Agent 的判断能够安全、可审计地进入业务闭环。

```mermaid
flowchart LR
    EDGE[边缘事件采集] --> EVENT[事件接入与业务处理]
    EVENT --> TWIN[奶牛数字孪生状态管理]
    TWIN --> ALERT[告警与任务闭环]
    ALERT --> AGENT[AI Agent 分析与决策辅助]
    AGENT --> CONFIRM[人工确认]
    CONFIRM --> EXECUTE[业务执行]
```

## 核心能力

### 1. 数字孪生与业务闭环

系统参考真实牧场管理流程，实现：

- 奶牛个体档案与实时状态管理
- AI 事件标准化接入
- 事件时间线追踪
- 告警与工单自动生成
- 工单状态流转与人工复核
- 牛棚、摄像头和边缘节点可视化管理

当前 MVP 聚焦一个可完整演示的垂直切片：

- 20 号牛棚
- 103 头奶牛
- 爬跨事件（`MOUNTING`）
- 跛行事件（`LAMENESS`）

完整业务链路如下：

```mermaid
flowchart LR
    A[AI 检测事件] --> B[事件标准化]
    B --> C[数字孪生状态更新]
    C --> D[规则引擎分析]
    D --> E[告警工单生成]
    E --> F[人工处理闭环]
```

### 2. 自研 BearCode Agent Runtime

BearCode 是本项目自主构建的 Agent Runtime 技术底座。它不把智能体简化为“输入问题、调用 LLM、返回文本”，而是提供从任务理解到受控执行的完整运行时：

```mermaid
flowchart TD
    REQUEST[用户请求] --> RUNTIME[BearCode Agent Runtime]
    RUNTIME --> REASON[任务理解与推理]
    REASON --> PLAN[工具调用规划]
    PLAN --> AUTH[权限与参数检查]
    AUTH --> TOOL[执行业务工具]
    TOOL --> RESULT[结果回写]
    RESULT --> REASON
    RESULT --> MEMORY[Memory / Skills 更新]
    REASON --> ANSWER[生成最终响应]
```

#### Agent Loop

完整支持：

- 用户请求解析与上下文组装
- 模型推理与 Tool Call 解析
- 工具执行和结果回写
- 多轮任务推进
- 任务结束条件判断

#### 工具调用体系

支持：

- 领域业务工具调用
- 外部 MCP 工具接入
- 子 Agent 调度
- 工具参数与执行结果管理
- 只读工具和写操作工具分级

#### 权限边界控制

模型负责思考、规划并提出执行意图，Runtime 负责检查权限、控制工具调用并执行实际操作，从而避免：

- 模型绕过业务系统直接修改数据
- 未经授权的工具调用
- 写操作在用户无感知的情况下执行
- 不可追踪的业务变更

#### Memory、Skills 与会话恢复

支持：

- 长期记忆与项目上下文保存
- Skills 能力沉淀和工作流复用
- Session 保存与长任务状态恢复
- 上下文压缩与多轮会话连续性

### 3. 领域智能体 cow-agent

`cow-agent` 基于 BearCode Agent Runtime 构建，将通用智能体能力与智慧牧场的业务工具、数据权限和 SOP 结合起来：

```text
BearCode Agent Runtime
          ↓
      cow-agent
          ↓
   牧场智能决策助手
```

#### 事件分析

Agent 可以组合调用多个领域工具：

- 查询奶牛档案
- 查询近期事件
- 分析个体时间线
- 解释异常状态
- 汇总并向场长报告

例如，当用户询问“`COW-0042` 今天发生了什么？”时，Agent 会依次查询奶牛档案、近期事件和状态时间线，再基于真实业务数据生成结论，而不是仅依赖模型自身知识回答。

#### SOP 辅助决策

Agent 可以按照已沉淀的业务 Skills 执行标准流程，包括：

- 爬跨事件分析
- 繁殖流程建议
- 跛行与异常事件复核
- 关键证据与事件编号回溯

#### 人机协同执行

所有涉及业务数据变更的操作均遵循“Agent 提议、人工确认、业务系统执行”的边界：

```mermaid
flowchart LR
    A[Agent 分析并提出建议] --> B[前端展示工具名、参数和理由]
    B --> C{用户审批}
    C -->|批准| D[cow-admin 确定性执行]
    C -->|拒绝或超时| E[取消操作并保留文字建议]
    D --> F[审计记录]
```

例如，创建工单时，`cow-agent` 只能提出 `create_work_order` 调用请求；前端确认后，才由 `cow-admin` 执行写操作。系统以此保证：

> Agent 负责智能分析与决策建议，业务系统负责确定性执行。

## 系统架构

```mermaid
flowchart TB
    USER[用户] --> WEB[cow-web<br/>Vue 3 + TypeScript + Element Plus]
    WEB -->|REST /api/v1| ADMIN[cow-admin<br/>Spring Boot 3]

    subgraph BUSINESS[数字孪生业务层]
        ADMIN --> EVENT[事件处理与规则引擎]
        ADMIN --> TWIN[数字孪生状态与时间线]
        ADMIN --> WORK[告警与工单状态机]
        EVENT --> PG[(PostgreSQL)]
        TWIN --> PG
        WORK --> PG
        ADMIN --> REDIS[(Redis)]
    end

    WEB -->|AI 助手| ADMIN
    ADMIN -->|代理、鉴权与审计| COWAGENT[cow-agent<br/>领域智能体服务]
    COWAGENT --> RUNTIME[BearCode Agent Runtime]
    RUNTIME --> LLM[LLM]
    RUNTIME --> TOOLS[Tools / MCP]
    RUNTIME --> MEMORY[Memory / Skills]
    COWAGENT -->|受控领域工具回调| ADMIN

    subgraph EDGE[边缘事件层]
        DEVICE[摄像头 / 模拟设备] --> EDGEAPP[cow-edge]
        EDGEAPP --> SQLITE[(SQLite 离线缓存)]
        EDGEAPP --> MQTT[MQTT]
    end

    MQTT --> ADMIN
    EDGEAPP -->|断网恢复后 HTTP 补传| ADMIN
    AI[cow-ai<br/>模型推理服务] -.-> EDGEAPP
```

## 技术架构

### cow-web：前端应用

**技术栈**：Vue 3、TypeScript、Element Plus

负责牛棚可视化、实时事件展示、工单管理、设备状态展示，以及 AI 助手交互与写操作审批。

### cow-admin：业务后端

**技术栈**：Java 17、Spring Boot 3、MyBatis-Plus、PostgreSQL、Redis

负责用户权限、统一事件接入、数字孪生状态、告警工单流程，以及 Agent 请求代理、鉴权与审计。

### cow-ai：AI 推理服务

**技术栈**：Python、FastAPI

负责 AI 模型接口、爬跨和跛行推理服务，以及视觉模型的标准化接入。

### cow-agent：Agent 服务

**技术栈**：Python、FastAPI、BearCode Agent Runtime

负责 Agent 推理、多轮任务推进、工具编排、领域 Skills 执行、写操作确认和智能决策辅助。

### cow-edge：边缘计算

**技术栈**：Python、MQTT、SQLite

负责设备与 AI 事件模拟、本地离线缓存、网络恢复与优先级补传，以及边缘节点心跳上报。

## 工程设计亮点

### 1. 事件幂等处理

每个事件拥有唯一的 `event_id`。系统通过数据库唯一约束和接入层校验，保证重复事件不会重复入库、不会重复更新数字孪生状态，也不会重复触发告警。

### 2. 断网恢复机制

边缘节点在网络不可用时将事件写入本地 SQLite，网络恢复后按照优先级补传：

```text
设备事件
   ↓
SQLite 本地缓存
   ↓
网络恢复
   ↓
HIGH / LOW 优先级补传
   ↓
服务端幂等处理
```

该机制支持离线缓存、优先级队列、成功确认后删除和自动恢复。

### 3. 工单状态机与并发控制

```text
NEW → DISPATCHED → PROCESSING → PENDING_REVIEW → CLOSED
                       └────────────────────────→ CANCELLED
```

系统通过状态机限制非法流转，并使用乐观锁避免并发修改时的 last-write-wins；版本冲突统一返回 `409 Conflict`。

### 4. 迟到事件保护

当事件的 `event_time` 早于当前数字孪生状态对应的事件时间时，系统只追加时间线记录，不回退当前状态，避免断网补传导致实时状态被旧事件覆盖。

### 5. Agent 写操作确认

写工具调用进入确认队列后，由前端展示工具名、参数和调用理由。用户批准后才执行；拒绝或 120 秒未审批则自动取消，确保 Agent 不能绕过人工确认修改业务数据。

### 6. 全链路审计

AI 助手请求经 `cow-admin` 统一代理，用户权限、会话、消息、工具调用结果和 token 用量均可落库追踪，使智能体行为可回溯、可审计。

## 项目目录

```text
cow-digital-twin-platform/
├── cow-web/             # Vue 3 前端（开发端口 5173，容器端口 8089）
├── cow-admin/           # Spring Boot 业务系统（端口 8081）
├── cow-agent/           # FastAPI 领域智能体服务（端口 8003）
│   └── bear/agents/     # BearCode Agent Runtime 核心模块
├── cow-ai/              # FastAPI AI 推理服务（端口 8000）
├── cow-edge/            # Python 边缘事件模拟器
├── deploy/              # Mosquitto 等部署配置
└── docker-compose.yml
```

## 技术栈总览

| 领域 | 技术 |
| --- | --- |
| 业务后端 | Java 17、Spring Boot 3、MyBatis-Plus、PostgreSQL、Redis |
| AI 与 Agent | Python、FastAPI、LLM、Agent Runtime、MCP、Memory、Skills |
| 前端 | Vue 3、TypeScript、Element Plus |
| 边缘与消息 | Python、MQTT、SQLite |
| 工程化 | Docker Compose、JWT、BCrypt、OpenAPI |

## 快速开始

### 环境要求

- JDK 17+
- Maven 3.8+
- Node.js 18+
- Python 3.9+
- Docker 与 Docker Compose（用于一键编排，可选）

### Docker 一键启动

```bash
# 设置 LLM Key（OpenAI 兼容协议，默认使用 DeepSeek 模型）
export LLM_API_KEY=sk-...

# 启动基础服务：PostgreSQL、Redis、Mosquitto、admin、ai、agent、web
docker compose up -d --build

# 可选：启动边缘事件模拟器
docker compose --profile demo up -d cow-edge
```

也可以将 `LLM_API_KEY` 写入 `cow-agent/.env`，该文件已被 `.gitignore` 排除。

启动后可访问：

| 服务 | 地址 |
| --- | --- |
| Web 前端 | <http://localhost:8089> |
| Swagger UI | <http://localhost:8081/swagger-ui.html> |
| cow-ai 健康检查 | <http://localhost:8000/health> |
| cow-agent 健康检查 | <http://localhost:8003/health> |

`cow-agent` 的 `/health` 返回 `llm_configured=true` 后才可进行真实 LLM 对话。

主要环境变量：

| 变量 | 说明 |
| --- | --- |
| `LLM_BASE_URL` | OpenAI 兼容接口地址，默认 `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名称，默认 `deepseek-flash` |
| `LLM_API_KEY` | 模型服务密钥，必填且无默认值 |
| `COW_ADMIN_BASE_URL` | cow-admin 服务地址 |
| `AGENT_USER` / `AGENT_PASSWORD` | Agent 回调业务系统使用的 Service 账号 |
| `CONFIRM_TIMEOUT_SECONDS` | 写操作审批超时，默认 120 秒 |

> Windows PowerShell 可使用 `$env:LLM_API_KEY="sk-..."` 设置当前会话的环境变量。

### 本地开发

> **无 Docker 环境实测路径（2026-09-14 验收通过）**：便携 PostgreSQL 16.10（建库 `cow_db`）+ 便携 Redis 5.0.14 + Mosquitto 2.0.22 便携版（`mosquitto -c acceptance.conf`，匿名监听 1883）即可满足全部依赖；MQTT 链路默认 `MQTT_ENABLED=true` 时生效。

| 模块 | 启动命令 |
| --- | --- |
| cow-admin | `cd cow-admin && mvn spring-boot:run`，需先启动 PostgreSQL、Redis 并创建 `cow_db` |
| cow-ai | `cd cow-ai && pip install -r requirements.txt && uvicorn app.main:app --port 8000` |
| cow-agent | `cd cow-agent && pip install -r requirements.txt && uvicorn app.main:app --port 8003`，需先配置 `LLM_API_KEY` |
| cow-edge | `cd cow-edge && pip install -r requirements.txt && python simulator.py --mode online` |
| cow-web | `cd cow-web && npm install && npm run dev`，默认访问 <http://localhost:5173>，`/api` 已代理到 8081 |

后端首次启动会自动执行 `schema.sql`，并由 `DataInitializer` 初始化账号、角色权限、103 头奶牛档案、4 个摄像头和 1 个边缘节点。

## 默认账号

| 账号 | 密码 | 角色与权限 |
| --- | --- | --- |
| `admin` | `Admin@123` | ADMIN，全部权限 |
| `vet` | `Vet@123` | VET，兽医，包含 `agent:chat` |
| `breeder` | `Breeder@123` | BREEDER，繁育员，包含 `agent:chat` |
| `svc-agent` | `SvcAgent@123` | SERVICE，cow-agent 回调专用，仅允许业务查询和手工建单 |

密码在启动时由 `BCryptPasswordEncoder` 编码入库，不以明文形式保存。

边缘节点 `edge-node-01` 的演示用 `deviceKey` 为 `edge-node-01-secret-2026`。HTTP 上报通过 `X-Device-Key` 请求头传递，心跳通过请求体内的 `deviceKey` 传递。生产部署必须更换此凭证。

## 演示与验收

### 断网恢复演示

前置条件：平台和 MQTT 已启动，当前目录切换到 `cow-edge`。

#### 1. 在线事件流

```bash
python simulator.py --mode online --interval 5
```

前端牛棚图、事件流和工单看板会显示实时数据。可以按 `Ctrl+C` 停止，也可以通过停止 Mosquitto 模拟真实断网；在线发布失败的事件会自动写入本地 `wal_buffer`。

#### 2. 离线缓存

```bash
python simulator.py --mode offline --duration 600 --interval 5
```

- 事件写入本地 `edge_buffer.db`
- `LAMENESS` 和 `DEVICE_OFFLINE` 记为高优先级
- 心跳连续失败 3 次后只写入本地
- 验证 72 小时缓存时可将 `--duration` 设置为 `259200`
- 设备页中的 `edge-node-01` 会在 60 秒后显示为 `OFFLINE`

#### 3. 恢复补传与幂等验证

```bash
python simulator.py --mode reconnect
```

恢复后先补传 HIGH 优先级事件，再补传 LOW 优先级事件；只有服务端确认成功才删除本地记录。脚本结束时会再次发送同一批 `event_id`，用于验证服务端幂等去重。

预期结果：

- 控制台输出 `DEDUP DEMO: ... duplicate alerts = 0`
- 设备页 `pending_count` 归零并恢复 `ONLINE`
- 事件流中同一 `event_id` 只出现一次

### AI 助手演示

前置条件：平台已启动，`cow-agent` 已配置 `LLM_API_KEY`，且 `/health` 显示 `llm_configured=true`。使用 `admin`、`vet` 或 `breeder` 登录前端，进入“AI 助手”页面。

1. 执行 `python simulator.py --mode online --interval 5` 制造事件。`MOUNTING` 事件会触发 24 小时收敛的告警工单。
2. 向 AI 助手提问：“`COW-0042` 今天什么情况？”工具调用轨迹会展示 `query_cow_profile`、`list_events` 和 `query_cow_timeline` 的取数过程。
3. 继续提问：“帮我复核一下这次爬跨要不要安排配种。”Agent 会命中 `mounting-review` SOP，结合档案、近期事件和时间线给出附带 `cow_id`、`event_id` 的复核建议。
4. 当 Agent 调用 `create_work_order` 时，前端会展示工具名、参数和理由。批准后工单看板出现 `NEW` 工单；拒绝或 120 秒内未操作时，系统取消写操作并保留文字建议。
5. 在 `cow-admin` 的 `agent_session` 和 `agent_message` 表中核对对话、工具轨迹和 token 用量审计记录。

### 真实 LLM 联调

1. 在 `cow-agent/.env` 中配置 `LLM_API_KEY=sk-...`。
2. 执行 `uvicorn app.main:app --port 8003` 启动 Agent 服务。
3. 请求 `http://localhost:8003/health`，确认 `llm_configured=true`。
4. 通过前端 AI 助手页面或 `POST /api/v1/agent/chat` 验证对话与工具调用。

## 核心设计细节

### 统一事件契约

边缘模拟器和后端 DTO 使用一致的字段命名：

```text
schema_version / tenant_id / farm_id / event_id / cow_id / device_id /
event_type / event_time / ingest_time / quality / confidence / model_version /
evidence_ref / raw
```

### 幂等去重

`unified_event.event_id` 具有数据库唯一约束。重复插入冲突时返回 `duplicated=true`，不重复落库、不触发数字孪生更新，也不创建重复工单。这是“重复告警为 0”的最终一致性防线。

### 工单状态机

合法流转定义在 `WorkOrderService.TRANSITIONS`。所有变更携带 `version` 并使用 MyBatis-Plus 乐观锁；非法状态流转返回业务错误，并发版本冲突返回 `409 Conflict`。

### 数字孪生迟到事件

当新接收事件的 `event_time` 早于当前状态事件时间时，系统只追加事件时间线，不回退当前孪生状态。

### 设备在线状态

设备在线状态是基于最近心跳计算的属性，阈值为 60 秒，不作为固定状态字段持久化。

### cow-agent 隔离与审批

- Agent 领域能力通过 `CowAgent`、`custom_tools` 和 Skills 注入
- `create_work_order` 等写工具必须进入确认流程
- `svc-agent` 仅拥有业务查询和手工建单权限，不拥有系统管理权限
- 每个 Session 使用独立 Agent 实例和 `asyncio.Lock`，隔离非并发安全状态
- Session 与 Message 经 `cow-admin` 审计落库
- Skills 使用进程级缓存，修改 `SKILL.md` 后需要重启 `cow-agent`

## 成熟能力插入点

| 能力资产 | 插入位置 |
| --- | --- |
| 爬跨 YOLOv8n 权重 | `cow-ai/app/routers/infer.py` 的 `infer_mounting()`；权重路径由 `MOUNTING_WEIGHTS_PATH` 配置 |
| 跛行 YOLOv11 + RTMPose + XGBoost 推理链 | `cow-ai/app/routers/infer.py` 的 `infer_lameness()`；权重目录由 `LAMENESS_WEIGHTS_PATH` 配置 |
| 真实摄像头 RTSP 接入 | 将 `cow-edge/simulator.py` 的 `make_event()` 替换为“RTSP 拉流 → 抽帧 → 调用 cow-ai → 组装事件”，事件契约保持不变 |
| 三维模型资产（glTF） | 在 `cow-web/src/views/barn/index.vue` 的 Three.js 升级插入点替换 SVG 渲染层，数据层保持不变 |
| 完整事件契约 | 扩展 `UnifiedEvent.java` 与 `db/schema.sql` 中的 `unified_event` 表，并同步提升 `schema_version` |

## 当前范围与验收标准

当前版本锁定在 20 号牛棚、103 头奶牛、`MOUNTING` 与 `LAMENESS` 两类 AI 事件，覆盖数字孪生状态、告警工单闭环、摄像头与边缘节点在线状态、断网缓存恢复和牛棚二维可视化。

主要验收标准：

- 结构化事件离线缓存不少于 72 小时
- 基于 `event_id` 幂等去重，重复告警为 0
- 断网重连后按照事件优先级补传
- 工单并发修改使用乐观锁，禁止 last-write-wins
- Agent 写操作必须经用户确认并留下审计记录

## 后续规划

- 接入真实摄像头 RTSP 视频流
- 部署奶牛爬跨与跛行视觉模型
- 引入发情和疾病预测模型
- 升级 Three.js 三维数字孪生展示
- 支持多牧场管理与跨场区分析
- 扩展更多牧场 SOP Skills 与业务工具

## 一句话总结

> 本项目构建了一套由自研 BearCode Agent Runtime 驱动的 AI 全栈智慧牧场平台，将 Agent 推理能力与数字孪生业务系统结合，实现从边缘数据采集、业务流程管理到智能决策辅助的完整闭环。
