"""Explicit feedback-to-Skill ledger used by the runtime evidence flow.

The production agent keeps automatic LLM skill evolution disabled. This module
retains the useful part of that design as an auditable, human-approved state
machine: submit a candidate, choose add/merge/discard, and roll a merge back to
the snapshot written before it.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.patch import apply_patches

apply_patches()

from agents.skills import create_skill, evolve_skill, rollback_skill  # noqa: E402


class FeedbackError(ValueError):
    """Invalid state transition or incomplete feedback candidate."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class FeedbackLedger:
    """Append-only feedback candidates and decisions for one Agent home."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or (Path.cwd() / ".bear" / "skill-evolution"))
        self.path = self.root / "feedback_candidates.jsonl"

    def _append(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def submit(
        self,
        *,
        skill_name: str,
        lesson: str,
        rationale: str = "",
        description: str = "",
        instructions: str = "",
        when_to_use: str = "",
        target: str = "project",
        evidence: str = "",
    ) -> dict[str, Any]:
        skill_name = str(skill_name or "").strip()
        lesson = str(lesson or "").strip()
        target = str(target or "project").strip().lower()
        if not skill_name or not lesson:
            raise FeedbackError("skill_name and lesson are required")
        if target not in {"project", "active"}:
            raise FeedbackError("feedback writes are limited to project skills")
        candidate = {
            "candidate_id": uuid.uuid4().hex[:12],
            "event": "candidate_submitted",
            "status": "pending",
            "time": _now(),
            "skill_name": skill_name,
            "lesson": lesson,
            "rationale": str(rationale or "").strip(),
            "description": str(description or "").strip(),
            "instructions": str(instructions or "").strip(),
            "when_to_use": str(when_to_use or "").strip(),
            "target": target,
            "evidence": str(evidence or "").strip(),
        }
        self._append(candidate)
        return candidate

    def _latest(self, candidate_id: str) -> dict[str, Any] | None:
        latest: dict[str, Any] | None = None
        for event in self._events():
            if event.get("candidate_id") == candidate_id:
                latest = event
        return latest

    def list(self) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for event in self._events():
            candidate_id = str(event.get("candidate_id") or "")
            if candidate_id:
                # Keep the candidate payload while applying each later event
                # as a state update, so the API remains useful after a
                # decision instead of returning only the final audit row.
                latest[candidate_id] = {**latest.get(candidate_id, {}), **event}
        return sorted(latest.values(), key=lambda item: str(item.get("time") or ""))

    def decide(self, candidate_id: str, action: str) -> dict[str, Any]:
        candidate = self._latest(str(candidate_id or "").strip())
        if not candidate:
            raise FeedbackError(f"feedback candidate not found: {candidate_id}")
        if candidate.get("status") != "pending":
            raise FeedbackError(f"candidate is already {candidate.get('status')}")
        action = str(action or "").strip().lower()
        if action not in {"add", "merge", "discard"}:
            raise FeedbackError("action must be add, merge, or discard")

        result: dict[str, Any]
        if action == "discard":
            result = {"ok": True, "action": "discard", "skill": candidate["skill_name"]}
            status = "discarded"
        elif action == "merge":
            result = evolve_skill(
                skill_name=candidate["skill_name"],
                lesson=candidate["lesson"],
                rationale=candidate.get("rationale", "feedback merge"),
                target="active",
                instructions=candidate.get("instructions", ""),
                description=candidate.get("description", ""),
                when_to_use=candidate.get("when_to_use", ""),
            )
            status = "merged" if result.get("ok") else "failed"
        else:
            description = candidate.get("description") or f"Reusable guidance for {candidate['skill_name']}"
            instructions = candidate.get("instructions") or candidate["lesson"]
            result = create_skill(
                name=candidate["skill_name"],
                description=description,
                instructions=instructions,
                when_to_use=candidate.get("when_to_use", ""),
                target=candidate.get("target", "project"),
                context="inline",
                user_invocable=False,
                evidence=candidate.get("evidence", ""),
                actor="feedback",
            )
            status = "added" if result.get("ok") else "failed"

        decision = {
            "candidate_id": candidate["candidate_id"],
            "event": "candidate_decided",
            "status": status,
            "action": action,
            "time": _now(),
            "skill_name": candidate["skill_name"],
            "result": result,
        }
        self._append(decision)
        if status == "failed":
            raise FeedbackError(str(result.get("error") or "feedback action failed"))
        return {**candidate, **decision}

    def rollback(self, skill_name: str) -> dict[str, Any]:
        result = rollback_skill(skill_name, target="active")
        if not result.get("ok"):
            raise FeedbackError(str(result.get("error") or "rollback failed"))
        self._append({
            "event": "skill_rollback",
            "status": "rolled_back",
            "time": _now(),
            "skill_name": skill_name,
            "result": result,
        })
        return result
