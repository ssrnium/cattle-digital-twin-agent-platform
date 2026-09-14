# cow-edge 边缘事件模拟器

20 号牛棚边缘节点（edge-node-01）的行为模拟：AI 事件产生、MQTT 上报、心跳、断网本地缓存与恢复补传。

## 三种模式

```bash
pip install -r requirements.txt

# 1) 在线：随机产生爬跨/跛行事件 → MQTT → cow-admin
python simulator.py --mode online --interval 5

# 2) 断网：事件写入本地 SQLite（edge_buffer.db，wal_buffer 表，含优先级），心跳失败后只写本地
#    验收"结构化事件离线缓存 ≥72h"：--duration 259200（本地缓存文件持续保留，可随时 reconnect 补传）
python simulator.py --mode offline --duration 3600 --interval 5

# 3) 恢复：高优先级(LAMENESS/DEVICE_OFFLINE)先传、普通后传；成功才删本地；
#    随后自动把同一批 event_id 重发一遍，服务端幂等去重 → 重复告警 0
python simulator.py --mode reconnect
```

环境变量可覆盖默认：`MQTT_HOST` / `MQTT_PORT` / `ADMIN_URL` / `DEVICE_ID` / `DEVICE_KEY` / `EDGE_DB_PATH`。

真实摄像头 RTSP 接入改造点：`make_event()` 替换为"RTSP 拉流 → 抽帧 → 调用 cow-ai /api/v1/infer/* → 命中后组装事件"的流水线，事件契约字段保持不变。
