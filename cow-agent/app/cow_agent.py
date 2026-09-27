"""CowAgent：BearCode Agent 子类，把奶牛领域工具挂进 agent loop。

不改母版一行代码：custom_tools 传「内置 tool_definitions + 领域 schema」，
重写 _execute_tool_call 先查领域注册表，未命中回落 super()。

子 Agent 实战：agent 工具新增领域类型 cow-investigator（单牛排查专员）。
母版的 launch 路径（bear/agents/agent.py:1277 _execute_agent_tool）只会构造
纯 Agent 子代理、挂内置代码工具，无法路由领域工具；这里按同一机制在 app 层
特化：子代理仍是真实 Agent.run_once 独立循环，但类型收窄为 CowAgent、
只挂只读领域工具，并继续继承父会话 permission_mode + confirm_fn——
写工具 create_work_order 始终留在主会话审批通道。
"""
from __future__ import annotations

import json

import app.patch  # noqa: F401  # 导入即把 bear/ 放上 sys.path
from agents.agent import Agent
from agents.tools import tool_definitions

from app import cow_tools
from app.config import settings

SUBAGENT_TYPE = "cow-investigator"

# 子 Agent 只挂只读领域工具；写工具（create_work_order）始终留在主会话审批通道
SUBAGENT_READ_ONLY_TOOLS = frozenset(
    name for name in cow_tools.TOOL_HANDLERS if name not in cow_tools.WRITE_TOOLS
)

INVESTIGATOR_SYSTEM_PROMPT = """你是「数字孪生牧场」的单牛排查专员（cow-investigator 子 Agent），
由主 Agent 启动，负责**一头牛**的档案与事件排查。

工作准则：
1. 只用授予你的只读领域工具取数，禁止凭空编造；
2. 你没有任何写工具：发现需要建单时，只能在报告中给出建议，
   由主 Agent 走用户确认通道执行；
3. 报告必须引用具体 cow_id 与 event_id；
4. 输出是给主 Agent 汇总的精简排查报告：当前状态判断、关键证据、建议动作（如有）。
"""

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
6. 多头牛排查：需要逐头排查多头牛（如"ZONE-B 异常的几头牛都什么情况"）时，
   先用 list_events 圈定牛只清单，再用 agent 工具（type="cow-investigator"）
   为每头牛启动一个排查子 Agent（只读工具、独立上下文），最后汇总各子 Agent 报告；
   子 Agent 没有写工具，建单始终由你在主会话按准则 4 走确认通道。

