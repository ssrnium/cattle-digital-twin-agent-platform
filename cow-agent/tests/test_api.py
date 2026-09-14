"""FastAPI 接口冒烟：/health、无 LLM key 时 chat 友好报错、confirm 无 pending 时 404。"""
import pytest
from fastapi.testclient import TestClient

from app.config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")  # 与 .env 是否真实存在解耦
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "UP"
    assert body["llm_configured"] is False


def test_chat_without_llm_key_friendly_error(client):
    resp = client.post("/api/v1/agent/chat", json={"message": "你好"})
    assert resp.status_code == 503
    assert "LLM_API_KEY" in resp.json()["detail"]


def test_chat_empty_message(client):
    resp = client.post("/api/v1/agent/chat", json={"message": "  "})
    assert resp.status_code == 400


def test_confirm_without_pending_404(client):
    resp = client.post("/api/v1/agent/confirm", json={"session_id": "nope", "approved": True})
    assert resp.status_code == 404


def test_sessions_list(client):
    resp = client.get("/api/v1/agent/sessions")
    assert resp.status_code == 200
    assert isinstance(resp.json()["sessions"], list)
