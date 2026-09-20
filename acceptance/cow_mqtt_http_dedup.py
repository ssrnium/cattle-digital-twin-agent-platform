# -*- coding: utf-8 -*-
"""MQTT 与 HTTP 统一幂等入口验证：同一 event_id 经两条路径到达，第二条必须 duplicated，不重复落库/告警。
运行：PSQL=... tools/pw-venv/Scripts/python.exe cow-digital-twin-platform/acceptance/cow_mqtt_http_dedup.py
前置：cow-admin(8081, MQTT_ENABLED=true)/Mosquitto(1883)/PG 在跑。
"""
import json, os, subprocess, sys, time, uuid, datetime
import httpx, paho.mqtt.client as mqtt

ADMIN = "http://127.0.0.1:8081"
PSQL = os.environ.get("PSQL", "psql")
RESULTS = []

def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(f'{"✓" if cond else "✗"} {name} {extra}', flush=True)

def psql(sql):
    r = subprocess.run([PSQL, "-U", "postgres", "-h", "127.0.0.1", "-d", "cow_db",
                        "-tAc", sql], capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

def count_eid(eid):
    return int(psql(f"SELECT count(*) FROM unified_event WHERE event_id='{eid}'") or 0)

def make_event(eid, etype="MOUNTING", cow="COW-0042"):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"schema_version": "1.0", "tenant_id": "t1", "farm_id": "farm-01",
            "event_id": eid, "cow_id": cow, "device_id": "edge-node-01",
            "event_type": etype, "event_time": now, "ingest_time": now,
            "quality": "GOOD", "confidence": 0.91, "model_version": "dedup-probe",
            "evidence_ref": "probe://dedup", "raw": {}}

def mqtt_pub(payload):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dedup-probe")
    c.connect("127.0.0.1", 1883, keepalive=10)
    c.loop_start()
    c.publish("farm/farm-01/event", json.dumps(payload, ensure_ascii=False), qos=1)
    time.sleep(1.5)
    c.loop_stop()
    c.disconnect()

def http_post(event):
    r = httpx.post(ADMIN + "/api/v1/events", json=[event],
                   headers={"X-Device-Key": "edge-node-01-secret-2026"}, timeout=15)
    return (r.json().get("data") or [{}])[0].get("duplicated")

# A：先 MQTT 后 HTTP（同 event_id）
eid_a = "DEDUP-MQTT-HTTP-" + uuid.uuid4().hex[:8]
ev_a = make_event(eid_a)
mqtt_pub(ev_a)
time.sleep(2)
check("A1 MQTT 路径入库", count_eid(eid_a) == 1, f"count={count_eid(eid_a)}")
dup_a = http_post(ev_a)
time.sleep(1)
check("A2 同 event_id 走 HTTP → duplicated", dup_a is True and count_eid(eid_a) == 1,
      f"dup={dup_a} count={count_eid(eid_a)}")

# B：先 HTTP 后 MQTT（同 event_id）
eid_b = "DEDUP-HTTP-MQTT-" + uuid.uuid4().hex[:8]
ev_b = make_event(eid_b)
dup_b0 = http_post(ev_b)
time.sleep(1)
check("B1 HTTP 路径入库", dup_b0 is False and count_eid(eid_b) == 1, f"count={count_eid(eid_b)}")
mqtt_pub(ev_b)
time.sleep(2)
check("B2 同 event_id 走 MQTT 不重复落库", count_eid(eid_b) == 1, f"count={count_eid(eid_b)}")

passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 通过 =====", flush=True)
