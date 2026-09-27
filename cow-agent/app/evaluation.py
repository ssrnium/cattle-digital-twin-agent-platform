"""Deterministic Agent runtime benchmarks.

These checks deliberately run without an LLM. They isolate the contracts that
must remain true when a model is attached: skill retrieval, tool schemas and
argument validity, and context folding. A live model run can add its trace to
the same report later without changing the metrics or the fixed dataset.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from app.cow_tools import TOOL_DEFS
from app.patch import apply_patches

apply_patches()

from agents.session_memory import fallback_folded_memory, format_folded_memory  # noqa: E402
from agents.skills import reset_skill_cache, retrieve_relevant_skills  # noqa: E402


EVAL_ROOT = Path(__file__).resolve().parents[1] / "eval"

# 域外负例判定阈值：与 retrieve_relevant_skills 的生产默认 min_score 一致。
# 负例（expected_skill=null）要求 Top-1 分数低于该阈值，即线上默认阈值下不会注入任何 skill。
OOD_MIN_SCORE = 0.08


def _load_cases(name: str) -> list[dict[str, Any]]:
    return json.loads((EVAL_ROOT / name).read_text(encoding="utf-8"))


def evaluate_skills(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    reset_skill_cache()
    rows: list[dict[str, Any]] = []
    cases = cases or _load_cases("skill_benchmark.json")
    for case in cases:
        hits = retrieve_relevant_skills(case["query"], limit=3, min_score=0.0)
        expected = case.get("expected_skill")
        top = hits[0]["name"] if hits else ""
        top_score = round(float(hits[0]["score"]), 4) if hits else 0.0
        negative = expected is None
        if negative:
            rank = 0
            hit = not hits or top_score < OOD_MIN_SCORE
        else:
            rank = next((index + 1 for index, item in enumerate(hits) if item["name"] == expected), 0)
            hit = top == expected
        rows.append({
            "id": case["id"],
            "expected_skill": expected,
            "negative": negative,
            "top_skill": top,
            "top_score": top_score,
            "rank": rank,
            "hit": hit,
            "candidates": [{"name": item["name"], "score": round(float(item["score"]), 4)} for item in hits],
        })
    positives = [row for row in rows if not row["negative"]]
    negatives = [row for row in rows if row["negative"]]
    metrics: dict[str, Any] = {
        "skill_hit_rate": sum(1 for row in positives if row["hit"]) / len(positives) if positives else 0.0,
        "skill_mrr": sum((1 / row["rank"]) if row["rank"] else 0.0 for row in positives) / len(positives) if positives else 0.0,
    }
    if negatives:
        metrics["ood_rejection_rate"] = sum(1 for row in negatives if row["hit"]) / len(negatives)
    return {
        "dataset": "eval/skill_benchmark.json",
        "count": len(rows),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "metrics": metrics,
        "cases": rows,
    }


def _tool_schema(name: str) -> dict[str, Any] | None:
    for definition in TOOL_DEFS:
        if definition.get("name") == name:
            return definition.get("input_schema") or {}
    return None


def validate_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    schema = _tool_schema(name)
    if schema is None:
        return {"valid": False, "errors": [f"unknown tool: {name}"]}
    errors: list[str] = []
    properties = schema.get("properties") or {}
    for required in schema.get("required") or []:
        if required not in arguments:
            errors.append(f"missing required argument: {required}")
    for key, value in arguments.items():
        expected = (properties.get(key) or {}).get("type")
        if expected == "string" and not isinstance(value, str):
            errors.append(f"{key} expected string")
        elif expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            errors.append(f"{key} expected integer")
    return {"valid": not errors, "errors": errors}


def _plan_tool_calls(query: str) -> list[dict[str, Any]]:
    """Small deterministic planner used to replay the fixed tool contract."""
    upper = query.upper()
    cow = re.search(r"COW-\d+", upper)
    cow_id = cow.group(0) if cow else "COW-0042"
    device = re.search(r"CAM-\d+", upper)
    device_id = device.group(0) if device else "CAM-03"
    create_intent = (
        "创建" in query
        or "新建" in query
        or re.search(r"建.{0,2}工单", query)
        or re.search(r"开.{0,3}工单", query)
    )
    if create_intent:
        if "DEVICE_REPAIR" in upper or "设备" in query:
            arguments: dict[str, Any] = {
                "type": "DEVICE_REPAIR",
                "device_id": device_id,
                "priority": "HIGH" if ("HIGH" in upper or "紧急" in query or "高优" in query) else "NORMAL",
                "description": f"设备 {device_id} 需现场检修",
            }
            source = re.search(r"E-\d+", upper)
            if source:
                arguments["source_event_id"] = source.group(0)
            return [{"name": "create_work_order", "arguments": arguments}]
        event = re.search(r"E-\d+", upper)
        event_id = event.group(0) if event else "E-100"
        return [{
            "name": "create_work_order",
            "arguments": {
                "type": "VET_CHECK",
                "cow_id": cow_id,
                "source_event_id": event_id,
                "priority": "HIGH",
                "description": f"依据 {event_id} 对 {cow_id} 做兽医检查",
            },
        }]
    if "工单" in query:
        arguments = {}
        for token in ("NEW", "DISPATCHED", "PROCESSING", "PENDING_REVIEW", "CLOSED", "CANCELLED"):
            if token in upper:
                arguments["state"] = token
                break
        if "state" not in arguments:
            for word, state in (("待复核", "PENDING_REVIEW"), ("待处理", "NEW"), ("已关闭", "CLOSED")):
                if word in query:
                    arguments["state"] = state
                    break
        for token in ("VET_CHECK", "BREEDING_REVIEW", "DEVICE_REPAIR"):
            if token in upper:
                arguments["type"] = token
                break
        if "type" not in arguments:
            for word, order_type in (("兽医", "VET_CHECK"), ("繁育", "BREEDING_REVIEW"), ("繁殖", "BREEDING_REVIEW"), ("设备维修", "DEVICE_REPAIR")):
                if word in query:
                    arguments["type"] = order_type
                    break
        return [{"name": "list_work_orders", "arguments": arguments}]
    if "孪生" in query or "全棚" in query or "整棚" in query:
        if cow:
            return [
                {"name": "get_twin_states", "arguments": {}},
                {"name": "query_cow_profile", "arguments": {"cow_id": cow_id}},
            ]
        return [{"name": "get_twin_states", "arguments": {}}]
    if "DEVICE_OFFLINE" in upper or "设备" in query or "摄像头" in query:
        return [
            {"name": "list_devices", "arguments": {}},
            {"name": "list_events", "arguments": {"event_type": "DEVICE_OFFLINE", "device_id": device_id}},
        ]
    if "事件" in query and cow is None:
        event_type = "LAMENESS" if ("LAMENESS" in upper or "跛行" in query) else "MOUNTING"
        return [{"name": "list_events", "arguments": {"event_type": event_type}}]
    if cow is not None and "时间线" in query:
        return [{"name": "query_cow_timeline", "arguments": {"cow_id": cow_id}}]
    if cow is not None and ("档案" in query or "资料" in query):
        return [{"name": "query_cow_profile", "arguments": {"cow_id": cow_id}}]
    event_type = "LAMENESS" if "LAMENESS" in upper or "跛行" in query else "MOUNTING"
    return [
        {"name": "query_cow_profile", "arguments": {"cow_id": cow_id}},
        {"name": "list_events", "arguments": {"event_type": event_type, "cow_id": cow_id}},
        {"name": "query_cow_timeline", "arguments": {"cow_id": cow_id}},
    ] if event_type == "MOUNTING" else [
        {"name": "list_events", "arguments": {"event_type": event_type, "cow_id": cow_id}},
        {"name": "query_cow_profile", "arguments": {"cow_id": cow_id}},
        {"name": "query_cow_timeline", "arguments": {"cow_id": cow_id}},
    ]


def evaluate_tool_calls(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases = cases or _load_cases("tool_benchmark.json")
    rows: list[dict[str, Any]] = []
    selected = 0
    valid = 0
    exact = 0
    total_calls = 0
    for case in cases:
        expected = case["expected"]
        observed = _plan_tool_calls(case["query"])
        expected_names = [item["name"] for item in expected]
        observed_names = [item["name"] for item in observed]
        selected += sum(a == b for a, b in zip(expected_names, observed_names))
        total_calls += len(expected_names)
        validations = [validate_tool_call(item["name"], item["arguments"]) for item in observed]
        valid += sum(1 for item in validations if item["valid"])
        exact += int(observed == expected)
        rows.append({
            "id": case["id"],
            "expected": expected,
            "observed": observed,
            "argument_validation": validations,
            "sequence_exact": observed == expected,
        })
    count = len(rows)
    return {
        "dataset": "eval/tool_benchmark.json",
        "count": count,
        "metrics": {
            "tool_selection_accuracy": selected / total_calls if total_calls else 0.0,
            "argument_validity": valid / total_calls if total_calls else 0.0,
            "sequence_exact_rate": exact / count if count else 0.0,
        },
        "cases": rows,
    }


def estimate_tokens(text: str) -> int:
    """Stable offline estimate: CJK characters count once, ASCII chunks four chars."""
    text = str(text or "")
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    non_cjk = re.sub(r"[\u4e00-\u9fff]", "", text)
    return max(1, cjk + math.ceil(len(non_cjk) / 4))


def evaluate_context_compression() -> dict[str, Any]:
    tasks = [
        ("cow-investigation", "分析 COW-0042 的异常事件并给出下一步排查动作。"),
        ("device-recovery", "设备 CAM-03 离线后恢复，核对补传和工单状态。"),
        ("breeding-review", "复核 MOUNTING 事件是否满足繁育员复检条件。"),
        ("daily-report", "给场长输出今日风险日报和待确认事项。"),
    ]
    rows: list[dict[str, Any]] = []
    for task_id, prompt in tasks:
        repeated_evidence = "\n".join(
            f"tool_result[{index}] event_id=E-{100 + index} cow_id=COW-0042 observation="
            + ("stable baseline; no new risk; verify evidence_ref before action. " * 10)
            for index in range(1, 31)
        )
        transcript = f"user: {prompt}\nassistant: I will inspect the evidence.\n{repeated_evidence}\nassistant: pending final recommendation."
        folded = format_folded_memory(fallback_folded_memory(transcript))
        output = "建议保留证据引用，先完成只读复核，再由场长确认写操作。"
        before_output = estimate_tokens(output)
        after_output = before_output
        before_total = estimate_tokens(transcript) + before_output
        after_total = estimate_tokens(folded) + after_output
        rows.append({
            "task_id": task_id,
            "model": "deepseek-flash",
            "input_tokens_before": estimate_tokens(transcript),
            "input_tokens_after": estimate_tokens(folded),
            "output_tokens_before": before_output,
            "output_tokens_after": after_output,
            "total_tokens_before": before_total,
            "total_tokens_after": after_total,
            "reduction_ratio": 1 - (after_total / before_total),
        })
    avg_before = sum(row["total_tokens_before"] for row in rows) / len(rows)
    avg_after = sum(row["total_tokens_after"] for row in rows) / len(rows)
    return {
        "method": "same fixed task transcripts, same model label, deterministic session_memory fallback folding, offline token estimate",
        "count": len(rows),
        "metrics": {
            "average_total_tokens_before": avg_before,
            "average_total_tokens_after": avg_after,
            "average_reduction_ratio": 1 - (avg_after / avg_before) if avg_before else 0.0,
        },
        "tasks": rows,
    }


def evaluate_apibank_subset() -> dict[str, Any]:
    """API-Bank 公开基准改写子集：来源与转换方法见文件内 _meta。"""
    payload = json.loads((EVAL_ROOT / "tool_benchmark_apibank_subset.json").read_text(encoding="utf-8"))
    report = evaluate_tool_calls(payload["cases"])
    report["dataset"] = "eval/tool_benchmark_apibank_subset.json"
    report["source"] = payload["_meta"]
    return report


def run_runtime_evaluation() -> dict[str, Any]:
    return {
        "skill_eval": evaluate_skills(),
        "tool_eval": evaluate_tool_calls(),
        "tool_eval_apibank_subset": evaluate_apibank_subset(),
        "context_compression": evaluate_context_compression(),
    }
