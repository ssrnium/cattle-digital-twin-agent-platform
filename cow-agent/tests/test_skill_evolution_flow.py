"""Skill 自进化端到端：双 merge → rollback 到最近快照 → 重复 rollback 幂等 → discard → 审计链。"""

import json
from pathlib import Path

import pytest

from app.feedback import FeedbackError, FeedbackLedger
from app.patch import apply_patches

apply_patches()

import agents.skills as skills_mod  # noqa: E402
from agents.frontmatter import parse_frontmatter  # noqa: E402


def _write_skill(root: Path, name: str, body: str = "# Workflow\n\n- original rule\n") -> Path:
    path = root / ".bear" / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ndescription: test skill\nwhen_to_use: use {name}\nversion: 0.1.0\n---\n{body}",
        encoding="utf-8",
    )
    return path


def _version_of(path: Path) -> str:
    return str(parse_frontmatter(path.read_text(encoding="utf-8")).meta.get("version") or "")


def _audit_events(ledger: FeedbackLedger) -> list[dict]:
    return [
        json.loads(line) for line in ledger.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_double_merge_rollback_restores_latest_snapshot_idempotently(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_file = _write_skill(tmp_path, "lameness-check")
    skills_mod.reset_skill_cache()
    ledger = FeedbackLedger()
    original = skill_file.read_text(encoding="utf-8")

    c1 = ledger.submit(skill_name="lameness-check", lesson="结论必须引用 event_id")
    d1 = ledger.decide(c1["candidate_id"], "merge")
    assert d1["status"] == "merged"
    assert _version_of(skill_file) == "0.1.1"
    content_v1 = skill_file.read_text(encoding="utf-8")
    assert content_v1 != original

    c2 = ledger.submit(skill_name="lameness-check", lesson="活动量低于 0.4 时给出健康状态字段")
    d2 = ledger.decide(c2["candidate_id"], "merge")
    assert d2["status"] == "merged"
    assert _version_of(skill_file) == "0.1.2"

    # merge 前快照：history 两条，分别是 original(0.1.0) 与 v1(0.1.1) 内容
    history = tmp_path / ".bear" / "skill-evolution" / "history" / "lameness-check.jsonl"
    snapshots = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()]
    assert [s["version"] for s in snapshots] == ["0.1.0", "0.1.1"]
    assert snapshots[0]["content"] == original
    assert snapshots[1]["content"] == content_v1

    # rollback 恢复最近一次快照（v1），不是一路退回 original
    rb1 = ledger.rollback("lameness-check")
    assert rb1["ok"] is True and rb1["restored_version"] == "0.1.1"
    assert skill_file.read_text(encoding="utf-8") == content_v1

    # 边界：快照 append-only 不弹栈，重复 rollback 幂等于同一快照，不会继续回退
    rb2 = ledger.rollback("lameness-check")
    assert rb2["ok"] is True and rb2["restored_version"] == "0.1.1"
    assert skill_file.read_text(encoding="utf-8") == content_v1


def test_discard_leaves_skill_untouched_and_audit_chain_ordered(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_file = _write_skill(tmp_path, "lameness-check")
    skills_mod.reset_skill_cache()
    ledger = FeedbackLedger()
    before = skill_file.read_text(encoding="utf-8")

    merged = ledger.submit(skill_name="lameness-check", lesson="值得沉淀的规则")
    discarded = ledger.submit(skill_name="lameness-check", lesson="一次性口误纠正")
    ledger.decide(merged["candidate_id"], "merge")
    ledger.rollback("lameness-check")
    d = ledger.decide(discarded["candidate_id"], "discard")
    assert d["status"] == "discarded"
    assert skill_file.read_text(encoding="utf-8") == before, "discard 不得改动 skill 文件"

    # 已决策候选不可重复决策
    with pytest.raises(FeedbackError):
        ledger.decide(discarded["candidate_id"], "merge")

    # 审计链：append-only JSONL 事件完整、有序、时间单调
    events = _audit_events(ledger)
    assert [e["event"] for e in events] == [
        "candidate_submitted", "candidate_submitted",
        "candidate_decided", "skill_rollback", "candidate_decided",
    ]
    times = [str(e.get("time") or "") for e in events]
    assert times == sorted(times)
    statuses = {e["candidate_id"]: e["status"] for e in events if e["event"] == "candidate_decided"}
    assert statuses == {merged["candidate_id"]: "merged", discarded["candidate_id"]: "discarded"}
