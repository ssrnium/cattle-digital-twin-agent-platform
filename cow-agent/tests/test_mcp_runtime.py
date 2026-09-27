"""MCP config discovery and permission boundary regression tests."""

import asyncio
from pathlib import Path

from app.config import agent_home_path
from app.patch import apply_patches

apply_patches()

from agents.mcp_client import McpManager  # noqa: E402
from agents.tools import check_permission  # noqa: E402
from agents.agent import Agent  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def test_fixture_is_discovered_called_and_failure_is_returned(monkeypatch):
    monkeypatch.chdir(agent_home_path())

    async def scenario():
        manager = McpManager()
        await manager.load_and_connect()
        try:
            definitions = manager.get_tool_definitions()
            names = {item["name"] for item in definitions}
            assert "mcp__ranch-demo__get_ranch_snapshot" in names
            assert await manager.call_tool(
                "mcp__ranch-demo__get_ranch_snapshot", {"farm_id": "north-star"}
            ) == '{"farm_id": "north-star", "online_devices": 12, "open_events": 3}'
            try:
                await manager.call_tool("mcp__ranch-demo__flaky_health_check", {"mode": "fail"})
            except RuntimeError as exc:
                assert "fixture health check failed" in str(exc)
            else:
                raise AssertionError("MCP JSON-RPC error was swallowed")
        finally:
            await manager.disconnect_all()

    run(scenario())


def test_mcp_write_tool_requires_confirm_and_dont_ask_denies(monkeypatch):
    monkeypatch.chdir(agent_home_path())

    async def scenario():
        manager = McpManager()
        await manager.load_and_connect()
        try:
            manager.get_tool_definitions()
            name = "mcp__ranch-demo__create_ranch_note"
            assert check_permission(name, {"note": "x"}, "default")["action"] == "confirm"
            assert check_permission(name, {"note": "x"}, "dontAsk")["action"] == "deny"
            assert check_permission("mcp__ranch-demo__get_ranch_snapshot", {}, "default")["action"] == "allow"
        finally:
            await manager.disconnect_all()

    run(scenario())


def test_agent_runtime_routes_discovered_mcp_tool(monkeypatch):
    monkeypatch.chdir(agent_home_path())

    async def scenario():
        agent = Agent(model="deepseek-chat", custom_system_prompt="test", custom_tools=[])
        await agent._mcp_manager.load_and_connect()
        try:
            agent.tools.extend(agent._mcp_manager.get_tool_definitions())
            result = await agent._execute_tool_call(
                "mcp__ranch-demo__get_ranch_snapshot", {"farm_id": "north-star"}
            )
            assert "online_devices" in result
        finally:
            await agent._mcp_manager.disconnect_all()

    run(scenario())
