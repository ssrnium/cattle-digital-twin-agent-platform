"""Sub-agent creation must preserve the parent approval boundary."""

import asyncio

from app.patch import apply_patches

apply_patches()

import agents.agent as agent_mod  # noqa: E402


def test_general_subagent_inherits_default_permission_and_confirm_callback(monkeypatch):
    parent = agent_mod.Agent(
        permission_mode="default",
        model="deepseek-chat",
        confirm_fn=lambda _message: asyncio.sleep(0, result=True),
        custom_system_prompt="test",
        custom_tools=[],
    )
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def run_once(self, _prompt):
            return {"text": "ok", "tokens": {"input": 0, "output": 0}}

    monkeypatch.setattr(agent_mod, "Agent", FakeAgent)
    result = asyncio.run(parent._execute_agent_tool({
        "type": "general",
        "description": "permission check",
        "prompt": "inspect",
    }))
    assert result == "ok"
    assert captured["permission_mode"] == "default"
    assert captured["confirm_fn"] is parent.confirm_fn
