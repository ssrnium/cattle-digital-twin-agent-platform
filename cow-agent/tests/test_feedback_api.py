"""Feedback API regression test for the explicit Skill evolution loop."""

from fastapi.testclient import TestClient

import app.main as main_mod


def test_feedback_api_submit_discard_and_list(tmp_path, monkeypatch):
    isolated_home = tmp_path / "agent-home"
    monkeypatch.setattr(main_mod, "agent_home_path", lambda: isolated_home)
    monkeypatch.chdir(tmp_path)

    with TestClient(main_mod.app) as client:
        submitted = client.post(
            "/api/v1/agent/feedback",
            json={
                "skill_name": "api-review",
                "lesson": "Keep the API decision auditable.",
                "rationale": "route regression",
            },
        )
        assert submitted.status_code == 200
        candidate = submitted.json()["candidate"]
        assert candidate["status"] == "pending"

        decided = client.post(
            f"/api/v1/agent/feedback/{candidate['candidate_id']}/decision",
            json={"action": "discard"},
        )
        assert decided.status_code == 200
        assert decided.json()["result"]["status"] == "discarded"

        listed = client.get("/api/v1/agent/feedback")
        assert listed.status_code == 200
        candidates = listed.json()["candidates"]
        assert len(candidates) == 1
        latest = candidates[0]
        assert latest["candidate_id"] == candidate["candidate_id"]
        assert latest["event"] == "candidate_decided"
        assert latest["status"] == "discarded"
        assert latest["action"] == "discard"
        assert latest["result"] == {"ok": True, "action": "discard", "skill": "api-review"}
