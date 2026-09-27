"""离线确定性测试/演示替身：脚本化 OpenAI 兼容客户端 + 罐头 cow-admin MockTransport。

只被 tests/ 与 scripts/demo_* 使用，不进生产链路：
- FakeOpenAIClient 按「角色脚本」回放流式响应（main / investigator 按系统提示词路由），
  不花真实 API 额度，每次运行结果完全一致；
- make_fake_admin_transport 用 httpx.MockTransport 提供 ZONE-B 两头异常牛的罐头数据，
  并记录所有建单请求，便于断言「写操作是否真的越过了审批边界」。
"""
from __future__ import annotations

import itertools
import json
from collections import deque
from types import SimpleNamespace
from typing import Any

import httpx

# 子 Agent 系统提示词里的身份标记，FakeOpenAIClient 据此路由脚本。
# 主 Agent 的 SYSTEM_PROMPT 不得包含该字符串。
INVESTIGATOR_MARKER = "排查专员"

DEFAULT_USAGE = {"prompt_tokens": 120, "completion_tokens": 30}

# ─── 罐头业务数据：ZONE-B 最近异常的两头牛 ─────────────────────

FAKE_EVENTS = [
    {
        "event_id": "EVT-2026-092701", "event_type": "MOUNTING", "cow_id": "COW-0042",
        "device_id": "CAM-B-03", "zone": "ZONE-B", "confidence": 0.87,
        "occurred_at": "2026-09-27T06:12:00Z",
    },
    {
        "event_id": "EVT-2026-092702", "event_type": "MOUNTING", "cow_id": "COW-0042",
        "device_id": "CAM-B-03", "zone": "ZONE-B", "confidence": 0.81,
        "occurred_at": "2026-09-27T06:40:00Z",
    },
    {
        "event_id": "EVT-2026-092703", "event_type": "LAMENESS", "cow_id": "COW-0057",
        "device_id": "CAM-B-05", "zone": "ZONE-B", "confidence": 0.76,
        "occurred_at": "2026-09-27T07:05:00Z",
    },
]

FAKE_PROFILES = {
    "COW-0042": {
        "cow_id": "COW-0042", "zone": "ZONE-B", "parity": 2, "lactation_day": 143,
        "twin": {"posture": "STANDING", "activity_index": 0.62,
                 "estrus_status": "SUSPECTED_HEAT", "health_status": "NORMAL"},
    },
    "COW-0057": {
        "cow_id": "COW-0057", "zone": "ZONE-B", "parity": 3, "lactation_day": 88,
        "twin": {"posture": "WALKING", "activity_index": 0.31,
                 "estrus_status": "NORMAL", "health_status": "ATTENTION"},
    },
}

FAKE_TIMELINES = {
    "COW-0042": [
        {"event_id": "EVT-2026-092702", "kind": "MOUNTING", "occurred_at": "2026-09-27T06:40:00Z",
         "note": "爬跨置信度 0.81"},
        {"event_id": "EVT-2026-092701", "kind": "MOUNTING", "occurred_at": "2026-09-27T06:12:00Z",
         "note": "爬跨置信度 0.87"},
        {"event_id": None, "kind": "TWIN_INFERENCE", "occurred_at": "2026-09-27T06:41:00Z",
         "note": "发情推断 SUSPECTED_HEAT（连续 2 次爬跨）"},
    ],
    "COW-0057": [
        {"event_id": "EVT-2026-092703", "kind": "LAMENESS", "occurred_at": "2026-09-27T07:05:00Z",
         "note": "跛行置信度 0.76"},
        {"event_id": None, "kind": "TWIN_INFERENCE", "occurred_at": "2026-09-27T07:06:00Z",
         "note": "活动量降至 0.31，健康状态 ATTENTION"},
    ],
}


def _ok(data: Any) -> httpx.Response:
    return httpx.Response(200, json={"code": 200, "data": data})


