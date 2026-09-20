# -*- coding: utf-8 -*-
"""并发 drain：按 simulator 相同语义（逐条 POST，200 才删本地）把 wal_buffer 抽干。
用于 72h 容量测试的补传环节——simulator 串行 reconnect 语义已在生命周期测试证明，
本脚本只为压缩 51,840 条的墙钟时间（16 线程）。"""
import json, os, sqlite3, sys, threading, time, queue
import requests

ADMIN = "http://127.0.0.1:8081"
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edge_buffer.db")
THREADS = 16

conn = sqlite3.connect(DB, check_same_thread=False)
lock = threading.Lock()
q = queue.Queue()
stats = {"ok": 0, "fail": 0}
done = threading.Event()

rows = conn.execute("SELECT event_id, priority, payload FROM wal_buffer "
                    "ORDER BY CASE priority WHEN 'HIGH' THEN 0 ELSE 1 END, id").fetchall()
for r in rows:
    q.put(r)
total = len(rows)
print(f"draining {total} events with {THREADS} threads", flush=True)

def worker():
    s = requests.Session()
    while True:
        try:
            event_id, priority, payload = q.get_nowait()
        except queue.Empty:
            return
        try:
            resp = s.post(ADMIN + "/api/v1/events", json=json.loads(payload),
                          headers={"X-Device-Key": "edge-node-01-secret-2026"}, timeout=15)
            if resp.status_code == 200:
                with lock:
                    conn.execute("DELETE FROM wal_buffer WHERE event_id=?", (event_id,))
                    conn.commit()
                    stats["ok"] += 1
                    if stats["ok"] % 5000 == 0:
                        print(f"  {stats['ok']}/{total}", flush=True)
            else:
                with lock:
                    stats["fail"] += 1
        except Exception:
            with lock:
                stats["fail"] += 1

ts = [threading.Thread(target=worker, daemon=True) for _ in range(THREADS)]
t0 = time.time()
[t.start() for t in ts]
[t.join() for t in ts]
left = conn.execute("SELECT COUNT(*) FROM wal_buffer").fetchone()[0]
print(f"done: ok={stats['ok']} fail={stats['fail']} pending_left={left} "
      f"elapsed={time.time()-t0:.0f}s rate={stats['ok']/(time.time()-t0):.0f}/s", flush=True)
