"""Skill 自进化端到端演示：feedback → candidate → merge → 快照 → rollback → 审计链。

全流程在 agent-home/.bear/skills 的**临时副本**里跑（不污染 agent-home），
覆盖两条决策路径与边界行为：
1. merge：版本 +1、merge 前快照写入 history/*.jsonl；
2. 再次 merge 后 rollback：恢复到最近一次快照（而非最早版本）；
3. 重复 rollback：快照是 append-only，不弹栈，幂等于最近快照（不会继续回退）；
4. discard：skill 文件零改动，候选标记 discarded；
5. 审计链：feedback_candidates.jsonl 事件完整、有序、时间单调。

运行：PYTHONUTF8=1 .venv/Scripts/python.exe scripts/demo_skill_evolution.py
证据：docs/evidence/skill_evolution_demo.json
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.feedback import FeedbackLedger  # noqa: E402
from app.patch import apply_patches  # noqa: E402

apply_patches()

import agents.skills as skills_mod  # noqa: E402
from agents.frontmatter import parse_frontmatter  # noqa: E402

SKILL_NAME = "lameness-check"
SKILLS_SOURCE = PROJECT_ROOT / "agent-home" / ".bear" / "skills"


def _tree_digest(root: Path) -> str:
    """目录树整体指纹：相对路径 + 文件内容哈希，用于零污染校验。"""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _skill_file(root: Path) -> Path:
    return root / ".bear" / "skills" / SKILL_NAME / "SKILL.md"


def _version_of(path: Path) -> str:
    return str(parse_frontmatter(path.read_text(encoding="utf-8")).meta.get("version") or "")


def run_demo(sandbox: Path) -> tuple[list[dict], list[str]]:
    steps: list[dict] = []
    failures: list[str] = []

    def record(step: str, ok: bool, **details) -> None:
        steps.append({"step": step, "ok": bool(ok), **details})
        if not ok:
            failures.append(step)

    # 步骤 0：agent-home 原目录整体指纹（演示结束时校验零污染；
    # .bear/skill-evolution 可能已有历史运行残留，故比对整树而非断言不存在）
    agent_home_bear = SKILLS_SOURCE.parent
    bear_digest_before = _tree_digest(agent_home_bear)

    work = sandbox / "agent-home-copy"
    shutil.copytree(SKILLS_SOURCE, work / ".bear" / "skills")
    os.chdir(work)
    skills_mod.reset_skill_cache()
    ledger = FeedbackLedger()
    skill_file = _skill_file(work)

    # 步骤 1：用户反馈 → 候选 → merge → 版本 +1 且 merge 前快照存在
    original_content = skill_file.read_text(encoding="utf-8")
    original_version = _version_of(skill_file)
    c1 = ledger.submit(
        skill_name=SKILL_NAME,
        lesson="跛行结论必须同时引用 LAMENESS 事件 event_id 与时间线活动量变化，缺一则标注数据不足。",
        rationale="场长反馈：排查结论证据不完整",
        evidence="2026-09-27 场长 review COW-0057 排查报告",
    )
    d1 = ledger.decide(c1["candidate_id"], "merge")
    history_path = work / ".bear" / "skill-evolution" / "history" / f"{SKILL_NAME}.jsonl"
    snapshots = [
        json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if history_path.is_file() else []
    v1 = _version_of(skill_file)
    record(
        "merge#1", d1["status"] == "merged" and v1 != original_version and len(snapshots) == 1,
        candidate_id=c1["candidate_id"], version_before=original_version, version_after=v1,
        snapshot_count=len(snapshots), snapshot_version=snapshots[0]["version"] if snapshots else None,
        snapshot_content_matches_original=bool(snapshots) and snapshots[0]["content"] == original_content,
    )
    content_v1 = skill_file.read_text(encoding="utf-8")

    # 步骤 2：第二次 merge → 版本再 +1，快照增至 2 条
    c2 = ledger.submit(
        skill_name=SKILL_NAME,
        lesson="活动量低于 0.4 时在报告中显式给出健康状态字段（如 ATTENTION）。",
        rationale="兽医反馈：报告缺少健康状态结论",
    )
    d2 = ledger.decide(c2["candidate_id"], "merge")
    snapshots = [
        json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    v2 = _version_of(skill_file)
    record(
        "merge#2", d2["status"] == "merged" and v2 != v1 and len(snapshots) == 2,
        candidate_id=c2["candidate_id"], version_before=v1, version_after=v2,
        snapshot_count=len(snapshots),
        latest_snapshot_content_matches_v1=snapshots[-1]["content"] == content_v1,
    )

    # 步骤 3：rollback → 恢复到最近一次快照（merge#2 之前的 v1 内容，不是最早的 original）
    rb1 = ledger.rollback(SKILL_NAME)
    restored = skill_file.read_text(encoding="utf-8")
    record(
        "rollback#1", rb1.get("ok") is True and restored == content_v1,
        restored_version=rb1.get("restored_version"),
        content_matches_v1=restored == content_v1,
        content_matches_original=restored == original_content,
        note="恢复快照栈顶（merge#2 前），不是一路回退到最初版本",
    )

    # 步骤 4：重复 rollback（边界）→ 快照 append-only 不弹栈，幂等于同一快照
    rb2 = ledger.rollback(SKILL_NAME)
    restored2 = skill_file.read_text(encoding="utf-8")
    record(
        "rollback#2-boundary", rb2.get("ok") is True and restored2 == content_v1,
        restored_version=rb2.get("restored_version"),
        content_unchanged=restored2 == restored,
        note="重复 rollback 不继续回退到更早快照：机制是『恢复最近快照』而非『撤销栈』",
    )

    # 步骤 5：discard 路径 → skill 文件零改动
    before_discard = skill_file.read_text(encoding="utf-8")
    c3 = ledger.submit(
        skill_name=SKILL_NAME,
        lesson="一次性口误纠正，不值得沉淀。",
        rationale="用户撤回",
    )
    d3 = ledger.decide(c3["candidate_id"], "discard")
    record(
        "discard", d3["status"] == "discarded" and skill_file.read_text(encoding="utf-8") == before_discard,
        candidate_id=c3["candidate_id"], skill_file_untouched=True,
    )

    # 步骤 6：审计链完整有序（append-only JSONL，事件类型与时间单调性）
    events = [
        json.loads(line) for line in ledger.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected_sequence = [
        "candidate_submitted", "candidate_decided",
        "candidate_submitted", "candidate_decided",
        "skill_rollback", "skill_rollback",
        "candidate_submitted", "candidate_decided",
    ]
    actual_sequence = [e.get("event") for e in events]
    times = [str(e.get("time") or "") for e in events]
    decisions = {e.get("candidate_id"): e.get("status") for e in events if e.get("event") == "candidate_decided"}
    record(
        "audit-chain",
        actual_sequence == expected_sequence
        and times == sorted(times)
        and decisions == {c1["candidate_id"]: "merged", c2["candidate_id"]: "merged", c3["candidate_id"]: "discarded"},
        event_sequence=actual_sequence,
        times_monotonic=times == sorted(times),
        decision_status=decisions,
        ledger_file=str(ledger.path.relative_to(work)),
    )

    # 步骤 7：零污染校验——agent-home 整树指纹不变
    bear_digest_after = _tree_digest(agent_home_bear)
    record(
        "no-pollution",
        bear_digest_after == bear_digest_before,
        agent_home_tree_digest_unchanged=bear_digest_after == bear_digest_before,
        note="全流程在临时副本执行，演示结束临时目录整体删除",
    )
    return steps, failures


def main() -> int:
    output = PROJECT_ROOT / "docs" / "evidence" / "skill_evolution_demo.json"
    original_cwd = Path.cwd()
    failures: list[str] = []
    steps: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="cow-evolution-demo-") as sandbox:
        try:
            steps, failures = run_demo(Path(sandbox))
        finally:
            os.chdir(original_cwd)
            skills_mod.reset_skill_cache()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "skill": SKILL_NAME,
        "mechanism": "app/feedback.py::FeedbackLedger + bear/agents/skill_evolution.py "
                     "（evolve 前快照 → rollback 恢复最近快照 → append-only JSONL 审计）",
        "sandbox": "agent-home/.bear/skills 临时副本，运行结束即删除，agent-home 零改动",
        "all_steps_ok": not failures,
        "steps": steps,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for step in steps:
        mark = "OK " if step["ok"] else "FAIL"
        print(f"[{mark}] {step['step']}")
    print(f"evidence written to {output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