可用领域工具：query_cow_profile、query_cow_timeline、list_events、get_twin_states、
list_work_orders、list_devices（只读）；create_work_order（写，需确认）。
领域 SOP（skills）：mounting-review（爬跨/疑似发情复核）、lameness-check（跛行排查）、
device-offline（设备离线排查）、report-style（对场长汇报口径），命中场景时遵循其流程。
"""


def cow_agent_tools() -> list[dict]:
    """内置工具 + 领域 schema；agent 工具的 type 枚举扩展 cow-investigator（app 层拷贝，不动母版）。"""
    tools: list[dict] = []
    for tool in tool_definitions:
        if tool["name"] == "agent":
            tool = json.loads(json.dumps(tool))  # 深拷贝，避免改写母版 tool_definitions
            tool["description"] += (
                f" 领域扩展类型：'{SUBAGENT_TYPE}'（单牛排查专员，只挂只读领域工具，"
                "适合多头牛排查时逐头下发）。"
            )
            enum = tool["input_schema"]["properties"]["type"].setdefault("enum", [])
            if SUBAGENT_TYPE not in enum:
                enum.append(SUBAGENT_TYPE)
        tools.append(tool)
    return tools + cow_tools.domain_tool_defs()


class CowAgent(Agent):
    """额外记录每轮工具调用轨迹与子 Agent 运行证据，随 run_once 返回供前端折叠展示。"""

    async def run_once(self, prompt: str):
        self._tool_trace: list[dict] = []
        self._subagent_runs: list[dict] = []
        try:
            result = await super().run_once(prompt)
        finally:
            trace = self._tool_trace
            subagent_runs = self._subagent_runs
            self._tool_trace = []
            self._subagent_runs = []
        result["tool_trace"] = trace
        result["subagent_runs"] = subagent_runs
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

    async def _execute_agent_tool(self, inp: dict) -> str:
        """cow-investigator：按母版 launch 机制启动领域排查子 Agent；其他类型回落母版路径。"""
        if str(inp.get("type") or "") != SUBAGENT_TYPE:
            return await super()._execute_agent_tool(inp)

        description = str(inp.get("description") or "单牛排查")
        prompt = str(inp.get("prompt") or "")
        granted = [t for t in cow_tools.domain_tool_defs() if t["name"] in SUBAGENT_READ_ONLY_TOOLS]
        use_openai = self.use_openai and self._openai_client is not None
        sub_agent = CowAgent(
            model=self.model,
            api_base=str(self._openai_client.base_url) if use_openai else None,
            # 构造后即刻复用父会话客户端，此占位 key 不用于任何真实请求
            api_key="inherited-from-parent" if use_openai else None,
            custom_system_prompt=INVESTIGATOR_SYSTEM_PROMPT,
            custom_tools=granted,
            is_sub_agent=True,
            # 与母版修复一致的权限继承：default 不隐式升级 bypassPermissions，
            # 写操作意图仍 park 回父会话的审批 Future
            permission_mode=self.permission_mode,
            confirm_fn=self.confirm_fn,
        )
        if use_openai:
            # 父子共享同一个 LLM 客户端（离线演示时即注入的 fake client）
            sub_agent._openai_client = self._openai_client
        try:
            result = await sub_agent.run_once(prompt)
        except Exception as e:
            return f"Sub-agent error: {e}"
        self.total_input_tokens += result["tokens"]["input"]
        self.total_output_tokens += result["tokens"]["output"]

        # 被父会话审批拒绝的调用不会进入 _execute_tool_call，从消息历史补捞为证据：
        # assistant tool_calls 与 tool_result 按 id 配对，收集 "User denied" 的调用意图。
        proposed: dict[str, dict] = {}
        denied_calls: list[dict] = []
        for message in getattr(sub_agent, "_openai_messages", []):
            if not isinstance(message, dict):
                continue
            for tc in message.get("tool_calls") or []:
                try:
                    args = json.loads((tc.get("function") or {}).get("arguments") or "{}")
                except Exception:
                    args = {}
                proposed[tc.get("id") or ""] = {
                    "tool": (tc.get("function") or {}).get("name") or "",
                    "arguments": args,
                }
            if message.get("role") == "tool" and "denied" in str(message.get("content") or "").lower():
                intent = proposed.get(message.get("tool_call_id") or "")
                if intent:
                    denied_calls.append({**intent, "outcome": "denied_by_parent_session"})

        record = {
            "type": SUBAGENT_TYPE,
            "description": description,
            "prompt": prompt,
            "permission_mode": sub_agent.permission_mode,
            "confirm_fn_shared_with_parent": sub_agent.confirm_fn is self.confirm_fn,
            "tools_granted": [t["name"] for t in granted],
            "write_tools_excluded": sorted(cow_tools.WRITE_TOOLS),
            "tool_trace": result.get("tool_trace", []),
            "denied_tool_calls": denied_calls,
            "tokens": result["tokens"],
            "report": result["text"],
        }
        runs = getattr(self, "_subagent_runs", None)
        if runs is not None:
            runs.append(record)
        return result["text"] or "(子 Agent 无输出)"


def create_cow_agent(confirm_fn) -> CowAgent:
    return CowAgent(
        model=settings.LLM_MODEL,
        api_base=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        permission_mode="default",  # 不启用 plan 模式（母版 agent.py:1192 有 await bug）
        confirm_fn=confirm_fn,
        custom_system_prompt=SYSTEM_PROMPT,
        custom_tools=cow_agent_tools(),
        max_turns=settings.AGENT_MAX_TURNS,
    )
