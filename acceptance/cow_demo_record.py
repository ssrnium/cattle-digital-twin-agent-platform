# -*- coding: utf-8 -*-
"""奶牛平台演示视频录制（Playwright recordVideo → webm）。
运行：tools/pw-venv/Scripts/python.exe cow-digital-twin-platform/acceptance/cow_demo_record.py
前置：cow-admin(8081)/cow-web(5174)/cow-agent(8003)/PG/Redis 在跑。
"""
import time, pathlib
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5174"
OUT = pathlib.Path(__file__).parent.parent.parent / "tmp_extract" / "cow_demo_raw"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 720},
                              record_video_dir=str(OUT), record_video_size={"width": 1280, "height": 720},
                              locale="zh-CN")
    page = ctx.new_page()
    page.set_default_timeout(20000)

    # 登录
    page.goto(BASE + "/login", wait_until="networkidle")
    time.sleep(2.5)
    page.fill('input[placeholder^="用户名"]', "admin")
    page.fill('input[placeholder="密码"]', "Admin@123")
    page.click(".login-btn")
    page.wait_for_url("**/dashboard", timeout=15000)
    time.sleep(4)

    # 3D 牛棚：旋转 + 选牛 + 详情
    page.goto(BASE + "/barn", wait_until="networkidle")
    page.wait_for_selector("canvas", timeout=30000)
    time.sleep(3)
    box = page.locator("canvas").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(cx, cy); page.mouse.down()
    page.mouse.move(cx + 220, cy + 40, steps=25); page.mouse.up()
    time.sleep(1.5)
    # 网格扫描点击选牛（命中即出个体卡片）
    picked = False
    for fx in (0.42, 0.5, 0.58, 0.36, 0.64, 0.46, 0.54):
        for fy in (0.42, 0.5, 0.58):
            page.mouse.click(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
            time.sleep(0.5)
            if page.locator('button:has-text("查看详情")').count():
                picked = True
                break
        if picked:
            break
    print(f"选牛命中: {picked}", flush=True)
    time.sleep(2)
    if picked:
        page.click('button:has-text("查看详情")')
        page.wait_for_url("**/cow/detail/**", timeout=10000)
        time.sleep(3.5)

    # 设备页
    page.goto(BASE + "/device", wait_until="networkidle")
    time.sleep(3.5)

    # AI 助手真实对话
    page.goto(BASE + "/assistant", wait_until="networkidle")
    time.sleep(2)
    ta = page.locator('textarea')
    ta.fill("COW-0042 今天什么情况？")
    time.sleep(0.5)
    page.click('button:has-text("发送")')
    # 等 thinking 出现再等回复（LLM 真实调用，放宽 150s）
    got_reply = False
    for _ in range(150):
        if page.locator('.el-button:has-text("批准")').count():
            break
        sending = page.locator('button:has-text("发送")').first
        # 回复出现判定：气泡区出现 tool trace 或 tokens 行
        if page.locator("text=/tokens?/i").count() > 0:
            got_reply = True
            break
        time.sleep(1)
    print(f"助手回复: {got_reply}", flush=True)
    time.sleep(4)

    # 工单看板收尾
    page.goto(BASE + "/task", wait_until="networkidle")
    time.sleep(3)

    ctx.close()
    browser.close()

vids = sorted(OUT.glob("*.webm"), key=lambda p: p.stat().st_mtime)
print("视频:", vids[-1] if vids else "未生成", flush=True)
