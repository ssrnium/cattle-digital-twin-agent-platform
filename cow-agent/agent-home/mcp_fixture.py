"""Small stdio MCP server used by the local runtime evidence checks.

It intentionally has no third-party dependencies and writes protocol messages
only to stdout. The fixture is a real child process, so discovery and calls go
through the same JSON-RPC path as an external MCP server.
"""

from __future__ import annotations

import json
import sys
from typing import Any


TOOLS = [
    {
        "name": "get_ranch_snapshot",
        "description": "Read the current deterministic ranch snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {"farm_id": {"type": "string"}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "create_ranch_note",
        "description": "Create an operational note in the ranch system.",
        "inputSchema": {
            "type": "object",
            "properties": {"note": {"type": "string"}},
            "required": ["note"],
        },
        "annotations": {"readOnlyHint": False},
    },
    {
        "name": "flaky_health_check",
        "description": "Exercise an MCP JSON-RPC failure response when mode=fail.",
        "inputSchema": {
            "type": "object",
            "properties": {"mode": {"type": "string"}},
        },
        "annotations": {"readOnlyHint": True},
    },
]


def response(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> None:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        message["error"] = error
    else:
        message["result"] = result
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(message: dict[str, Any]) -> None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    if request_id is None:
        return
    if method == "initialize":
        response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ranch-demo", "version": "1.0.0"},
            },
        )
    elif method == "tools/list":
        response(request_id, {"tools": TOOLS})
    elif method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        if name == "get_ranch_snapshot":
            farm_id = arguments.get("farm_id") or "north-star"
            response(
                request_id,
                {"content": [{"type": "text", "text": json.dumps({"farm_id": farm_id, "online_devices": 12, "open_events": 3})}]},
            )
        elif name == "create_ranch_note":
            note = str(arguments.get("note") or "").strip()
            if not note:
                response(request_id, error={"code": -32602, "message": "note is required"})
            else:
                response(request_id, {"content": [{"type": "text", "text": f"note-created:{note}"}]})
        elif name == "flaky_health_check":
            if arguments.get("mode") == "fail":
                response(request_id, error={"code": -32001, "message": "fixture health check failed"})
            else:
                response(request_id, {"content": [{"type": "text", "text": "healthy"}]})
        else:
            response(request_id, error={"code": -32601, "message": f"unknown tool: {name}"})
    else:
        response(request_id, error={"code": -32601, "message": f"unknown method: {method}"})


def main() -> None:
    for line in sys.stdin:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            handle(payload)


if __name__ == "__main__":
    main()
