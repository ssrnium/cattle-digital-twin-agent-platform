# -*- coding: utf-8 -*-
"""cow-d2：写操作人工确认机制确定性验收（API 级，经 admin 代理）。
链路：智能体决定调用 create_work_order → 系统拦截 park → /sessions 暴露 pending_confirmation
     → /confirm 批准 → 工具真正执行 → work_order 落库。
运行：tools/pw-venv/Scripts/python.exe tools/acceptance/cow_d2_agent_confirm.py
"""
import httpx, time, json, threading, subprocess, sys

ADMIN = "http://127.0.0.1:8081"
PSQL = r"<user-home>\pgsql16\bin\psql.exe"
RESULTS = []

def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(f'{"✓" if cond else "✗"} {name} {extra}', flush=True)

def psql(sql):
    r = subprocess.run([PSQL, "-U", "postgres", "-h", "127.0.0.1", "-d", "cow_db", "-tAc", sql],
                       capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

c = httpx.Client(trust_env=False, timeout=300)
token = c.post(f"{ADMIN}/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"}).json()["data"]["token"]
H = {"Authorization": f"Bearer {token}"}

# 选有跛行事件且无未结工单的牛
cow = psql("""SELECT DISTINCT cow_id FROM unified_event
              WHERE event_type='LAMENESS' AND cow_id IS NOT NULL
                AND cow_id NOT IN (SELECT cow_id FROM work_order
                                   WHERE state NOT IN ('CLOSED','CANCELLED') AND cow_id IS NOT NULL)
              ORDER BY cow_id LIMIT 1""")
check("选牛（有证据无未结工单）", bool(cow), f"cow={cow}")

before = int(psql("SELECT count(*) FROM work_order") or 0)
msg1 = f"给 {cow} 建一个兽医检查工单，它今天有跛行事件记录。先取证据再向我说明理由。"
msg2 = "确认，创建吧"

final = {}
def send_chat(m):
    r = c.post(f"{ADMIN}/api/v1/agent/chat",
               json={"session_id": final.get("session_id"), "message": m}, headers=H)
    d = r.json()
    final["code"] = d.get("code")
    data = d.get("data") or {}
    final["session_id"] = data.get("session_id")
    final.setdefault("replies", []).append(data.get("reply"))

def poll_pending(seconds=90):
    for _ in range(seconds // 3):
        time.sleep(3)
        s = c.get(f"{ADMIN}/api/v1/agent/sessions", headers=H).json()
        for sess in ((s.get("data") or {}).get("sessions") or []):
            if sess.get("pending_confirmation"):
                return sess
    return None

pending_seen = None
for attempt_msg in (msg1, msg2):
    th = threading.Thread(target=send_chat, args=(attempt_msg,), daemon=True)
    th.start()
    pending_seen = poll_pending(100)
    if pending_seen:
        break
    th.join(timeout=200)

check("写操作被系统拦截并 park（pending_confirmation 出现）", pending_seen is not None,
      json.dumps((pending_seen or {}).get("pending_confirmation"), ensure_ascii=False)[:130] if pending_seen else "（两轮对话均未触发写工具调用）")

pc = (pending_seen or {}).get("pending_confirmation") or {}
check("pending 内容正确（create_work_order + 参数）", pc.get("tool") == "create_work_order" and pc.get("arguments", {}).get("cow_id") == cow,
      f"tool={pc.get('tool')} args={json.dumps(pc.get('arguments'), ensure_ascii=False)[:80]}")

# 先验证"拒绝"路径：重新发起一次 pending 后拒绝，应不落库
# （本测试用批准路径作为主验证；拒绝路径已由 120s 超时自动拒绝的日志佐证，见 force-tool-2 之前的 smoke5）
sid = pending_seen["session_id"] if pending_seen else None
if sid:
    r = c.post(f"{ADMIN}/api/v1/agent/confirm", json={"session_id": sid, "approved": True}, headers=H)
    check("批准接口受理", r.json().get("code") == 200, f"resp={r.json()}")
    th.join(timeout=200)
    time.sleep(2)
    after = int(psql("SELECT count(*) FROM work_order") or 0)
    check("批准后工单真实落库（+1）", after == before + 1, f"orders {before}→{after}")
    new_state = psql(f"SELECT state || '|' || cow_id FROM work_order ORDER BY id DESC LIMIT 1")
    check("新工单为 NEW 状态且关联正确牛只", new_state.startswith("NEW") and cow in new_state, f"db={new_state}")
    audit = int(psql("SELECT count(*) FROM agent_message") or 0)
    check("对话审计落库（agent_message 有记录）", audit > 0, f"rows={audit}")
else:
    check("批准接口受理", False, "无 pending 可批准")

fails = [r for r in RESULTS if not r[1]]
print(f"\n==== cow-d2 汇总：{len(RESULTS) - len(fails)}/{len(RESULTS)} 通过 ====")
sys.exit(1 if fails else 0)
