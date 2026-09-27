"""MCP discovery, call, failure, and permission smoke test."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agents.mcp_client import McpManager
from agents.tools import check_permission


async def run_mcp_smoke(working_dir: str | Path | None = None) -> dict[str, Any]:
    previous = Path.cwd()
    if working_dir is not None:
        os.chdir(Path(working_dir))
    manager = McpManager()
    try:
        await manager.load_and_connect()
        definitions = manager.get_tool_definitions()
        names = [definition["name"] for definition in definitions]
        snapshot_name = "mcp__ranch-demo__get_ranch_snapshot"
        note_name = "mcp__ranch-demo__create_ranch_note"
        failure_name = "mcp__ranch-demo__flaky_health_check"
        snapshot = await manager.call_tool(snapshot_name, {"farm_id": "north-star"})
        write_permission = check_permission(note_name, {"note": "operator review"}, "default")
        deny_permission = check_permission(note_name, {"note": "operator review"}, "dontAsk")
        # The smoke test models the same boundary as Agent._execute_tool_call:
        # a write is sent to the server only after the default policy asks for
        # confirmation and the operator approves it.
        write_result = ""
        if write_permission.get("action") == "confirm":
            approved = True
            if approved:
                write_result = await manager.call_tool(note_name, {"note": "operator review"})
        else:
            raise RuntimeError("MCP write policy did not require confirmation")
        failure = ""
        try:
            await manager.call_tool(failure_name, {"mode": "fail"})
        except Exception as exc:
            failure = str(exc)
        return {
            "config_dir": str(Path.cwd()),
            "servers": ["ranch-demo"] if snapshot_name in names else [],
            "discovered_tools": names,
            "discovered_count": len(names),
            "read_call": {"tool": snapshot_name, "result": snapshot},
            "write_permission": write_permission,
            "dont_ask_permission": deny_permission,
            "write_call_after_approval": {"tool": note_name, "result": write_result},
            "failure_recovered": bool(failure),
            "failure": failure,
        }
    finally:
        await manager.disconnect_all()
        os.chdir(previous)
