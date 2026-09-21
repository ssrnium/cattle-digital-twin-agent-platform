# 云服务器部署手册（无 GPU 单机，Ubuntu 22.04）

> 目标：一台 4 核 8G 无卡服务器上，`docker compose up -d --build` 一键起全平台。
> 验收口径：健康检查全过 → 前端可登录 → 事件接入 → 工单流转 → AI 助手可对话（写操作需人工确认）→ 容器重启后状态恢复。

## 1. 准备

```bash
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker $USER && newgrp docker
docker compose version   # 需 v2.x
```

## 2. 部署

```bash
git clone https://github.com/ssrnium/cattle-digital-twin-agent-platform.git
cd cattle-digital-twin-agent-platform
cp .env.example .env          # 编辑填 key：LLM_API_KEY / JWT_SECRET
docker compose up -d --build
# 可选：边缘模拟器（制造事件流与断网缓存演示）
docker compose --profile demo up -d cow-edge
```

## 3. 验证清单

| 检查 | 命令/路径 | 预期 |
| --- | --- | --- |
| 健康状态 | `docker compose ps` | 全部 healthy/running |
| admin | `curl localhost:8081/swagger-ui.html` | 200/302 |
| agent | `curl localhost:8003/health` | `llm_configured=true`（需 LLM_API_KEY） |
| 前端 | `http://<服务器IP>:8089` | 登录页（admin/Admin@123） |
| 事件→工单 | `docker compose --profile demo up -d cow-edge` | 看板事件流、牛棚变色、规则引擎出工单 |
| MQTT 消费 | `docker compose logs cow-admin \| grep -i mqtt` | 订阅成功无异常 |
| AI 助手 | AI 助手页问"COW-0042 今天什么情况" | 工具轨迹 + 回答；建单弹人工确认框 |
| 断网演示 | 见 README「断网恢复演示脚本（三步）」 | OFFLINE 翻转 + 补传 + 重复告警 0 |
| 重启恢复 | `docker compose restart && docker compose ps` | 数据卷数据仍在（事件/工单/孪生） |

## 4. 备注

- 端口：8089(web) / 8081(admin) / 8003(agent) / 1883(MQTT)；云安全组按需放行 8089 即可，其余建议仅内网。
- 演示用 deviceKey（`edge-node-01-secret-2026`）与默认账号密码仅用于演示，公网部署请更换（根级 .env 的 `DEVICE_KEY`、`AGENT_PASSWORD`、`JWT_SECRET`）。
- cow-ai 为推理占位服务（确定性伪随机结果）；真实视觉模型权重属课题保密资产，不随仓库分发（接入点见 README「成熟代码插入点清单」）。
