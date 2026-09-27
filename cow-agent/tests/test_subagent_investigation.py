"""cow-investigator 子 Agent 实战：真实 launch 路径 + 工具白名单收窄 + 写意图回父会话审批。

LLM 用 app.offline_fakes.FakeOpenAIClient 脚本回放（不花真实 API 额度），
cow-admin 用罐头 MockTransport，全链路离线确定性。
"""
import asyncio
import json

import pytest

from app import cow_tools
from app.cow_agent import (
    SUBAGENT_READ_ONLY_TOOLS,
    SUBAGENT_TYPE,
    CowAgent,
    cow_agent_tools,
)
from app.offline_fakes import FakeOpenAIClient, make_fake_admin_transport
from app.patch import apply_patches

apply_patches()

import agents.agent as agent_mod  # noqa: E402

Q1 = "ZONE-B 最近异常的几头牛都什么情况？"

MAIN_SCRIPT = [
    {"tool_calls": [{"name": "list_events", "arguments": {"size": 10}}]},
    {"tool_calls": [{"name": "agent", "arguments": {
        "type": SUBAGENT_TYPE,
        "description": "排查 COW-0042",
        "prompt": "排查 COW-0042：档案 + 时间线 + 近期事件，给出状态判断与建议。",
    }}]},
    {"tool_calls": [{"name": "agent", "arguments": {
        "type": SUBAGENT_TYPE,
        "description": "排查 COW-0057",
        "prompt": "排查 COW-0057：档案 + 近期跛行事件，给出状态判断与建议。",
    }}]},
    {"content": "ZONE-B 异常汇总：COW-0042 疑似发情（EVT-2026-092701/092702）；"
                "COW-0057 跛行待复核（EVT-2026-092703）。"},
]

INVESTIGATOR_SCRIPTS = [
    [
        {"tool_calls": [
            {"name": "query_cow_profile", "arguments": {"cow_id": "COW-0042"}},
            {"name": "query_cow_timeline", "arguments": {"cow_id": "COW-0042", "limit": 10}},
        ]},
        {"content": "COW-0042 报告：疑似发情，证据 EVT-2026-092701 / EVT-2026-092702，"
                    "建议繁殖复核（建单需主会话确认）。"},
    ],
    [
        {"tool_calls": [
            {"name": "query_cow_profile", "arguments": {"cow_id": "COW-0057"}},
        ]},
        {"tool_calls": [
            {"name": "query_cow_timeline", "arguments": {"cow_id": "COW-0057", "limit": 10}},
        ]},
        {"content": "COW-0057 报告：跛行事件 EVT-2026-092703，活动量 0.31，建议兽医检查。"},
    ],
]


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def fake_admin(monkeypatch):
    transport, state = make_fake_admin_transport()
    client = cow_tools.AdminClient(transport=transport)
    monkeypatch.setattr(cow_tools, "admin_client", client)
    return state


def _make_agent(confirm_fn, fake_llm) -> CowAgent:
    agent = CowAgent(
        model="fake-model",
        api_base="http://offline-fake.local/v1",
        api_key="fake-key",
        permission_mode="default",
        confirm_fn=confirm_fn,
        custom_system_prompt="牧场主 Agent（测试）",
        custom_tools=cow_agent_tools(),
        max_turns=12,
    )
    agent._openai_client = fake_llm
    return agent


