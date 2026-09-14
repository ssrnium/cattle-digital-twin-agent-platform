"""领域工具单测：httpx.MockTransport mock 掉 cow-admin，不落真实 HTTP。"""
import asyncio
import json

import httpx
import pytest

from app import cow_tools


def _result(data, code=200):
    return {"code": code, "message": "success" if code == 200 else "err", "data": data}


def make_transport(record: list, fail_first_with_401: bool = False):
    state = {"get_count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        record.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/v1/auth/login":
            body = json.loads(request.content)
            assert body["username"], "登录必须带用户名"
            return httpx.Response(200, json=_result({"token": f"token-{len(record)}"}))
        if fail_first_with_401 and state["get_count"] == 0 and request.method == "GET":
            state["get_count"] += 1
            return httpx.Response(401, json=_result(None, code=401))
        if request.url.path.startswith("/api/v1/cows/") and request.url.path.endswith("/timeline"):
            return httpx.Response(200, json=_result([{"cowId": "COW-0042", "eventType": "MOUNTING"}]))
        if request.url.path.startswith("/api/v1/cows/"):
            return httpx.Response(200, json=_result({"profile": {"cowId": "COW-0042"}, "twinState": None}))
        if request.url.path == "/api/v1/events":
            return httpx.Response(200, json=_result({"records": [{"eventId": "e-1"}], "total": 1}))
        if request.url.path == "/api/v1/twin/states":
            return httpx.Response(200, json=_result([{"cowId": "COW-0001"}]))
        if request.url.path == "/api/v1/devices":
            return httpx.Response(200, json=_result([{"deviceId": "edge-node-01", "onlineStatus": "ONLINE"}]))
        if request.url.path == "/api/v1/tasks" and request.method == "GET":
            return httpx.Response(200, json=_result({"records": [], "total": 0}))
        if request.url.path == "/api/v1/tasks" and request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json=_result({"id": 99, "orderNo": "WO-x", **body}))
        return httpx.Response(404, json=_result(None, code=404))

    return httpx.MockTransport(handler)


@pytest.fixture
def mock_admin(monkeypatch):
    record: list = []
    client = cow_tools.AdminClient(transport=make_transport(record))
    monkeypatch.setattr(cow_tools, "admin_client", client)
    return record


def run(coro):
    return asyncio.run(coro)


def test_read_tools_call_admin_and_unwrap(mock_admin):
    out = json.loads(run(cow_tools.execute("query_cow_profile", {"cow_id": "COW-0042"})))
    assert out["profile"]["cowId"] == "COW-0042"
    out = json.loads(run(cow_tools.execute("query_cow_timeline", {"cow_id": "COW-0042"})))
    assert out[0]["eventType"] == "MOUNTING"
    out = json.loads(run(cow_tools.execute("list_events", {"event_type": "MOUNTING"})))
    assert out["total"] == 1
    out = json.loads(run(cow_tools.execute("get_twin_states", {})))
    assert out[0]["cowId"] == "COW-0001"
    out = json.loads(run(cow_tools.execute("list_work_orders", {"state": "NEW"})))
    assert out["total"] == 0
    out = json.loads(run(cow_tools.execute("list_devices", {})))
    assert out[0]["onlineStatus"] == "ONLINE"


def test_create_work_order_posts_body(mock_admin):
    out = json.loads(run(cow_tools.execute("create_work_order", {
        "type": "VET_CHECK", "cow_id": "COW-0042", "description": "跛行复核"})))
    assert out["orderNo"] == "WO-x"
    assert out["type"] == "VET_CHECK"
    assert out["priority"] == "NORMAL"  # 默认优先级


def test_jwt_refresh_on_401(monkeypatch):
    record: list = []
    client = cow_tools.AdminClient(transport=make_transport(record, fail_first_with_401=True))
    monkeypatch.setattr(cow_tools, "admin_client", client)
    out = json.loads(run(cow_tools.execute("list_devices", {})))
    assert out[0]["deviceId"] == "edge-node-01"
    # 两次登录（首次 + 401 后重登）
    assert record.count("POST /api/v1/auth/login") == 2


def test_tool_error_is_friendly_string(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json=_result({"token": "t"}))
        return httpx.Response(200, json=_result(None, code=404))

    client = cow_tools.AdminClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(cow_tools, "admin_client", client)
    out = run(cow_tools.execute("query_cow_profile", {"cow_id": "COW-9999"}))
    assert out.startswith("Error:"), "业务错误必须作为字符串返回给模型，不抛出"


def test_tool_defs_registered():
    names = {t["name"] for t in cow_tools.domain_tool_defs()}
    assert names == {
        "query_cow_profile", "query_cow_timeline", "list_events",
        "get_twin_states", "list_work_orders", "list_devices", "create_work_order",
    }
    assert cow_tools.WRITE_TOOLS == {"create_work_order"}
