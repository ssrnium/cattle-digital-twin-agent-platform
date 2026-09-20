# -*- coding: utf-8 -*-
"""设备离线完整生命周期验证：
断网(心跳失败停用) → SQLite 缓存(周期性 DEVICE_OFFLINE HIGH) → 恢复补传(成功才删)
→ 幂等去重(重复告警 0) → 规则引擎只建 1 张高优维修单 → 关闭工单 → 再次离线产生新一轮 → 同 event_id 重发不重复。
运行：tools/pw-venv/Scripts/python.exe cow-digital-twin-platform/acceptance/cow_offline_lifecycle.py
前置：cow-admin(8081)/PG/Redis 在跑。psql 用 PSQL 环境变量指定。
"""
import json, os, subprocess, sys, time, uuid, pathlib, datetime
import httpx

ADMIN = "http://127.0.0.1:8081"
DEAD = "http://127.0.0.1:9999"
EDGE = pathlib.Path(__file__).parent.parent / "cow-edge"
PY = sys.executable
PSQL = os.environ.get("PSQL", "psql")
RESULTS = []

def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(f'{"✓" if cond else "✗"} {name} {extra}', flush=True)

def psql(sql):
    r = subprocess.run([PSQL, "-U", "postgres", "-h", "127.0.0.1", "-d", "cow_db",
                        "-tAc", sql], capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

def counts():
    ev = int(psql("SELECT count(*) FROM unified_event WHERE event_type='DEVICE_OFFLINE'") or 0)
    wo = int(psql("SELECT count(*) FROM work_order WHERE type='DEVICE_REPAIR'") or 0)
    return ev, wo

def api(token, method, path, body=None, raw=False):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = httpx.request(method, ADMIN + path, headers=h, json=body, timeout=30)
    if raw:
        return r.status_code, r.json()
    body = r.json()
    assert body.get("code") == 200, f"{method} {path} → {body}"
    return body["data"]

# 0 登录
r = httpx.post(ADMIN + "/api/v1/auth/login",
               json={"username": "admin", "password": "Admin@123"}, timeout=15)
TOKEN = r.json()["data"]["token"]

# 1 清场：备份旧缓存库 + 计数基线
old = EDGE / "edge_buffer.db"
bak = EDGE / "edge_buffer.bak.db"
if bak.exists():
    bak.unlink()
if old.exists():
    old.rename(bak)
ev0, wo0 = counts()
print(f"基线: DEVICE_OFFLINE事件={ev0} DEVICE_REPAIR工单={wo0}", flush=True)

# 2 断网缓存（admin-url 指向死端口：心跳 3 连败后停用，周期性缓存 DEVICE_OFFLINE）
t0 = time.time()
off = subprocess.run([PY, "simulator.py", "--mode", "offline", "--admin-url", DEAD,
                      "--duration", "34", "--interval", "3"],
                     cwd=EDGE, capture_output=True, text=True, timeout=120)
log_off = off.stdout + off.stderr
n_buffered = log_off.count("BUFFERED [HIGH] DEVICE_OFFLINE")
check("1 断网期周期性缓存 DEVICE_OFFLINE(HIGH)", n_buffered >= 2, f"{n_buffered} 条")
check("2 心跳 3 连败后停用并转本地缓存", "heartbeat failed 3 times" in log_off)

# 3 恢复补传（真实 admin：HIGH 优先、成功才删、末尾 DEDUP DEMO 重发同批）
rec = subprocess.run([PY, "simulator.py", "--mode", "reconnect", "--admin-url", ADMIN],
                     cwd=EDGE, capture_output=True, text=True, timeout=180)
log_rec = rec.stdout + rec.stderr
check("3 补传完成且本地缓存清空", "duplicate alerts = 0" in log_rec,
      [l for l in log_rec.splitlines() if "DEDUP" in l][-1][:80] if "DEDUP" in log_rec else log_rec[-120:])

time.sleep(2)
ev1, wo1 = counts()
check("4 DEVICE_OFFLINE 事件全部入库(幂等,不重复)", ev1 - ev0 == n_buffered,
      f"+{ev1-ev0} 条 (缓存 {n_buffered} 条)")
check("5 多条离线事件只产生 1 张 DEVICE_REPAIR 工单", wo1 - wo0 == 1,
      f"工单 +{wo1-wo0}")

row = psql("SELECT id||'|'||order_no||'|'||state||'|'||priority FROM work_order "
           "WHERE type='DEVICE_REPAIR' ORDER BY id DESC LIMIT 1")
oid, order_no, state, prio = row.split("|")
check("6 维修单为高优先级且 NEW", prio == "HIGH" and state == "NEW", f"{order_no} {state}/{prio}")

# 7 关闭工单（真实状态机流转，乐观锁逐步带 version）
v = api(TOKEN, "GET", f"/api/v1/tasks/{oid}")["version"]
api(TOKEN, "POST", f"/api/v1/tasks/{oid}/assign", {"assigneeId": 1, "version": v})
v = api(TOKEN, "GET", f"/api/v1/tasks/{oid}")["version"]
api(TOKEN, "POST", f"/api/v1/tasks/{oid}/start", {"version": v})
v = api(TOKEN, "GET", f"/api/v1/tasks/{oid}")["version"]
api(TOKEN, "POST", f"/api/v1/tasks/{oid}/submit-review",
    {"result": "已更换电源模块并恢复在线（生命周期验收）", "version": v})
v = api(TOKEN, "GET", f"/api/v1/tasks/{oid}")["version"]
api(TOKEN, "POST", f"/api/v1/tasks/{oid}/review",
    {"approved": True, "reviewResult": "恢复在线，关闭", "version": v})
st = api(TOKEN, "GET", f"/api/v1/tasks/{oid}")["state"]
check("7 工单全流转关闭", st == "CLOSED", f"{order_no} → {st}")

# 8 再次离线 → 新一轮告警（前一单已关闭，不再去重）
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
eid = "LC-" + uuid.uuid4().hex[:12]
event = {"schema_version": "1.0", "tenant_id": "t1", "farm_id": "farm-01",
         "event_id": eid, "cow_id": None, "device_id": "edge-node-01",
         "event_type": "DEVICE_OFFLINE", "event_time": now, "ingest_time": now,
         "quality": "good", "confidence": 0.99, "model_version": "lifecycle-test",
         "evidence_ref": "sim://lifecycle", "raw": {}}
# 事件接口走设备凭证，不走用户 JWT
r = httpx.post(ADMIN + "/api/v1/events", json=[event],
               headers={"X-Device-Key": "edge-node-01-secret-2026"}, timeout=15)
time.sleep(2)
ev2, wo2 = counts()
check("8 关闭后再次离线产生新一轮工单", r.status_code == 200 and wo2 - wo1 == 1,
      f"工单 {wo1}→{wo2}")
new_no = psql("SELECT order_no FROM work_order WHERE type='DEVICE_REPAIR' ORDER BY id DESC LIMIT 1")
check("9 新一轮工单为新单号", new_no != order_no, f"{order_no} → {new_no}")

# 9 同 event_id 重发 → duplicated=true，不再出单
r2 = httpx.post(ADMIN + "/api/v1/events", json=[event],
                headers={"X-Device-Key": "edge-node-01-secret-2026"}, timeout=15)
dup = bool((r2.json().get("data") or [{}])[0].get("duplicated"))
ev3, wo3 = counts()
check("10 同 event_id 重发 duplicated=true 且不出单", dup and wo3 == wo2,
      f"dup={dup} 工单 {wo2}→{wo3}")

passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 通过 =====", flush=True)
