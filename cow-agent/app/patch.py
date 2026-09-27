"""启动时应用的运行时补丁：BearCode 母版源码零改动，全部在进程内 patch。

- 把 bear/ 加入 sys.path（agents/ 是 namespace package，无 __init__.py）；
- agents.agent 模块命名空间里的 print_* / spinner 系列 patch 为 no-op
  （母版是 CLI 形态，服务端场景下消除日志刷屏与 spinner 线程；
   print_error 例外，转发到 logging 保留错误可见性）；
- BEAR_AUTO_SKILL_EVOLUTION 默认关闭（后台 skill 进化在 default 模式不写文件，
  但会多调 LLM）；
- 扩展 check_permission：自定义领域写工具（create_work_order）默认不进 confirm
  流程，这里补上——走 confirm_fn park 到前端审批。
- 历史完整性守卫（repair_dangling_tool_calls）：发送前扫描 _openai_messages，
  为悬空 tool_calls（工具结果未配对落盘，DeepSeek 会对整个会话持续 400）
  注入合成错误 tool 消息补齐配对；只修不剥，WARNING 记日志，正常历史零改动。
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

BEAR_ROOT = Path(__file__).resolve().parent.parent / "bear"
if str(BEAR_ROOT) not in sys.path:
    sys.path.insert(0, str(BEAR_ROOT))

logger = logging.getLogger("cow-agent.patch")

# 领域写工具：必须走前端确认（见 app.cow_tools.WRITE_TOOLS，此处硬编码避免循环依赖）
COW_WRITE_TOOLS = {"create_work_order"}

# 历史完整性守卫注入的合成 tool 消息内容（只修不剥，现场可审计）
REPAIR_NOTE = "[runtime] tool result missing: repaired by history integrity guard"

_applied = False


def repair_dangling_tool_calls(messages: list, *, session_id: str = "") -> list[str]:
    """发送前历史扫描：为悬空 tool_calls 注入合成错误 tool 消息，使配对完整。

    背景：某轮异常中断（如工具结果未落盘）会在历史里留下带 tool_calls 的 assistant
    消息却缺少对应 tool 结果，DeepSeek 下一轮起对该会话一律 400
    （tool_calls must be followed by tool messages），会话被永久毒化。
    本守卫只修不剥：不删除任何既有消息，只在缺失处插入 REPAIR_NOTE  tool 消息，
    返回被修复的 tool_call_id 列表（正常历史返回空、零改动）。
    """
    repaired: list[str] = []
    i = 0
    while i < len(messages):
        message = messages[i]
        tool_calls = message.get("tool_calls") or [] if isinstance(message, dict) else []
        expected = [str(tc.get("id")) for tc in tool_calls if isinstance(tc, dict) and tc.get("id")]
        if not expected:
            i += 1
            continue
        answered = set()
        j = i + 1
        while j < len(messages) and isinstance(messages[j], dict) and messages[j].get("role") == "tool":
            answered.add(messages[j].get("tool_call_id"))
            j += 1
        for tool_call_id in expected:
            if tool_call_id not in answered:
                messages.insert(j, {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": REPAIR_NOTE,
                })
                j += 1
                repaired.append(tool_call_id)
        i = j
    if repaired:
        logger.warning(
            "history integrity guard: repaired %d dangling tool_calls (session=%s, history=%d msgs, ids=%s)",
            len(repaired), session_id or "unknown", len(messages), repaired,
        )
    return repaired


def _noop(*args, **kwargs):
    return None


def _log_error(*args, **kwargs):
    logger.error("bear: %s", " ".join(str(a) for a in args))


def apply_patches() -> None:
    global _applied
    if _applied:
        return

    os.environ.setdefault("BEAR_AUTO_SKILL_EVOLUTION", "0")

    import agents.agent as agent_mod
    import agents.tools as tools_mod

    for name in (
        "print_info", "print_divider", "print_assistant_text",
        "print_sub_agent_start", "print_sub_agent_end", "print_cost",
        "print_tool_call", "print_tool_result", "print_confirmation",
        "print_retry", "start_spinner", "stop_spinner",
    ):
        setattr(agent_mod, name, _noop)
    agent_mod.print_error = _log_error

    original_check_permission = tools_mod.check_permission

    def patched_check_permission(tool_name, inp, mode="default", plan_file_path=None):
        result = original_check_permission(tool_name, inp, mode, plan_file_path)
        if (
            result["action"] == "allow"
            and tool_name in COW_WRITE_TOOLS
            and mode != "bypassPermissions"
        ):
            return {
                "action": "confirm",
                "message": json.dumps(
                    {"kind": "cow_write", "tool": tool_name, "arguments": inp},
                    ensure_ascii=False,
                ),
            }
        return result

    # agents.agent 是模块级 from-import，patch 该模块命名空间即生效
    agent_mod.check_permission = patched_check_permission

    # DeepSeek V4.1 Flash 在并行/多轮工具调用时会复用 tool_call_id，
    # 下一轮请求被 DeepSeek 拒（400 Duplicate tool_call_id）。
    # 这些 id 只在单次请求内起"调用-结果"配对作用，与跨轮语义无关——
    # 因此在每次发请求前，把历史消息里的调用/结果 id 按顺序成对重写成全新唯一值。
    import uuid

    original_call_stream = agent_mod.Agent._call_openai_stream

    def sanitize_history_ids(agent_self):
        try:
            pending = []
            for m in getattr(agent_self, "_openai_messages", []):
                tcs = m.get("tool_calls") or []
                if tcs:
                    for tc in tcs:
                        new_id = f"call_{uuid.uuid4().hex[:10]}"
                        tc["id"] = new_id
                        pending.append(new_id)
                if m.get("role") == "tool" and m.get("tool_call_id") is not None:
                    m["tool_call_id"] = pending.pop(0) if pending else m["tool_call_id"]
            seq = [(m.get("role"), len(m.get("tool_calls") or []), m.get("tool_call_id"))
                   for m in getattr(agent_self, "_openai_messages", [])]
            logger.info("outbound messages: %s", seq)
        except Exception:
            pass

    async def sanitized_call_stream(self):
        # 历史完整性守卫（先于 id 重写）：悬空 tool_calls 会让 DeepSeek 对整个会话 400，
        # 注入合成错误 tool 消息补齐配对后再走成对重写，正常历史零改动。
        try:
            repair_dangling_tool_calls(
                self._openai_messages, session_id=str(getattr(self, "session_id", "")))
        except Exception:
            pass
        sanitize_history_ids(self)
        resp = await original_call_stream(self)
        try:
            # 新响应里的 tool_calls 与历史已有 id 查重（保险丝）
            existing_ids = set()
            for m in getattr(self, "_openai_messages", []):
                for tc in (m.get("tool_calls") or []):
                    if tc.get("id"):
                        existing_ids.add(tc["id"])
                if m.get("role") == "tool" and m.get("tool_call_id"):
                    existing_ids.add(m["tool_call_id"])
            for choice in resp.get("choices", []):
                tcs = (choice.get("message") or {}).get("tool_calls") or []
                for tc in tcs:
                    cid = tc.get("id") or ""
                    if not cid or cid in existing_ids:
                        n = 0
                        new_id = cid or f"call_{uuid.uuid4().hex[:10]}"
                        while not new_id or new_id in existing_ids:
                            n += 1
                            new_id = f"{cid or 'call'}_x{n}_{uuid.uuid4().hex[:6]}"
                        tc["id"] = new_id
                    existing_ids.add(tc["id"])
        except Exception:
            pass
        return resp

    agent_mod.Agent._call_openai_stream = sanitized_call_stream

    _applied = True
    logger.info("bear runtime patches applied")
