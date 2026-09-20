# acceptance/ — 浏览器级验收脚本（Playwright）

仓库内留档的自动化验收脚本，验收结论与证据见根目录 `验收报告_20260914.md`。

## 脚本

| 脚本 | 范围 | 结果 |
|---|---|---|
| `cow_d1_main.py` | 浏览器主链路：登录 → 看板 → 牛棚孪生图 → 单牛时间线 → 事件流 → 工单状态机全流程 → 设备页 → AI 助手 | 15/15 通过 |
| `cow_d2_agent_confirm.py` | 智能体高风险写操作人工确认闭环（park → 前端弹窗 → 批准/超时拒绝 → 工单落库） | 7/7 通过 |
| `cow_device_flip.py` | 设备心跳在线翻转：OFFLINE → 心跳 → ONLINE → 停跳 70s → OFFLINE（API 断言 + 页面截图双证据） | 通过（2026-09-20） |
| `cow_offline_lifecycle.py` | 设备离线完整生命周期：断网缓存(HIGH 优先级+心跳停用) → 恢复补传(DEDUP DEMO 重发全去重) → 多条离线事件只建 1 张高优维修单 → 全流转关闭 → 再次离线产生新一轮 → 同 event_id 重发 duplicated 不出单 | 10/10 通过（2026-09-20） |
| `cow_demo_record.py` | 55s 演示视频录制（Playwright recordVideo，登录→看板→3D 选牛→设备→AI 助手真实对话） | 已录制（2026-09-20，GIF 见 `docs/screenshots/demo-cow-20260920.gif`） |

## 怎么跑

```bash
# 任一装了 playwright 的 Python 均可；验收时用 tools/pw-venv
python acceptance/cow_d1_main.py
python acceptance/cow_d2_agent_confirm.py
```

## 前置条件

以下服务全部在跑，且 `cow-edge/simulator.py` 已产生过事件（库内有事件/工单/孪生数据）：

- PostgreSQL（`cow_db` 库）+ Redis + Mosquitto(1883)
- cow-admin(8081，MQTT 入站开) / cow-ai(8001) / cow-agent(8003) / cow-web(5174)
- 演示账号 admin / Admin@123

## 截图证据

验收截图留档在 `docs/screenshots/`（看板、牛棚孪生图、写操作确认弹窗、设备在线翻转 4 张）。
