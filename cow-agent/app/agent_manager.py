"""per-session Agent 实例池 + 写操作确认 park 机制。

- Agent 实例非并发安全 → 每个 session 一个实例 + 每实例 asyncio.Lock；
- confirm_fn 把确认请求 park 到 asyncio.Future，前端调 /confirm 后放行，
  超时（默认 120s）自动拒绝；
- pending 确认通过 /sessions 暴露给前端轮询（chat 请求本身阻塞等待确认）；
- 审批下沉：领域写工具 park 前先向 admin 注册 PENDING_ACTION（失败即拒绝该
  写操作，fail-closed），放行后凭证经 ContextVar 传给工具执行（X-Action-Id），
  超时路径同步作废 admin 侧凭证。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

from app import cow_tools
from app.config import settings
from app.cow_agent import create_cow_agent

logger = logging.getLogger("cow-agent.manager")


class LLMNotConfigured(Exception):
    """未配置 LLM_API_KEY 时的友好错误。"""


@dataclass
class PendingConfirm:
    future: asyncio.Future
    message: str
    tool: str
    arguments: dict
    since: float = field(default_factory=time.time)
    action_id: str | None = None


@dataclass
class SessionEntry:
    session_id: str
    agent: object
    lock: asyncio.Lock
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


class AgentManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionEntry] = {}
        self._pending: dict[str, PendingConfirm] = {}

    def new_session_id(self) -> str:
        return uuid.uuid4().hex[:12]

    async def _get_entry(self, session_id: str | None) -> SessionEntry:
        if not session_id:
            session_id = self.new_session_id()
        entry = self._sessions.get(session_id)
        if entry is None:

            async def confirm_fn(message: str, _sid: str = session_id) -> bool:
                return await self._park_confirm(_sid, message)

            entry = SessionEntry(
                session_id=session_id,
                agent=create_cow_agent(confirm_fn),
                lock=asyncio.Lock(),
            )
            self._sessions[session_id] = entry
            logger.info("agent session created: %s", session_id)
        return entry

    async def chat(self, session_id: str | None, message: str) -> dict:
        if not settings.LLM_API_KEY:
            raise LLMNotConfigured(
                "LLM 未配置：请在 cow-agent/.env 或环境变量中设置 LLM_API_KEY 后重启服务")
        entry = await self._get_entry(session_id)
        async with entry.lock:
            entry.last_active = time.time()
            result = await entry.agent.run_once(message)
            entry.last_active = time.time()
        return {
            "session_id": entry.session_id,
            "reply": result.get("text", ""),
            "tokens": result.get("tokens", {}),
            "tool_trace": result.get("tool_trace", []),
        }

    async def _park_confirm(self, session_id: str, message: str) -> bool:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        tool, arguments = self._parse_confirm_message(message)
        action_id = None
        if tool in cow_tools.WRITE_TOOLS:
            # 审批下沉：先向 admin 注册 PENDING_ACTION；注册不上 = 后端审批不可用，
            # 直接拒绝该写操作（fail-closed，不放行无凭证的写）
            try:
                action_id = await cow_tools.register_action(session_id, tool, arguments)
            except Exception as e:
                logger.warning("session %s action register failed, deny write: %s", session_id, e)
                return False
            cow_tools.current_action_id.set(action_id)
        self._pending[session_id] = PendingConfirm(
            future=fut, message=message, tool=tool, arguments=arguments, action_id=action_id)
        logger.info("session %s waiting confirm: %s (action=%s)", session_id, tool, action_id)
        try:
            return bool(await asyncio.wait_for(fut, timeout=settings.CONFIRM_TIMEOUT_SECONDS))
        except asyncio.TimeoutError:
            logger.info("session %s confirm timeout, auto-denied", session_id)
            if action_id:
                await cow_tools.expire_action(action_id)  # 同步作废 admin 侧凭证
            return False
        finally:
            self._pending.pop(session_id, None)

    @staticmethod
    def _parse_confirm_message(message: str) -> tuple[str, dict]:
        """patch.py 对领域写工具产生的 message 是 JSON；其余（如写文件）是原文。"""
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict) and parsed.get("kind") == "cow_write":
                return str(parsed.get("tool", "")), dict(parsed.get("arguments") or {})
        except (ValueError, TypeError):
            pass
        return "", {}

    def confirm(self, session_id: str, approved: bool) -> bool:
        pending = self._pending.get(session_id)
        if pending is None or pending.future.done():
            return False
        pending.future.set_result(bool(approved))
        logger.info("session %s confirm resolved: approved=%s", session_id, approved)
        return True

    def list_sessions(self) -> list[dict]:
        result = []
        for sid, entry in self._sessions.items():
            pending = self._pending.get(sid)
            result.append({
                "session_id": sid,
                "created_at": entry.created_at,
                "last_active": entry.last_active,
                "pending_confirmation": None if pending is None else {
                    "tool": pending.tool,
                    "arguments": pending.arguments,
                    "message": pending.message,
                    "since": pending.since,
                },
            })
        return result


agent_manager = AgentManager()
