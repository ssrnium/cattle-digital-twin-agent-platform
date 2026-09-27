"""子 Agent 实战演示：ZONE-B 多头异常牛排查 + 建单审批，全链路离线确定性。

- LLM：app.offline_fakes.FakeOpenAIClient 脚本回放（不花真实 API 额度，可复跑）；
- cow-admin：罐头 MockTransport（ZONE-B 两头异常牛：COW-0042 爬跨 ×2、COW-0057 跛行）；
- 走 runtime 真实子 Agent 机制：主 Agent 的 agent 工具 → CowAgent._execute_agent_tool
  → 子 CowAgent 独立 run_once 循环（只挂只读领域工具，继承父 permission_mode + confirm_fn）；
- 第二轮演示写操作闭环：建单意图 park 到主会话 confirm_fn，批准后才到达（罐头）后端。

运行：PYTHONUTF8=1 .venv/Scripts/python.exe scripts/demo_subagent_investigation.py
证据：docs/evidence/subagent_investigation_demo.json
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import cow_tools  # noqa: E402
from app.cow_agent import (  # noqa: E402
    SUBAGENT_TYPE,
    CowAgent,
    cow_agent_tools,
)
from app.offline_fakes import FakeOpenAIClient, make_fake_admin_transport  # noqa: E402
from app.patch import apply_patches  # noqa: E402

apply_patches()  # 领域写工具确认拦截 + CLI 输出静音，与生产服务一致

Q1 = "ZONE-B 最近异常的几头牛都什么情况？"
Q2 = "那就给 COW-0057 开一张兽医检查工单，依据是它的跛行事件。"

MAIN_SCRIPT = [
    # 第 1 轮：圈定 ZONE-B 异常牛清单 → 逐头下发 cow-investigator 子 Agent → 汇总
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
    {"content": "ZONE-B 近期异常共 2 头：\n"
                "1) COW-0042：疑似发情，证据 EVT-2026-092701 / EVT-2026-092702（爬跨 ×2），建议繁殖复核；\n"
                "2) COW-0057：跛行，证据 EVT-2026-092703，活动量降至 0.31，建议兽医检查。"},
    # 第 2 轮：用户明确要求建单 → 主会话走确认通道 → 批准后执行写工具
    {"tool_calls": [{"name": "create_work_order", "arguments": {
        "type": "VET_CHECK", "cow_id": "COW-0057",
        "source_event_id": "EVT-2026-092703", "priority": "NORMAL",
        "description": "跛行复核：LAMENESS 事件 EVT-2026-092703，活动量 0.31，建议兽医检查。",
    }}]},
    {"content": "已创建兽医检查工单 WO-20260927-0001（COW-0057，依据 EVT-2026-092703）。"},
]

INVESTIGATOR_SCRIPTS = [
    [
        {"tool_calls": [
            {"name": "query_cow_profile", "arguments": {"cow_id": "COW-0042"}},
            {"name": "query_cow_timeline", "arguments": {"cow_id": "COW-0042", "limit": 10}},
        ]},
        {"content": "COW-0042 排查报告：疑似发情（SUSPECTED_HEAT）。"
                    "证据：EVT-2026-092701（爬跨 0.87）、EVT-2026-092702（爬跨 0.81），"
                    "时间线含发情推断记录。建议：繁殖复核，如需建单请主 Agent 走确认通道。"},
    ],
    [
        {"tool_calls": [
            {"name": "query_cow_profile", "arguments": {"cow_id": "COW-0057"}},
        ]},
        {"tool_calls": [
            {"name": "query_cow_timeline", "arguments": {"cow_id": "COW-0057", "limit": 10}},
        ]},
        {"content": "COW-0057 排查报告：跛行待复核。证据：EVT-2026-092703（跛行 0.76），"
                    "活动量 0.31、健康状态 ATTENTION。建议：兽医检查工单（写操作归主会话审批）。"},
    ],
]


async def run_demo() -> dict:
    transport, admin_state = make_fake_admin_transport()
    original_admin = cow_tools.admin_client
    cow_tools.admin_client = cow_tools.AdminClient(transport=transport)

    confirmations: list[dict] = []

    async def confirm(message: str) -> bool:
        payload = json.loads(message)
        confirmations.append({"message": payload, "decision": "approved"})
        return True  # 演示：场长在前端点击批准

    fake_llm = FakeOpenAIClient(MAIN_SCRIPT, INVESTIGATOR_SCRIPTS)
    agent = CowAgent(
        model="fake-model",
        api_base="http://offline-fake.local/v1",
        api_key="fake-key",
        permission_mode="default",
        confirm_fn=confirm,
        custom_system_prompt="牧场主 Agent（离线演示）",
        custom_tools=cow_agent_tools(),
        max_turns=12,
    )
    agent._openai_client = fake_llm

    try:
        turn1 = await agent.run_once(Q1)
        turn2 = await agent.run_once(Q2)
    finally:
        cow_tools.admin_client = original_admin

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "deterministic": "LLM 为脚本化 FakeOpenAIClient，cow-admin 为罐头 MockTransport，可重复运行结果一致",
        "scenario": {
            "name": "ZONE-B 多头异常牛并行排查 + 建单审批",
            "turns": [
                {"user": Q1, "expectation": "主 Agent 用 list_events 圈定异常牛，"
                                           "逐头启动 cow-investigator 子 Agent（只读），汇总报告"},
                {"user": Q2, "expectation": "写工具 create_work_order park 到主会话 confirm_fn，"
                                           "批准后才执行（PENDING_ACTION 链路在真实部署中等价）"},
            ],
        },
        "permission_boundary": {
            "subagent_type": SUBAGENT_TYPE,
            "subagent_launch_path": "agent 工具 → CowAgent._execute_agent_tool（app/cow_agent.py）"
                                    " → 子 CowAgent.run_once 独立循环（与母版 agent.py:1277 同一 launch 机制）",
            "write_tools_parent_only": sorted(cow_tools.WRITE_TOOLS),
            "permission_mode": "default（子 Agent 继承，不隐式升级 bypassPermissions）",
        },
        "turns": [
            {
                "user": Q1,
                "answer": turn1["text"],
                "tokens": turn1["tokens"],
                "main_tool_trace": turn1["tool_trace"],
                "subagent_runs": turn1["subagent_runs"],
            },
            {
                "user": Q2,
                "answer": turn2["text"],
                "tokens": turn2["tokens"],
                "main_tool_trace": turn2["tool_trace"],
                "confirmations": confirmations,
            },
        ],
        "llm_calls": fake_llm.calls,
        "backend_writes": admin_state["work_orders"],
    }


def main() -> int:
    # 在临时目录里跑，bear 运行时的会话/大结果落盘不污染 agent-home
    output = PROJECT_ROOT / "docs" / "evidence" / "subagent_investigation_demo.json"
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="cow-subagent-demo-") as sandbox:
        os.chdir(sandbox)
        try:
            report = asyncio.run(run_demo())
        finally:
            os.chdir(original_cwd)
    report["permission_boundary"]["subagent_tools"] = sorted(
        report["turns"][0]["subagent_runs"][0]["tools_granted"]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    turn1 = report["turns"][0]
    print(f"Q1: {report['turns'][0]['user']}")
    for run in turn1["subagent_runs"]:
        tools = ", ".join(t["tool"] for t in run["tool_trace"])
        print(f"  子 Agent[{run['description']}]: 工具[{tools}] → {run['report'][:60]}...")
    print(f"Q2: {report['turns'][1]['user']}")
    print(f"  审批: {report['turns'][1]['confirmations']}")
    print(f"  后端建单: {report['backend_writes']}")
    print(f"evidence written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
