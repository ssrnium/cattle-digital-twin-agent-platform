# -*- coding: utf-8 -*-
"""设备心跳在线翻转实证：初始 OFFLINE → 心跳后 ONLINE → 停跳 60s+ 后回 OFFLINE。
运行：tools/pw-venv/Scripts/python.exe cow-digital-twin-platform/acceptance/cow_device_flip.py
前置：cow-admin(8081)/cow-web(5174)/PG/Redis 在跑。
"""
import json, time, pathlib, urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5174"
API = "http://127.0.0.1:8081"
SHOTS = pathlib.Path(__file__).parent.parent.parent / "tmp_extract" / "cow_flip"
SHOTS.mkdir(parents=True, exist_ok=True)

def heartbeat():
    req = urllib.request.Request(
        API + "/api/v1/devices/heartbeat",
        data=json.dumps({"device_id": "edge-node-01", "deviceKey": "edge-node-01-secret-2026",
                         "pending_count": 0}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def device_state():
    req = urllib.request.Request(API + "/api/v1/devices/heartbeat".replace("/heartbeat", ""),
                                 headers={"Authorization": "Bearer " + TOKEN})
    with urllib.request.urlopen(req, timeout=10) as r:
        devs = json.loads(r.read())["data"]
    return [d for d in devs if d["deviceId"] == "edge-node-01"][0]

# 先登录拿 token（设备列表需 JWT）
req = urllib.request.Request(API + "/api/v1/auth/login",
                             data=json.dumps({"username": "admin", "password": "Admin@123"}).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=10) as r:
    TOKEN = json.loads(r.read())["data"]["token"]

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 900})
    page.goto(BASE + "/login", wait_until="networkidle")
    page.fill('input[placeholder^="用户名"]', "admin")
    page.fill('input[placeholder="密码"]', "Admin@123")
    page.click('button:has-text("进入控制中心"), .login-btn')
    page.wait_for_url("**/dashboard", timeout=15000)

    page.goto(BASE + "/device", wait_until="networkidle")
    time.sleep(2)

    s0 = device_state()
    print(f'初始状态: {s0["onlineStatus"]} 离线时长={s0.get("offlineSeconds")}s', flush=True)
    page.screenshot(path=str(SHOTS / "flip_1_initial.png"))
    assert s0["onlineStatus"] == "OFFLINE", "预期初始 OFFLINE（上次心跳很久以前）"

    heartbeat()
    print("已发心跳，等待页面 10s 轮询翻转…", flush=True)
    t0 = time.time()
    while time.time() - t0 < 25:
        if device_state()["onlineStatus"] == "ONLINE":
            break
        time.sleep(3)
    page.reload(wait_until="networkidle")
    time.sleep(2)
    s1 = device_state()
    print(f'心跳后状态: {s1["onlineStatus"]}', flush=True)
    page.screenshot(path=str(SHOTS / "flip_2_online.png"))
    assert s1["onlineStatus"] == "ONLINE", "心跳后应为 ONLINE"

    print("停止心跳，等待 70s（>60s 阈值）…", flush=True)
    time.sleep(70)
    page.reload(wait_until="networkidle")
    time.sleep(2)
    s2 = device_state()
    print(f'70s 后状态: {s2["onlineStatus"]} 离线时长={s2.get("offlineSeconds")}s', flush=True)
    page.screenshot(path=str(SHOTS / "flip_3_offline.png"))
    assert s2["onlineStatus"] == "OFFLINE" and (s2.get("offlineSeconds") or 0) >= 60, "应为 OFFLINE 且带离线时长"

    browser.close()

print("PASS: OFFLINE→ONLINE→OFFLINE 翻转实证完成", flush=True)
