"""审批下沉（PENDING_ACTION）cow-agent 侧：park 注册 / fail-closed / 超时作废 / X-Action-Id 透传。"""
import asyncio
import json

import httpx
import pytest

from app import cow_tools
from app.agent_manager import AgentManager

WRITE_MSG = json.dumps({
    "kind": "cow_write",
    "tool": "create_work_order",
    "arguments": {"type": "VET_CHECK", "cow_id": "COW-0042", "description": "跛行复核"},
}, ensure_ascii=False)


def run(coro):
    return asyncio.run(coro)


class _ActionVarStub:
    """替代 ContextVar，记录 set 调用（跨 task 不可见，单测内直接断言）。"""

    def __init__(self):
        self.value = None

    def set(self, v):
        self.value = v

    def get(self):
        return self.value


@pytest.fixture
def action_stub(monkeypatch):
    stub = _ActionVarStub()
    monkeypatch.setattr(cow_tools, "current_action_id", stub)
    return stub


def test_park_registers_action_then_approve(monkeypatch, action_stub):
    registered = {}

    async def fake_register(session_id, tool, arguments):
        registered.update(session_id=session_id, tool=tool, arguments=arguments)
        return "act-0001"

    monkeypatch.setattr(cow_tools, "register_action", fake_register)
    manager = AgentManager()

    async def scenario():
        task = asyncio.create_task(manager._park_confirm("sess-1", WRITE_MSG))
        await asyncio.sleep(0.05)
        pending = manager._pending.get("sess-1")
        assert pending is not None and pending.action_id == "act-0001"
        assert manager.confirm("sess-1", True) is True
        return await task

    assert run(scenario()) is True
    assert registered["session_id"] == "sess-1"
    assert registered["tool"] == "create_work_order"
    assert registered["arguments"]["cow_id"] == "COW-0042"
    assert action_stub.value == "act-0001", "放行后凭证必须写入 ContextVar 供工具执行携带"


def test_register_failure_denies_write_fail_closed(monkeypatch, action_stub):
    async def boom(session_id, tool, arguments):
        raise cow_tools.ToolError("cow-admin 不可达")

    monkeypatch.setattr(cow_tools, "register_action", boom)
    manager = AgentManager()

    assert run(manager._park_confirm("sess-1", WRITE_MSG)) is False
    assert manager._pending.get("sess-1") is None, "fail-closed：注册不上不进入待确认"
    assert action_stub.value is None


def test_timeout_expires_registered_action(monkeypatch, action_stub):
    expired = []

    async def fake_register(session_id, tool, arguments):
        return "act-0009"

    async def fake_expire(action_id):
        expired.append(action_id)

    monkeypatch.setattr(cow_tools, "register_action", fake_register)
    monkeypatch.setattr(cow_tools, "expire_action", fake_expire)
    monkeypatch.setattr("app.agent_manager.settings.CONFIRM_TIMEOUT_SECONDS", 0.1)
    manager = AgentManager()

    assert run(manager._park_confirm("sess-1", WRITE_MSG)) is False
    assert expired == ["act-0009"], "120s 超时自动拒绝必须同步作废 admin 侧凭证"


def test_non_domain_write_confirm_skips_registration(monkeypatch, action_stub):
    async def fake_register(session_id, tool, arguments):
        raise AssertionError("非领域写工具不应注册 PENDING_ACTION")

    monkeypatch.setattr(cow_tools, "register_action", fake_register)
    manager = AgentManager()

    async def scenario():
        task = asyncio.create_task(manager._park_confirm("sess-2", "是否写入文件 notes.txt？"))
        await asyncio.sleep(0.05)
        assert manager.confirm("sess-2", True) is True
        return await task

    assert run(scenario()) is True
    assert action_stub.value is None


def test_create_work_order_sends_action_header(monkeypatch):
    """批准后执行建单：请求头必须带 X-Action-Id（admin 侧强制校验）。"""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"code": 200, "data": {"token": "t"}})
        if request.url.path == "/api/v1/tasks" and request.method == "POST":
            seen["action_id"] = request.headers.get("X-Action-Id")
            return httpx.Response(200, json={"code": 200, "data": {"id": 99, "orderNo": "WO-x"}})
        return httpx.Response(404, json={"code": 404, "data": None})

    client = cow_tools.AdminClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(cow_tools, "admin_client", client)
    cow_tools.current_action_id.set("act-0001")
    try:
        out = json.loads(run(cow_tools.execute("create_work_order", {
            "type": "VET_CHECK", "cow_id": "COW-0042", "description": "跛行复核"})))
    finally:
        cow_tools.current_action_id.set(None)
    assert out["orderNo"] == "WO-x"
    assert seen["action_id"] == "act-0001"
