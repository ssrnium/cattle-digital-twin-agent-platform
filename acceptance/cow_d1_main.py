# -*- coding: utf-8 -*-
"""奶牛平台浏览器级主链路验收：登录→看板→牛棚孪生图→单牛时间线→事件流→工单状态机→设备→AI助手（含写操作审批）。
运行：tools/pw-venv/Scripts/python.exe tools/acceptance/cow_d1_main.py
前置：PG(cow_db)/Redis/mosquitto/cow-admin(8081,MQTT开)/cow-ai(8001)/cow-agent(8003)/cow-web(5174) 全部在跑，
     且 simulator 已产生过事件（库内有事件/工单/孪生数据）。
"""
import subprocess, sys, time, pathlib, os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5174"
SHOTS = pathlib.Path(__file__).parent.parent / "logs" / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)
PSQL = os.environ.get("PSQL", "psql")  # 便携 PostgreSQL 可用环境变量指定全路径

RESULTS = []
def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(f'{"✓" if cond else "✗"} {name} {extra}', flush=True)

def psql(sql):
    r = subprocess.run([PSQL, "-U", "postgres", "-h", "127.0.0.1", "-d", "cow_db", "-tAc", sql],
                       capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

def login(page, u, p):
    page.goto(BASE + "/login", wait_until="networkidle")
    page.fill('input[placeholder^="用户名"]', u)
    page.fill('input[placeholder="密码"]', p)
    page.locator('button:has-text("登")').first.click()
    page.wait_for_url("**/dashboard", timeout=15000)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1500, "height": 900}, locale="zh-CN").new_page()

    # 1. 未登录重定向 + 登录
    page.goto(BASE + "/barn", wait_until="networkidle")
    check("1 未登录重定向登录页", "/login" in page.url, page.url)
    login(page, "admin", "Admin@123")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    body = page.locator("body").inner_text()
    check("2 登录成功+看板数据", "103" in body, "看板含牛总数 103")
    page.screenshot(path=str(SHOTS / "cow-02-dashboard.png"))

    # 3. 牛棚二维孪生图：103 圆点 + 图例 + 状态变色
    page.goto(BASE + "/barn", wait_until="networkidle")
    page.wait_for_selector(".cow-dot", timeout=15000)
    dots = page.locator(".cow-dot").count()
    check("3 牛棚图 103 头牛圆点", dots == 103, f"dots={dots}")
    colors = page.eval_on_selector_all(".cow-dot", "els => els.map(e => e.getAttribute('fill'))")
    colored = len([c for c in colors if c in ("#e6a23c", "#f56c6c")])
    check("3b 存在异常状态变色牛（发情橙/跛行红）", colored > 0, f"异常色圆点={colored}")
    page.screenshot(path=str(SHOTS / "cow-03-barn.png"))

    # 4. 单牛详情 + 时间线（点红/橙牛或任意牛）
    page.locator(".cow-dot").nth(8).click()
    page.wait_for_selector(".el-timeline", timeout=15000)
    body = page.locator("body").inner_text()
    tl = page.locator(".el-timeline-item").count()
    check("4 单牛详情+孪生状态+时间线", ("COW-" in body and tl >= 1), f"timeline_items={tl}")
    page.screenshot(path=str(SHOTS / "cow-04-cow-detail.png"))

    # 5. 事件流页
    page.goto(BASE + "/event", wait_until="networkidle")
    time.sleep(1.5)
    body = page.locator("body").inner_text()
    check("5 事件流含 MOUNTING/LAMENESS", ("MOUNTING" in body or "爬跨" in body), "")
    page.screenshot(path=str(SHOTS / "cow-05-events.png"))

    # 6. 工单状态机全流程（NEW→DISPATCHED→PROCESSING→PENDING_REVIEW→CLOSED）
    page.goto(BASE + "/task", wait_until="networkidle")
    time.sleep(1.5)
    page.locator('.el-table__row button:has-text("分派")').first.click()
    page.wait_for_selector(".el-dialog", timeout=8000)
    page.locator(".el-dialog .el-select__wrapper").click()
    time.sleep(0.8)
    # headless 下 el-select 弹层 popper 定位失效（0x0），改键盘选择第一项
    page.keyboard.press("ArrowDown")
    time.sleep(0.3)
    page.keyboard.press("Enter")
    time.sleep(0.3)
    order_no = page.locator(".el-table__row").first.locator("td").nth(0).inner_text()
    page.locator('.el-dialog button:has-text("确定")').click()
    time.sleep(1.2)
    st = psql(f"SELECT state FROM work_order WHERE order_no='{order_no}'")
    check("6a 分派 → DISPATCHED", st == "DISPATCHED", f"order={order_no} state={st}")

    page.locator('.el-tabs__item:has-text("已分派")').click()
    time.sleep(1.2)
    page.locator('.el-table__row', has_text=order_no).locator('button:has-text("开始处理")').click()
    time.sleep(1.2)
    st = psql(f"SELECT state FROM work_order WHERE order_no='{order_no}'")
    check("6b 开始处理 → PROCESSING", st == "PROCESSING", f"state={st}")

    page.locator('.el-tabs__item:has-text("处理中")').click()
    time.sleep(1.2)
    page.locator('.el-table__row', has_text=order_no).locator('button:has-text("提交复查")').click()
    page.wait_for_selector(".el-dialog textarea", timeout=8000)
    page.fill(".el-dialog textarea", "已现场检查，步态评分 2 分，建议观察三天（验收测试）")
    page.locator('.el-dialog button:has-text("提交")').click()
    time.sleep(1.2)
    st = psql(f"SELECT state FROM work_order WHERE order_no='{order_no}'")
    check("6c 提交复查 → PENDING_REVIEW", st == "PENDING_REVIEW", f"state={st}")

    page.locator('.el-tabs__item:has-text("待复查")').click()
    time.sleep(1.2)
    page.locator('.el-table__row', has_text=order_no).locator('button:has-text("复查通过")').click()
    page.wait_for_selector(".el-message-box", timeout=8000)
    page.locator(".el-message-box__btns .el-button--primary").click()
    time.sleep(1.2)
    st = psql(f"SELECT state FROM work_order WHERE order_no='{order_no}'")
    ver = psql(f"SELECT version FROM work_order WHERE order_no='{order_no}'")
    check("6d 复查通过 → CLOSED（乐观锁 version 递增）", st == "CLOSED" and int(ver or 0) >= 4, f"state={st} version={ver}")
    page.screenshot(path=str(SHOTS / "cow-06-task-closed.png"))

    # 7. 设备页
    page.goto(BASE + "/device", wait_until="networkidle")
    time.sleep(1.5)
    body = page.locator("body").inner_text()
    check("7 设备页 edge-node-01 在线", ("edge-node-01" in body and "在线" in body), "")
    page.screenshot(path=str(SHOTS / "cow-07-devices.png"))

    # 8. AI 助手：查询类（只读工具）+ 写操作审批
    page.goto(BASE + "/assistant", wait_until="networkidle")
    page.fill(".input-bar textarea", "COW-0009 今天什么情况？")
    page.locator('.input-bar button:has-text("发送")').click()
    page.wait_for_function("""() => {
      const rows = document.querySelectorAll('.msg-row.assistant .content');
      if (!rows.length) return false;
      const t = rows[rows.length-1].innerText;
      return t.length > 20 && !t.includes('思考中');
    }""", timeout=240000)
    time.sleep(1.5)
    body = page.locator(".chat-card").inner_text()
    check("8a 智能体回答（真实内容）", "COW-0009" in body and "思考中" not in body, "")
    page.screenshot(path=str(SHOTS / "cow-08a-agent-answer.png"))

    # 8b. 写操作审批流：以"消息行数增加 + 按钮 loading 消失"为准，杜绝发送竞态丢消息
    def msg_count():
        return page.locator(".msg-row").count()

    def send_and_wait(text, prev, timeout=240000):
        page.fill(".input-bar textarea", text)
        page.locator('.input-bar button:has-text("发送")').click()
        page.wait_for_function(
            f"() => document.querySelectorAll('.msg-row').length >= {prev + 2} "
            f"&& !document.querySelector('.input-bar button.is-loading')",
            timeout=timeout)
        time.sleep(1)

    n0 = msg_count()
    # 选"有跛行事件证据、但无未结工单"的牛——让建单有据可依且不与 24h 去重冲突
    free_cow = psql("""SELECT DISTINCT cow_id FROM unified_event
                       WHERE event_type='LAMENESS' AND cow_id IS NOT NULL
                         AND cow_id NOT IN (SELECT cow_id FROM work_order
                                            WHERE state NOT IN ('CLOSED','CANCELLED') AND cow_id IS NOT NULL)
                       ORDER BY cow_id LIMIT 1""")
    check("8b0 找到有证据且无未结工单的牛", bool(free_cow), f"cow={free_cow}")
    send_and_wait(f"给 {free_cow} 建一个兽医检查工单——它今天有跛行事件记录，依据充分，备注：步态待复查（验收测试）", n0)
    n1 = msg_count()
    # 关键时序：发送"确认创建"后 chat 会 park 在审批上（120s 内不返回），
    # 不能等对话完成——必须直接在弹窗出现时批准（真实用户操作时序）
    page.fill(".input-bar textarea", "确认创建")
    page.locator('.input-bar button:has-text("发送")').click()
    try:
        page.wait_for_selector(".el-dialog >> text=批准执行", timeout=240000)
    except Exception:
        # 智能体先补了一段说明（chat 已返回）才调工具：再确认一次
        page.wait_for_function(
            f"() => document.querySelectorAll('.msg-row').length >= {n1 + 2} "
            f"&& !document.querySelector('.input-bar button.is-loading')", timeout=240000)
        n2 = msg_count()
        page.fill(".input-bar textarea", "确认执行")
        page.locator('.input-bar button:has-text("发送")').click()
        page.wait_for_selector(".el-dialog >> text=批准执行", timeout=240000)
    check("8b 写操作审批弹窗出现", True, "")
    page.screenshot(path=str(SHOTS / "cow-08b-agent-confirm.png"))
    before_orders = int(psql("SELECT count(*) FROM work_order") or 0)
    page.locator('.el-dialog button:has-text("批准执行")').click()
    # 批准后以 DB 轮询为准（工具执行→工单落库），不依赖回复气泡的行数时序
    after_orders = before_orders
    for _ in range(40):
        time.sleep(3)
        after_orders = int(psql("SELECT count(*) FROM work_order") or 0)
        if after_orders > before_orders:
            break
    check("8c 批准后工单真实创建", after_orders == before_orders + 1, f"orders {before_orders}→{after_orders}")
    page.screenshot(path=str(SHOTS / "cow-08c-agent-done.png"))

    browser.close()

fails = [r for r in RESULTS if not r[1]]
print(f"\n==== 奶牛 D1 汇总：{len(RESULTS) - len(fails)}/{len(RESULTS)} 通过 ====")
for n, c, e in fails:
    print(f"未过项: {n} {e}")
sys.exit(1 if fails else 0)
