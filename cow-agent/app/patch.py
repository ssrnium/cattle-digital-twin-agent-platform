"""启动时应用的运行时补丁：BearCode 母版源码零改动，全部在进程内 patch。

- 把 bear/ 加入 sys.path（agents/ 是 namespace package，无 __init__.py）；
- agents.agent 模块命名空间里的 print_* / spinner 系列 patch 为 no-op
  （母版是 CLI 形态，服务端场景下消除日志刷屏与 spinner 线程；
   print_error 例外，转发到 logging 保留错误可见性）；
- BEAR_AUTO_SKILL_EVOLUTION 默认关闭（后台 skill 进化在 default 模式不写文件，
  但会多调 LLM）；
- 扩展 check_permission：自定义领域写工具（create_work_order）默认不进 confirm
  流程，这里补上——走 confirm_fn park 到前端审批。
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

_applied = False


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

    _applied = True
    logger.info("bear runtime patches applied")
