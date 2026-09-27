"""历史完整性守卫：悬空 tool_calls（会话毒化）发送前补齐配对，只修不剥。

线上事实：真实 DeepSeek 评测中某轮在历史里留下带 tool_calls 的 assistant 消息
但缺少 tool 结果消息，下一轮起 DeepSeek 对该会话一律 400
（tool_calls must be followed by tool messages），此后所有轮次失败。
守卫落点：app/patch.py 的 _call_openai_stream 包装链路（repair_dangling_tool_calls）。
"""
import asyncio
import copy
import logging

from app.patch import REPAIR_NOTE, apply_patches, repair_dangling_tool_calls

apply_patches()

import agents.agent as agent_mod  # noqa: E402
from app.offline_fakes import FakeOpenAIClient  # noqa: E402


def _assistant_with_calls(*ids: str) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": i, "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
            for i in ids
        ],
    }


def _tool_result(tool_call_id: str, content: str = "ok") -> dict:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _pairing_gaps(messages: list) -> list[str]:
    """DeepSeek 视角的配对检查：返回仍悬空的 tool_call_id（应为空）。"""
    answered = {m.get("tool_call_id") for m in messages if isinstance(m, dict) and m.get("role") == "tool"}
    gaps = []
    for m in messages:
        if isinstance(m, dict) and m.get("tool_calls"):
            gaps.extend(tc["id"] for tc in m["tool_calls"] if tc.get("id") and tc["id"] not in answered)
    return gaps


def test_guard_repairs_dangling_and_keeps_scene_auditable():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "q1"},
        _assistant_with_calls("call_a", "call_b"),
        _tool_result("call_a", "档案数据"),          # 部分缺失：call_b 悬空
        {"role": "assistant", "content": "回答 1"},
        {"role": "user", "content": "q2"},
        _assistant_with_calls("call_c", "call_d"),   # 整组悬空（0/2 有结果）
        {"role": "user", "content": "q3"},            # 会话毒化后用户仍在发问
    ]
    before = copy.deepcopy(messages)

    repaired = repair_dangling_tool_calls(messages, session_id="sess-test")

    assert repaired == ["call_b", "call_c", "call_d"]
    assert _pairing_gaps(messages) == []
    # 只修不剥：原有消息全部保留、内容与顺序不变，合成消息插入在各自工具块之后
    original_items = [m for m in messages if m.get("content") != REPAIR_NOTE]
    assert original_items == before
    synthetic = [m for m in messages if m.get("content") == REPAIR_NOTE]
    assert [m["tool_call_id"] for m in synthetic] == ["call_b", "call_c", "call_d"]
    assert all(m["role"] == "tool" for m in synthetic)
    # 合成消息位置：call_b 的补在 call_a 结果之后、assistant 文本之前；
    # call_c/call_d 的补在悬空 assistant 之后、下一条 user 之前
    idx = {id(m): pos for pos, m in enumerate(messages)}
    by_tid = {m.get("tool_call_id"): m for m in messages if m.get("role") == "tool"}
    assistant_text = next(m for m in messages if m.get("content") == "回答 1")
    user_q3 = next(m for m in messages if m.get("content") == "q3")
    assert idx[id(by_tid["call_b"])] < idx[id(assistant_text)]
    assert idx[id(by_tid["call_d"])] < idx[id(user_q3)]


def test_guard_leaves_healthy_history_untouched():
    healthy = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "q"},
        _assistant_with_calls("call_a"),
        _tool_result("call_a"),
        {"role": "assistant", "content": "最终回复"},
        {"role": "assistant", "content": "无工具回复", "tool_calls": []},  # 空 tool_calls
        {"role": "user", "content": "q2"},
    ]
    before = copy.deepcopy(healthy)
    assert repair_dangling_tool_calls(healthy, session_id="sess-ok") == []
    assert healthy == before, "正常历史必须零改动"


def test_guard_end_to_end_via_send_path(caplog):
    """走真实发送链路：毒化历史 → run_once → 守卫修复 + WARNING 日志 + LLM 请求配对完整。"""
    agent = agent_mod.Agent(
        permission_mode="default",
        model="fake-model",
        api_base="http://offline-fake.local/v1",
        api_key="fake-key",
        custom_system_prompt="test",
        custom_tools=[],
    )
    fake_llm = FakeOpenAIClient(main_script=[{"content": "修复后正常回复"}])
    agent._openai_client = fake_llm
    # 模拟线上事故现场：skill/read_file 那轮的 assistant tool_calls 没有对应 tool 结果
    agent._openai_messages.append({"role": "user", "content": "帮我看看这个 skill 文件"})
    agent._openai_messages.append(_assistant_with_calls("call_dangling_1"))

    with caplog.at_level(logging.WARNING, logger="cow-agent.patch"):
        result = asyncio.run(agent.run_once("继续"))

    assert result["text"].strip() == "修复后正常回复"
    assert any(
        "repaired 1 dangling tool_calls" in rec.message and "sess" in rec.message
        for rec in caplog.records
    ), caplog.text
    # 历史现场：合成 tool 消息已落盘配对，后续轮次不再重复修复
    history = agent._openai_messages
    synthetic = [m for m in history if m.get("content") == REPAIR_NOTE]
    assert len(synthetic) == 1
    # id 重写不回归：合成消息的 tool_call_id 已被成对重写为新的 call_* id
    assert synthetic[0]["tool_call_id"] != "call_dangling_1"
    assert synthetic[0]["tool_call_id"].startswith("call_")
    # 第二轮不再修复（幂等）
    caplog.clear()
    fake_llm._main.append({"content": "第二轮"})
    asyncio.run(agent.run_once("再来一轮"))
    assert not any("dangling" in rec.message for rec in caplog.records)
