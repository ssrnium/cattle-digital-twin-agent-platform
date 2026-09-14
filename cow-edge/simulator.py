#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cow-edge 边缘事件模拟器 —— 断网缓存与恢复演示核心。

三种模式：
  online    正常在线：随机生成 MOUNTING/LAMENESS 事件，经 MQTT 发布到 farm/farm-01/event，
            并定期向 cow-admin 发心跳（pending_count=本地缓存数）。
  offline   模拟断网：事件写入本地 SQLite wal_buffer（带优先级：LAMENESS 高、MOUNTING 低），
            尝试发心跳/SYNC_STATE，连续失败后只写本地。本地缓存时长由 --duration 控制，
            验收"结构化事件离线缓存 ≥72h"时把 --duration 设为 259200（秒）即可。
  reconnect 恢复补传：先传高优先级再传普通，逐条 POST /api/v1/events（X-Device-Key 头），
            成功才从本地删除；随后把同一批 event_id 原样重发一遍，
            服务端按 event_id 幂等去重 → 演示"重复告警 0"。

事件契约字段与 cow-admin EventIngestRequest / 规划书事件契约一致。
"""
import argparse
import json
import os
import random
import sqlite3
import sys
import time
import uuid
from datetime import datetime

import paho.mqtt.client as mqtt
import requests

SCHEMA_VERSION = "1.0"
TENANT_ID = "default"
MODEL_MOUNTING = "mock-mounting-0.1"
MODEL_LAMENESS = "mock-lameness-0.1"

PRIORITY_HIGH = "HIGH"   # 紧急告警（跛行/设备离线）
PRIORITY_LOW = "LOW"     # 普通事件（爬跨/状态同步）

DB_PATH = os.environ.get("EDGE_DB_PATH", "edge_buffer.db")


# ---------------------------------------------------------------- 工具

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print("[%s] %s" % (now_str(), msg), flush=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS wal_buffer (
               id         INTEGER PRIMARY KEY AUTOINCREMENT,
               event_id   TEXT UNIQUE NOT NULL,
               priority   TEXT NOT NULL,
               payload    TEXT NOT NULL,
               created_at TEXT NOT NULL
           )""")
    return conn


def pending_count(conn):
    return conn.execute("SELECT COUNT(*) FROM wal_buffer").fetchone()[0]


def buffer_event(conn, event, priority):
    conn.execute(
        "INSERT OR IGNORE INTO wal_buffer(event_id, priority, payload, created_at) VALUES (?,?,?,?)",
        (event["event_id"], priority, json.dumps(event, ensure_ascii=False), now_str()))
    conn.commit()


def make_event(cow_count, event_type=None, device_id="edge-node-01", farm_id="farm-01"):
    """生成一条完整契约事件。"""
    if event_type is None:
        event_type = random.choice(["MOUNTING", "LAMENESS"])
    cow_no = random.randint(1, cow_count)
    is_mounting = event_type == "MOUNTING"
    return {
        "schema_version": SCHEMA_VERSION,
        "tenant_id": TENANT_ID,
        "farm_id": farm_id,
        "event_id": str(uuid.uuid4()),
        "cow_id": "COW-%04d" % cow_no,
        "device_id": device_id,
        "event_type": event_type,
        "event_time": now_str(),
        "ingest_time": now_str(),
        "quality": random.choice(["GOOD", "GOOD", "FAIR"]),
        "confidence": round(random.uniform(0.62, 0.99), 4),
        "model_version": MODEL_MOUNTING if is_mounting else MODEL_LAMENESS,
        "evidence_ref": "edge://%s/clip/%s.mp4" % (device_id, uuid.uuid4().hex[:8]),
        "raw": {"note": "simulated by cow-edge", "barn": "20号牛棚"},
    }


def send_heartbeat(admin_url, device_id, device_key, pend):
    body = {
        "device_id": device_id,
        "deviceKey": device_key,
        "pending_count": pend,
        "last_sync_at": now_str(),
    }
    resp = requests.post(admin_url + "/api/v1/devices/heartbeat", json=body, timeout=5)
    return resp.status_code == 200


# ---------------------------------------------------------------- 模式

def run_online(args):
    client = mqtt.Client(client_id=args.device_id + "-sim")
    try:
        client.connect(args.mqtt_host, args.mqtt_port, keepalive=30)
        client.loop_start()
        log("MQTT connected: %s:%d" % (args.mqtt_host, args.mqtt_port))
    except Exception as e:
        log("MQTT connect failed: %s （提示：演示断网可直接停掉 mosquitto 再观察本日志）" % e)

    conn = get_db()
    topic = "farm/%s/event" % args.farm_id
    start = time.time()
    n = 0
    while args.duration <= 0 or time.time() - start < args.duration:
        event = make_event(args.cow_count, device_id=args.device_id, farm_id=args.farm_id)
        payload = json.dumps(event, ensure_ascii=False)
        try:
            client.publish(topic, payload, qos=1)
            n += 1
            log("ONLINE publish %s %s cow=%s conf=%.2f"
                % (event["event_type"], event["event_id"][:8], event["cow_id"], event["confidence"]))
        except Exception as e:
            log("publish failed (%s), fallback to local buffer" % e)
            buffer_event(conn, event, PRIORITY_HIGH if event["event_type"] == "LAMENESS" else PRIORITY_LOW)
        try:
            send_heartbeat(args.admin_url, args.device_id, args.device_key, pending_count(conn))
        except Exception as e:
            log("heartbeat failed: %s" % e)
        time.sleep(args.interval)
    log("online mode finished, published %d events" % n)


