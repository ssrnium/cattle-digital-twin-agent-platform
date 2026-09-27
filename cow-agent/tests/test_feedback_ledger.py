"""Explicit add/merge/discard feedback flow with snapshot rollback."""

from pathlib import Path

from app.feedback import FeedbackLedger
from app.patch import apply_patches

apply_patches()

import agents.skills as skills_mod  # noqa: E402


def _write_skill(root: Path, name: str, body: str = "# Workflow\n\n- original rule\n") -> Path:
    path = root / ".bear" / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ndescription: test skill\nwhen_to_use: use {name}\nversion: 0.1.0\n---\n{body}",
        encoding="utf-8",
    )
    return path


def test_feedback_add_merge_discard_and_rollback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original = _write_skill(tmp_path, "existing-skill")
    skills_mod.reset_skill_cache()
    ledger = FeedbackLedger()

    merge_candidate = ledger.submit(
        skill_name="existing-skill",
        lesson="Keep a concrete evidence reference in every conclusion.",
        rationale="review feedback",
    )
    merged = ledger.decide(merge_candidate["candidate_id"], "merge")
    assert merged["status"] == "merged"
    assert "evidence reference" in original.read_text(encoding="utf-8")
    assert merged["result"]["version"] == "0.1.1"

    rollback = ledger.rollback("existing-skill")
    assert rollback["ok"] is True
    assert original.read_text(encoding="utf-8").endswith("- original rule\n")

    add_candidate = ledger.submit(
        skill_name="new-skill",
        lesson="Run the read-only checks before proposing a write action.",
        description="Approval-aware operational checks",
        instructions="# Workflow\n\n1. Run read-only checks.\n2. Request approval.\n",
    )
    added = ledger.decide(add_candidate["candidate_id"], "add")
    assert added["status"] == "added"
    assert (tmp_path / ".bear" / "skills" / "new-skill" / "SKILL.md").is_file()

    discard_candidate = ledger.submit(skill_name="discarded-skill", lesson="One-off correction")
    discarded = ledger.decide(discard_candidate["candidate_id"], "discard")
    assert discarded["status"] == "discarded"
    assert not (tmp_path / ".bear" / "skills" / "discarded-skill").exists()
