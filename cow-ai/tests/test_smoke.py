from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "UP"


def test_infer_mounting_mock():
    resp = client.post("/api/v1/infer/mounting",
                       json={"cow_id": "COW-0001", "device_id": "camera-01"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mocked"] is True
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["detections"][0]["label"] == "mounting"
    assert body["model_version"]


def test_infer_lameness_mock():
    resp = client.post("/api/v1/infer/lameness",
                       json={"cow_id": "COW-0002", "device_id": "camera-02"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["detections"][0]["label"] == "lameness"


def test_mounting_deterministic_mock():
    payload = {"cow_id": "COW-0003", "device_id": "camera-01"}
    a = client.post("/api/v1/infer/mounting", json=payload).json()
    b = client.post("/api/v1/infer/mounting", json=payload).json()
    assert a["confidence"] == b["confidence"]