def make_fake_admin_transport() -> tuple[httpx.MockTransport, dict[str, Any]]:
    """罐头 cow-admin：登录 / 事件 / 档案 / 时间线 / 建单，全部内存数据。

    返回 (transport, state)；state["work_orders"] 记录每一笔到达后端的建单请求，
    审批边界测试用它断言「未确认的写操作从未到达后端」。
    """
    state: dict[str, Any] = {"work_orders": [], "logins": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/auth/login" and request.method == "POST":
            state["logins"] += 1
            return _ok({"token": "fake-service-token"})
        if path == "/api/v1/events" and request.method == "GET":
            items = list(FAKE_EVENTS)
            cow_id = request.url.params.get("cowId")
            event_type = request.url.params.get("eventType")
            if cow_id:
                items = [e for e in items if e["cow_id"] == cow_id]
            if event_type:
                items = [e for e in items if e["event_type"] == event_type]
            return _ok({"total": len(items), "items": items})
        if path.startswith("/api/v1/cows/") and request.method == "GET":
            parts = path.strip("/").split("/")
            cow_id = parts[3] if len(parts) >= 4 else ""
            if len(parts) == 5 and parts[4] == "timeline":
                return _ok(FAKE_TIMELINES.get(cow_id, []))
            profile = FAKE_PROFILES.get(cow_id)
            if profile:
                return _ok(profile)
            return httpx.Response(200, json={"code": 404, "message": f"牛只不存在: {cow_id}"})
        if path == "/api/v1/tasks" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            state["work_orders"].append({
                "body": body, "action_id": request.headers.get("X-Action-Id"),
            })
            return _ok({"id": 1001, "orderNo": "WO-20260927-0001", "state": "NEW"})
        if path == "/api/v1/tasks" and request.method == "GET":
            return _ok({"total": 0, "items": []})
        if path == "/api/v1/devices" and request.method == "GET":
            return _ok([
                {"device_id": "CAM-B-03", "zone": "ZONE-B", "online": True},
                {"device_id": "CAM-B-05", "zone": "ZONE-B", "online": True},
            ])
        if path == "/api/v1/twin/states" and request.method == "GET":
            return _ok([p["twin"] | {"cow_id": cid} for cid, p in FAKE_PROFILES.items()])
        return httpx.Response(404, json={"code": 404, "message": f"fake admin 未覆盖: {path}"})

    return httpx.MockTransport(handler), state


# ─── 脚本化 OpenAI 兼容流式客户端 ──────────────────────────────

_id_counter = itertools.count(1)


def _chunk(*, content=None, tool_call=None, finish=None, usage=None):
    delta = SimpleNamespace(
        content=content,
        tool_calls=[
            SimpleNamespace(
                index=tool_call["index"],
                id=tool_call["id"],
                function=SimpleNamespace(name=tool_call["name"], arguments=tool_call["arguments"]),
            )
        ] if tool_call else None,
        reasoning_content=None,
    )
    return SimpleNamespace(
        usage=SimpleNamespace(**usage) if usage else None,
        choices=[SimpleNamespace(delta=delta, finish_reason=finish)],
    )


class _FakeStream:
    """把一条脚本步骤组装成 OpenAI 流式 chunk 序列（content → tool_calls → finish+usage）。"""

    def __init__(self, step: dict[str, Any]) -> None:
        chunks = []
        content = step.get("content")
        tool_calls = step.get("tool_calls") or []
        if content:
            chunks.append(_chunk(content=content))
        for index, tc in enumerate(tool_calls):
            chunks.append(_chunk(tool_call={
                "index": index,
                "id": tc.get("id") or f"call_fake_{next(_id_counter)}",
                "name": tc["name"],
                "arguments": json.dumps(tc.get("arguments") or {}, ensure_ascii=False),
            }))
        chunks.append(_chunk(
            finish="tool_calls" if tool_calls else "stop",
            usage=step.get("usage") or dict(DEFAULT_USAGE),
        ))
        self._chunks = chunks

    def __aiter__(self):
        async def _gen():
            for chunk in self._chunks:
                yield chunk
        return _gen()


class FakeOpenAIClient:
    """脚本化 fake：主 Agent 与排查子 Agent 共用，按系统提示词中的身份标记路由脚本。

    - main_script: 主 Agent 每次模型调用弹一步；
    - investigator_scripts: 队列，每次启动子 Agent 弹出该子 Agent 的完整脚本；
    - calls: 记录每次请求的 role 与实际下发的工具名清单（用于断言白名单收窄）。
    """

    def __init__(
        self,
        main_script: list[dict[str, Any]],
        investigator_scripts: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        self.base_url = "http://offline-fake.local/v1"
        self._main = deque(main_script)
        self._investigators = deque(deque(script) for script in (investigator_scripts or []))
        self._active_investigator: deque | None = None
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _next_step(self, role: str, fresh_conversation: bool) -> dict[str, Any]:
        if role == "investigator":
            if fresh_conversation or self._active_investigator is None:
                # 新一轮子 Agent 对话（历史里还没有任何工具结果）→ 弹出该子 Agent 的脚本
                self._active_investigator = (
                    self._investigators.popleft() if self._investigators else deque()
                )
            step = self._active_investigator.popleft() if self._active_investigator else None
        else:
            step = self._main.popleft() if self._main else None
        if step is None:
            return {"content": f"[fake:{role}] 脚本已用尽，默认收尾回复"}
        return step

    async def _create(self, **kwargs):
        messages = kwargs.get("messages") or []
        system = str(messages[0].get("content") or "") if messages and isinstance(messages[0], dict) else ""
        role = "investigator" if INVESTIGATOR_MARKER in system else "main"
        if not kwargs.get("stream"):
            # memory side_query / skill 评判等非流式调用：返回空选择，等价于「无记忆命中」
            self.calls.append({"role": f"{role}:side_query", "tools": []})
            return SimpleNamespace(choices=[])
        tools = [
            str((t.get("function") or {}).get("name") or "")
            for t in (kwargs.get("tools") or [])
        ]
        fresh = not any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
        self.calls.append({"role": role, "tools": tools, "message_count": len(messages)})
        return _FakeStream(self._next_step(role, fresh))
