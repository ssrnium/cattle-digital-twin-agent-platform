"""Fixed benchmark and context compression metrics remain reproducible."""

import shutil
from pathlib import Path

from app.evaluation import (
    evaluate_apibank_subset,
    evaluate_context_compression,
    evaluate_skills,
    evaluate_tool_calls,
)
from app.patch import apply_patches

apply_patches()

import agents.skills as skills_mod  # noqa: E402


def test_fixed_skill_and_tool_metrics(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "agent-home" / ".bear" / "skills"
    shutil.copytree(source, tmp_path / ".bear" / "skills")
    monkeypatch.chdir(tmp_path)
    skills_mod.reset_skill_cache()
    skill_report = evaluate_skills()
    tool_report = evaluate_tool_calls()
    assert skill_report["count"] == 16
    assert skill_report["negative_count"] == 2
    assert skill_report["metrics"]["skill_hit_rate"] == 1.0
    assert skill_report["metrics"]["ood_rejection_rate"] == 1.0
    assert tool_report["count"] == 12
    assert tool_report["metrics"]["tool_selection_accuracy"] == 1.0
    assert tool_report["metrics"]["argument_validity"] == 1.0
    assert tool_report["metrics"]["sequence_exact_rate"] == 1.0
    subset_report = evaluate_apibank_subset()
    assert subset_report["count"] == 26
    assert subset_report["metrics"]["argument_validity"] == 1.0
    assert subset_report["metrics"]["sequence_exact_rate"] == 1.0


def test_context_compression_reports_input_output_total_and_target_reduction():
    report = evaluate_context_compression()
    metrics = report["metrics"]
    assert metrics["average_total_tokens_before"] > metrics["average_total_tokens_after"]
    assert metrics["average_reduction_ratio"] >= 0.35
    for task in report["tasks"]:
        assert task["input_tokens_before"] > task["input_tokens_after"]
        assert task["output_tokens_before"] == task["output_tokens_after"]
        assert task["total_tokens_before"] > task["total_tokens_after"]