def test_cow_investigator_subagent_runs_with_narrowed_read_only_tools(
    tmp_path, monkeypatch, fake_admin,
):
    """多头牛排查：主 Agent 圈定清单 → 每头牛一个真实子 Agent（只读白名单）→ 汇总。"""
    monkeypatch.chdir(tmp_path)

    async def confirm(_message):
        return True

    fake_llm = FakeOpenAIClient(MAIN_SCRIPT, INVESTIGATOR_SCRIPTS)
    agent = _make_agent(confirm, fake_llm)
    result = _run(agent.run_once(Q1))

    runs = result["subagent_runs"]
    assert len(runs) == 2, "两头异常牛应各启动一个 cow-investigator 子 Agent"
    for run in runs:
        assert run["type"] == SUBAGENT_TYPE
        # 白名单收窄：只挂只读领域工具，写工具被排除
        assert set(run["tools_granted"]) == set(SUBAGENT_READ_ONLY_TOOLS)
        assert "create_work_order" not in run["tools_granted"]
        assert run["write_tools_excluded"] == ["create_work_order"]
        # 权限边界继承：default 模式 + 父会话 confirm_fn
        assert run["permission_mode"] == "default"
        assert run["confirm_fn_shared_with_parent"] is True
        # 子 Agent 真实跑了自己的 agent loop 并用了领域只读工具
        tools_used = [t["tool"] for t in run["tool_trace"]]
        assert "query_cow_profile" in tools_used
        assert run["report"].strip()

    cow_ids = {run["tool_trace"][0]["arguments"]["cow_id"] for run in runs}
    assert cow_ids == {"COW-0042", "COW-0057"}

    # 主会话 trace 可见父子分工：list_events 由主 Agent 执行，两次 agent 调用下发子 Agent
    main_tools = [t["tool"] for t in result["tool_trace"]]
    assert main_tools == ["list_events", "agent", "agent"]

    # 下发给 LLM 的工具清单证据：子 Agent 请求里没有 create_work_order，主 Agent 请求里有
    investigator_calls = [c for c in fake_llm.calls if c["role"] == "investigator"]
    main_calls = [c for c in fake_llm.calls if c["role"] == "main"]
    assert investigator_calls, "子 Agent 必须真实发起过 LLM 请求"
    for call in investigator_calls:
        assert "create_work_order" not in call["tools"]
        assert "agent" not in call["tools"], "子 Agent 不允许再递归启动子 Agent"
    assert any("create_work_order" in c["tools"] for c in main_calls)
    assert "COW-0042" in result["text"] and "COW-0057" in result["text"]


def test_subagent_write_intent_parks_in_parent_session_confirm(
    tmp_path, monkeypatch, fake_admin,
):
    """子 Agent 脚本尝试建单：确认请求仍进入父会话 confirm_fn；拒绝后写操作不到达后端。"""
    monkeypatch.chdir(tmp_path)
    confirmations = []

    async def confirm(message):
        confirmations.append(json.loads(message))
        return False  # 用户拒绝

    main_script = [
        {"tool_calls": [{"name": "agent", "arguments": {
            "type": SUBAGENT_TYPE,
            "description": "排查 COW-0057",
            "prompt": "排查 COW-0057 跛行。",
        }}]},
        {"content": "COW-0057 需要兽医检查，但用户拒绝了建单。"},
    ]
    investigator_scripts = [[
        {"tool_calls": [{"name": "create_work_order", "arguments": {
            "type": "VET_CHECK", "cow_id": "COW-0057",
            "description": "跛行复核（子 Agent 越权尝试）",
        }}]},
        {"content": "建单被拒绝，我只能建议主 Agent 走确认通道。"},
    ]]

    fake_llm = FakeOpenAIClient(main_script, investigator_scripts)
    agent = _make_agent(confirm, fake_llm)
    result = _run(agent.run_once("看看 COW-0057 的跛行，需要就建单"))

    # 写意图没有静默执行，而是 park 到父会话的 confirm_fn（与主会话同一个审批通道）
    assert len(confirmations) == 1
    assert confirmations[0]["kind"] == "cow_write"
    assert confirmations[0]["tool"] == "create_work_order"
    assert confirmations[0]["arguments"]["cow_id"] == "COW-0057"

    # 拒绝后：后端没有收到任何建单请求
    assert fake_admin["work_orders"] == []

    run = result["subagent_runs"][0]
    # 被拒绝的写意图留在子 Agent 证据里：意图、参数与「父会话拒绝」结果
    assert run["denied_tool_calls"] == [{
        "tool": "create_work_order",
        "arguments": {"type": "VET_CHECK", "cow_id": "COW-0057",
                      "description": "跛行复核（子 Agent 越权尝试）"},
        "outcome": "denied_by_parent_session",
    }]
    assert all(t["tool"] != "create_work_order" for t in run["tool_trace"]), \
        "被拒绝的写操作不得真正执行"


def test_other_subagent_types_fall_back_to_runtime_launch_path(monkeypatch):
    """非 cow-investigator 类型回落母版 _execute_agent_tool，权限继承不变。"""
    async def confirm(_message):
        return True

    agent = CowAgent(
        model="fake-model",
        api_base="http://offline-fake.local/v1",
        api_key="fake-key",
        permission_mode="default",
        confirm_fn=confirm,
        custom_system_prompt="test",
        custom_tools=cow_agent_tools(),
    )
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def run_once(self, _prompt):
            return {"text": "ok", "tokens": {"input": 0, "output": 0}}

    monkeypatch.setattr(agent_mod, "Agent", FakeAgent)
    result = _run(agent._execute_agent_tool({
        "type": "general", "description": "runtime path", "prompt": "inspect",
    }))
    assert result == "ok"
    assert captured["permission_mode"] == "default"
    assert captured["confirm_fn"] is agent.confirm_fn
    assert captured["is_sub_agent"] is True
