"""奶牛领域工具：7 个，全部通过 httpx 回调 cow-admin 的业务 REST 接口。

- 只读工具（自动放行）：query_cow_profile / query_cow_timeline / list_events /
  get_twin_states / list_work_orders / list_devices
- 写工具（需前端确认，见 app.patch）：create_work_order

service 账号（svc-agent）启动登录拿 JWT，401 时自动重登重试一次；
所有调用带超时与错误兜底，返回给模型的都是字符串（JSON 或友好错误）。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Awaitable

import httpx

from app.config import settings

logger = logging.getLogger("cow-agent.tools")

WRITE_TOOLS = {"create_work_order"}

HTTP_TIMEOUT = 10.0


class AdminClient:
    """cow-admin REST 客户端：service 账号 JWT 自动登录 / 过期重登。"""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base_url = settings.COW_ADMIN_BASE_URL.rstrip("/")
        self._transport = transport
        self._token: str | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=HTTP_TIMEOUT,
            transport=self._transport,
        )

    async def login(self) -> None:
        async with self._client() as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": settings.AGENT_USER, "password": settings.AGENT_PASSWORD},
            )
            body = resp.json()
        if resp.status_code != 200 or body.get("code") != 200:
            raise ToolError(f"service 账号登录失败: {body.get('message') or resp.status_code}")
        self._token = body["data"]["token"]

    async def request(self, method: str, path: str, **kwargs) -> Any:
        """调 cow-admin 并解包 Result；401 重登后重试一次。"""
        last_error: Exception | None = None
        for attempt in range(2):
            if self._token is None:
                await self.login()
            try:
                async with self._client() as client:
                    resp = await client.request(
                        method, path,
                        headers={"Authorization": f"Bearer {self._token}"},
                        **kwargs,
                    )
            except httpx.HTTPError as e:
                raise ToolError(f"无法连接 cow-admin({self._base_url}): {e}") from e
            if resp.status_code == 401 and attempt == 0:
                self._token = None  # token 过期，重登再试
                continue
            try:
                body = resp.json()
            except ValueError:
                raise ToolError(f"cow-admin 返回非 JSON: HTTP {resp.status_code}")
            if isinstance(body, dict) and "code" in body:
                if body.get("code") == 200:
                    return body.get("data")
                last_error = ToolError(f"cow-admin 业务错误: {body.get('message')}")
                break
            if resp.status_code >= 400:
                last_error = ToolError(f"cow-admin HTTP {resp.status_code}")
                break
            return body
        raise last_error or ToolError("cow-admin 调用失败")


class ToolError(Exception):
    """领域工具友好错误：作为字符串返回给模型，不抛穿 agent loop。"""


admin_client = AdminClient()


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


TOOL_DEFS: list[dict] = [
    {
        "name": "query_cow_profile",
        "description": "查询单头奶牛的档案与当前数字孪生状态（姿态/区域/健康/发情推断）。",
        "input_schema": _schema(
            {"cow_id": {"type": "string", "description": "牛只编号，如 COW-0042"}},
            ["cow_id"],
        ),
    },
    {
        "name": "query_cow_timeline",
        "description": "查询单头奶牛的时间线（事件与状态推断记录，按发生时间倒序）。",
        "input_schema": _schema(
            {
                "cow_id": {"type": "string", "description": "牛只编号，如 COW-0042"},
                "limit": {"type": "integer", "description": "返回条数，默认 20，最大 100"},
            },
            ["cow_id"],
        ),
    },
    {
        "name": "list_events",
        "description": "分页查询 AI 事件流（爬跨 MOUNTING / 跛行 LAMENESS / 设备离线 DEVICE_OFFLINE 等）。",
        "input_schema": _schema(
            {
                "event_type": {"type": "string", "description": "事件类型过滤，可选"},
                "cow_id": {"type": "string", "description": "按牛只过滤，可选"},
                "device_id": {"type": "string", "description": "按设备过滤，可选"},
                "page": {"type": "integer", "description": "页码，默认 1"},
                "size": {"type": "integer", "description": "每页条数，默认 20"},
            },
            [],
        ),
    },
    {
        "name": "get_twin_states",
        "description": "获取全棚奶牛的当前数字孪生状态列表。",
        "input_schema": _schema({}, []),
    },
    {
        "name": "list_work_orders",
        "description": "分页查询告警工单（繁殖复核 BREEDING_REVIEW / 兽医检查 VET_CHECK / 设备维修 DEVICE_REPAIR）。",
        "input_schema": _schema(
            {
                "state": {"type": "string", "description": "状态过滤：NEW/DISPATCHED/PROCESSING/PENDING_REVIEW/CLOSED/CANCELLED，可选"},
                "type": {"type": "string", "description": "类型过滤，可选"},
                "page": {"type": "integer", "description": "页码，默认 1"},
                "size": {"type": "integer", "description": "每页条数，默认 20"},
            },
            [],
        ),
    },
    {
        "name": "list_devices",
        "description": "查询摄像头与边缘节点列表（在线状态为 60s 心跳计算属性，含断网时长与待补传数）。",
        "input_schema": _schema({}, []),
    },
    {
        "name": "create_work_order",
        "description": "【写操作，需用户确认】手工创建告警工单。调用前必须向用户说明创建理由。",
        "input_schema": _schema(
            {
                "type": {"type": "string", "description": "工单类型：BREEDING_REVIEW/VET_CHECK/DEVICE_REPAIR"},
                "cow_id": {"type": "string", "description": "关联牛只编号，可选"},
                "device_id": {"type": "string", "description": "关联设备编号，可选"},
                "source_event_id": {"type": "string", "description": "来源事件 event_id，可选"},
                "priority": {"type": "string", "description": "优先级：HIGH/NORMAL/LOW，默认 NORMAL"},
                "description": {"type": "string", "description": "工单描述，须包含依据（引用的 cow_id / event_id）"},
            },
            ["type", "description"],
        ),
    },
]


def is_domain_tool(name: str) -> bool:
    return name in TOOL_HANDLERS


def domain_tool_defs() -> list[dict]:
    return TOOL_DEFS


async def execute(name: str, inp: dict) -> str:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return f"Error: unknown domain tool: {name}"
    try:
        data = await handler(inp)
        return json.dumps(data, ensure_ascii=False, default=str)
    except ToolError as e:
        logger.warning("domain tool %s failed: %s", name, e)
        return f"Error: {e}"
    except Exception as e:  # 兜底：任何异常都不抛出 agent loop
        logger.exception("domain tool %s crashed", name)
        return f"Error: 工具执行异常: {e}"


async def _query_cow_profile(inp: dict) -> Any:
    return await admin_client.request("GET", f"/api/v1/cows/{inp['cow_id']}")


async def _query_cow_timeline(inp: dict) -> Any:
    limit = min(int(inp.get("limit") or 20), 100)
    return await admin_client.request(
        "GET", f"/api/v1/cows/{inp['cow_id']}/timeline", params={"limit": limit})


async def _list_events(inp: dict) -> Any:
    params = {"page": inp.get("page") or 1, "size": min(int(inp.get("size") or 20), 50)}
    if inp.get("event_type"):
        params["eventType"] = inp["event_type"]
    if inp.get("cow_id"):
        params["cowId"] = inp["cow_id"]
    if inp.get("device_id"):
        params["deviceId"] = inp["device_id"]
    return await admin_client.request("GET", "/api/v1/events", params=params)


async def _get_twin_states(inp: dict) -> Any:
    return await admin_client.request("GET", "/api/v1/twin/states")


async def _list_work_orders(inp: dict) -> Any:
    params = {"page": inp.get("page") or 1, "size": min(int(inp.get("size") or 20), 50)}
    if inp.get("state"):
        params["state"] = inp["state"]
    if inp.get("type"):
        params["type"] = inp["type"]
    return await admin_client.request("GET", "/api/v1/tasks", params=params)


async def _list_devices(inp: dict) -> Any:
    return await admin_client.request("GET", "/api/v1/devices")


async def _create_work_order(inp: dict) -> Any:
    body = {
        "type": inp["type"],
        "cowId": inp.get("cow_id"),
        "deviceId": inp.get("device_id"),
        "sourceEventId": inp.get("source_event_id"),
        "priority": inp.get("priority") or "NORMAL",
        "description": inp["description"],
    }
    return await admin_client.request("POST", "/api/v1/tasks", json=body)


TOOL_HANDLERS: dict[str, Callable[[dict], Awaitable[Any]]] = {
    "query_cow_profile": _query_cow_profile,
    "query_cow_timeline": _query_cow_timeline,
    "list_events": _list_events,
    "get_twin_states": _get_twin_states,
    "list_work_orders": _list_work_orders,
    "list_devices": _list_devices,
    "create_work_order": _create_work_order,
}