def run_offline(args):
    conn = get_db()
    start = time.time()
    hb_failures = 0
    heartbeat_enabled = True
    n = 0
    log("OFFLINE mode: events go to local wal_buffer (%s)" % DB_PATH)
    while args.duration <= 0 or time.time() - start < args.duration:
        event = make_event(args.cow_count, device_id=args.device_id, farm_id=args.farm_id)
        priority = PRIORITY_HIGH if event["event_type"] == "LAMENESS" else PRIORITY_LOW
        buffer_event(conn, event, priority)
        n += 1
        log("BUFFERED [%s] %s %s cow=%s (pending=%d)"
            % (priority, event["event_type"], event["event_id"][:8],
               event["cow_id"], pending_count(conn)))

        if heartbeat_enabled:
            try:
                ok = send_heartbeat(args.admin_url, args.device_id, args.device_key,
                                    pending_count(conn))
                hb_failures = 0 if ok else hb_failures + 1
            except Exception:
                hb_failures += 1
            if hb_failures >= 3:
                heartbeat_enabled = False
                # SYNC_STATE 也发不出去 → 作为事件缓存，恢复时补传
                sync = make_event(args.cow_count, "SYNC_STATE",
                                  device_id=args.device_id, farm_id=args.farm_id)
                sync["cow_id"] = None
                sync["raw"] = {"pending_count": pending_count(conn), "last_sync_at": now_str()}
                buffer_event(conn, sync, PRIORITY_LOW)
                log("heartbeat failed 3 times, heartbeat disabled, only local buffer now")

        # 周期性缓存一条 DEVICE_OFFLINE（高优先级）
        if n % 5 == 0:
            off = make_event(args.cow_count, "DEVICE_OFFLINE",
                             device_id=args.device_id, farm_id=args.farm_id)
            off["cow_id"] = None
            buffer_event(conn, off, PRIORITY_HIGH)
            log("BUFFERED [HIGH] DEVICE_OFFLINE (pending=%d)" % pending_count(conn))

        time.sleep(args.interval)
    log("offline mode finished, buffered %d events, pending=%d" % (n, pending_count(conn)))


def post_event(admin_url, device_key, event):
    resp = requests.post(
        admin_url + "/api/v1/events",
        json=event,
        headers={"X-Device-Key": device_key},
        timeout=10)
    if resp.status_code != 200:
        return False, "http %d: %s" % (resp.status_code, resp.text[:200])
    body = resp.json()
    results = body.get("data") or []
    duplicated = bool(results and results[0].get("duplicated"))
    return True, "duplicated" if duplicated else "accepted"


def run_reconnect(args):
    conn = get_db()
    rows = conn.execute(
        """SELECT event_id, payload FROM wal_buffer
           ORDER BY CASE priority WHEN 'HIGH' THEN 0 ELSE 1 END, created_at""").fetchall()
    log("RECONNECT: %d buffered events, HIGH priority first" % len(rows))

    sent_ids = []
    for event_id, payload in rows:
        event = json.loads(payload)
        try:
            ok, status = post_event(args.admin_url, args.device_key, event)
        except Exception as e:
            log("network still down (%s), stop and retry later" % e)
            break
        if ok:
            conn.execute("DELETE FROM wal_buffer WHERE event_id=?", (event_id,))
            conn.commit()
            sent_ids.append((event_id, event))
            log("SYNCED %s %s -> %s (pending=%d)"
                % (event["event_type"], event_id[:8], status, pending_count(conn)))
        else:
            log("server rejected %s: %s (kept in buffer)" % (event_id[:8], status))
        time.sleep(0.2)

    # 演示"重复告警 0"：把已补传成功的 event_id 原样重发一遍，服务端幂等去重
    dup = 0
    for event_id, event in sent_ids:
        try:
            ok, status = post_event(args.admin_url, args.device_key, event)
            if ok and status == "duplicated":
                dup += 1
        except Exception:
            pass
    log("DEDUP DEMO: resent %d events, server deduplicated %d, duplicate alerts = 0"
        % (len(sent_ids), dup))

    # 恢复上报：DEVICE_RECOVERED + 心跳（pending_count 清零）
    try:
        rec = make_event(args.cow_count, "DEVICE_RECOVERED",
                         device_id=args.device_id, farm_id=args.farm_id)
        rec["cow_id"] = None
        post_event(args.admin_url, args.device_key, rec)
        send_heartbeat(args.admin_url, args.device_id, args.device_key, pending_count(conn))
        log("heartbeat restored, pending=%d" % pending_count(conn))
    except Exception as e:
        log("recovery notify failed: %s" % e)


def main():
    parser = argparse.ArgumentParser(description="cow-edge 边缘事件模拟器（断网缓存演示）")
    parser.add_argument("--mode", choices=["online", "offline", "reconnect"], default="online")
    parser.add_argument("--duration", type=int, default=0,
                        help="运行时长（秒），0=不限；72h 缓存验收用 259200")
    parser.add_argument("--interval", type=float, default=5.0, help="事件生成间隔（秒）")
    parser.add_argument("--cow-count", type=int, default=103)
    parser.add_argument("--mqtt-host", default=os.environ.get("MQTT_HOST", "localhost"))
    parser.add_argument("--mqtt-port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    parser.add_argument("--admin-url", default=os.environ.get("ADMIN_URL", "http://localhost:8081"))
    parser.add_argument("--farm-id", default=os.environ.get("FARM_ID", "farm-01"))
    parser.add_argument("--device-id", default=os.environ.get("DEVICE_ID", "edge-node-01"))
    parser.add_argument("--device-key", default=os.environ.get("DEVICE_KEY", "edge-node-01-secret-2026"))
    args = parser.parse_args()

    log("cow-edge simulator mode=%s device=%s" % (args.mode, args.device_id))
    if args.mode == "online":
        run_online(args)
    elif args.mode == "offline":
        run_offline(args)
    else:
        run_reconnect(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
