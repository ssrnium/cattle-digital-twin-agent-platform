"""CowAgent：BearCode Agent 子类，把奶牛领域工具挂进 agent loop。

不改母版一行代码：custom_tools 传「内置 tool_definitions + 领域 schema」，
重写 _execute_tool_call 先查领域注册表，未命中回落 super()。
"""
from __future__ import annotations

import app.patch  # noqa: F401  # 导入即把 bear/ 放上 sys.path
from agents.agent import Agent
from agents.tools import tool_definitions

from app import cow_tools
from app.config import settings

SYSTEM_PROMPT = """你是「数字孪生牧场」的牧场智能体，服务 20 号牛棚（103 头奶牛），
协助场长、兽医与繁育员做事件排查与处置建议。

工作准则：
1. 先查数据再下结论：回答任何牛只 / 设备 / 工单问题前，先用领域工具取数，
   禁止凭空编造数据；
2. 引用证据：结论中必须引用具体的 cow_id（如 COW-0042）与 event_id；
3. 不确定就说不知道，并说明还缺什么数据、可以用哪个工具补查；
4. 写操作闭环：用户明确要求建单时，按"取数（最多 2 次只读工具，够用即止）
   → 说明理由 → 用户确认 → 立即调用 create_work_order → 系统审批后执行"的顺序完成；
   用户在消息中已给出 cow_id 和依据时，可直接给提案等待确认，确认后必须立刻调用工具，
   不得只做文字回复。查询与排查类问题只用只读工具并给出建议，不主动建单。
5. 平台侧已保证确定性（event_id 幂等去重、工单状态机、乐观锁），
   你负责分析 / 排查 / 建议类不确定任务，不要承诺替人做最终处置决定。

可用领域工具：query_cow_profile、query_cow_timeline、list_events、get_twin_states、
list_work_orders、list_devices（只读）；create_work_order（写，需确认）。
领域 SOP（skills）：mounting-review（爬跨/疑似发情复核）、lameness-check（跛行排查）、
device-offline（设备离线排查）、report-style（对场长汇报口径），命中场景时遵循其流程。
"""


class CowAgent(Agent):
    """额外记录每轮工具调用轨迹（名称/参数/结果预览），随 run_once 返回供前端折叠展示。"""

    async def run_once(self, prompt: str):
        self._tool_trace: list[dict] = []
        try:
            result = await super().run_once(prompt)
        finally:
            trace = self._tool_trace
            self._tool_trace = []
        result["tool_trace"] = trace
        return result

    async def _execute_tool_call(self, name: str, inp: dict) -> str:
        if cow_tools.is_domain_tool(name):
            result = await cow_tools.execute(name, inp)
        else:
            result = await super()._execute_tool_call(name, inp)
        if hasattr(self, "_tool_trace"):
            self._tool_trace.append({
                "tool": name,
                "arguments": inp,
                "result_preview": (result or "")[:500],
            })
        return result


def create_cow_agent(confirm_fn) -> CowAgent:
    return CowAgent(
        model=settings.LLM_MODEL,
        api_base=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        permission_mode="default",  # 不启用 plan 模式（母版 agent.py:1192 有 await bug）
        confirm_fn=confirm_fn,
        custom_system_prompt=SYSTEM_PROMPT,
        custom_tools=tool_definitions + cow_tools.domain_tool_defs(),
        max_turns=settings.AGENT_MAX_TURNS,
    )
