# -*- coding: utf-8 -*-
"""72h 离线缓存容量与断点续传实测。
口径：1 设备 × 1 事件/5s × 72h = 51,840 条（主体 SYNC_STATE LOW，每 5 条 1 条 DEVICE_OFFLINE HIGH）。
三组验证：①等量容量灌库（吞吐/体积/分布）②断点续传（杀进程重跑，成功才删）③幂等（全量唯一 + 抽样重发全 duplicated）。
运行：PSQL=... tools/pw-venv/Scripts/python.exe cow-digital-twin-platform/acceptance/cow_72h_capacity.py
前置：cow-admin(8081)/PG 在跑。预计 8-12 分钟。
"""
import json, os, subprocess, sys, time, pathlib, signal
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "cow-edge"))
import simulator as sim  # noqa: E402

PSQL = os.environ.get("PSQL", "psql")
ADMIN = "http://127.0.0.1:8081"
EDGE = pathlib.Path(__file__).parent.parent / "cow-edge"
TOTAL = 51840          # 72h × 1 事件/5s × 1 设备
MARK = "cap72h"
RESULTS = []

def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(f'{"✓" if cond else "✗"} {name} {extra}', flush=True)

def psql(sql):
    r = subprocess.run([PSQL, "-U", "postgres", "-h", "127.0.0.1", "-d", "cow_db",
                        "-tAc", sql], capture_output=True, text=True, timeout=60)
    return r.stdout.strip()

def server_count():
    return int(psql(f"SELECT count(*) FROM unified_event WHERE model_version='{MARK}'") or 0)

# 0 清场（simulator 的 DB_PATH 是相对路径，统一在 cow-edge 目录下工作）
os.chdir(EDGE)
old, bak = EDGE / "edge_buffer.db", EDGE / "edge_buffer.bak.db"
if bak.exists():
    bak.unlink()
if old.exists():
    old.rename(bak)
base = server_count()

# 1 等量容量灌库
conn = sim.get_db()
t0 = time.time()
n_high = 0
for n in range(1, TOTAL + 1):
    if n % 5 == 0:
        ev = sim.make_event(103, "DEVICE_OFFLINE")
        ev["cow_id"] = None
        ev["model_version"] = MARK
        sim.buffer_event(conn, ev, sim.PRIORITY_HIGH)
        n_high += 1
    else:
        ev = sim.make_event(103, "SYNC_STATE")
        ev["cow_id"] = None
        ev["model_version"] = MARK
        sim.buffer_event(conn, ev, sim.PRIORITY_LOW)
secs = time.time() - t0
pend = sim.pending_count(conn)
size_mb = (EDGE / "edge_buffer.db").stat().st_size / 1048576
check("1a 等量灌库 51,840 条", pend == TOTAL, f"{pend} 条, {secs:.0f}s ({TOTAL/secs:.0f} 条/s)")
check("1b 缓存体积可估算", size_mb > 5, f"{size_mb:.1f} MB（≈{size_mb*1048576/TOTAL:.0f} B/条）")
check("1c HIGH/LOW 分布", n_high == TOTAL // 5, f"HIGH={n_high} LOW={TOTAL-n_high}")

# 2 断点续传：先杀一轮，再跑完
p1 = subprocess.Popen([sys.executable, "simulator.py", "--mode", "reconnect", "--admin-url", ADMIN],
                      cwd=EDGE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(5)
p1.kill()
p1.wait(timeout=10)
time.sleep(1)
c1 = server_count() - base
check("2a 断点：第一轮补传被中断", 0 < c1 < TOTAL, f"已入库 {c1} 条")

p2 = subprocess.run([sys.executable, "simulator.py", "--mode", "reconnect", "--admin-url", ADMIN],
                    cwd=EDGE, capture_output=True, text=True, timeout=1500)
log2 = p2.stdout + p2.stderr
time.sleep(2)
c2 = server_count() - base
pend2 = sim.pending_count(sim.get_db())
check("2b 断点续传至清空", c2 == TOTAL and pend2 == 0, f"服务端 {c2}/{TOTAL}, 本地 pending={pend2}")

# 3 幂等：唯一性 + 抽样重发
uniq = int(psql(f"SELECT count(DISTINCT event_id) FROM unified_event WHERE model_version='{MARK}'") or 0)
check("3a 服务端 event_id 零重复", uniq == TOTAL, f"distinct={uniq}/{TOTAL}")
sample = psql(f"SELECT payload FROM unified_event WHERE model_version='{MARK}' LIMIT 20")
import requests as rq
dup_ok = 0
for line in sample.splitlines():
    ev = json.loads(line)
    r = rq.post(ADMIN + "/api/v1/events", json=[ev],
                headers={"X-Device-Key": "edge-node-01-secret-2026"}, timeout=15)
    if (r.json().get("data") or [{}])[0].get("duplicated"):
        dup_ok += 1
check("3b 抽样 20 条重发全部 duplicated", dup_ok == 20, f"{dup_ok}/20")

passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"\n===== {passed}/{len(RESULTS)} 通过 =====", flush=True)
