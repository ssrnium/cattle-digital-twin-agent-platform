import app.routers.infer as infer
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class FakeTensor:
    def __init__(self, vals):
        self.vals = vals

    def tolist(self):
        return self.vals


class FakeBox:
    def __init__(self, cls_id, conf, xyxy=(10.0, 20.0, 30.0, 40.0)):
        self.cls = [cls_id]
        self.conf = [conf]
        self.xyxy = [FakeTensor(list(xyxy))]


class FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


class FakeYOLO:
    """按脚本的逐帧置信度返回检出；names 模拟采购权重的 10 类命名。"""

    names = {0: "standing", 1: "walking", 9: "mounting"}

    def __init__(self, confs):
        self.confs = list(confs)
        self.calls = 0

    def predict(self, img, verbose=False):
        conf = self.confs[self.calls]
        self.calls += 1
        boxes = [] if conf <= 0 else [FakeBox(9, conf)]
        return [FakeResult(boxes)]


def _patch_decode(monkeypatch):
    # 测试环境无 cv2/numpy：解码函数替换为直通，FakeYOLO 不读图像内容
    monkeypatch.setattr(infer, "_decode_image", lambda b64: b64)


def test_infer_mounting_real_branch(monkeypatch):
    monkeypatch.setattr(infer, "_load_mounting_model", lambda: FakeYOLO([0.87]))
    _patch_decode(monkeypatch)
    resp = client.post("/api/v1/infer/mounting", json={
        "cow_id": "COW-0001", "device_id": "camera-01", "image_base64": "AAAA"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mocked"] is False
    assert body["confidence"] == 0.87
    assert body["detections"][0]["label"] == "mounting"
    assert body["detections"][0]["bbox"] == [10.0, 20.0, 30.0, 40.0]
    assert body["model_version"]


def test_infer_mounting_filters_by_class_name(monkeypatch):
    # standing(0) 置信度更高也必须被过滤，只取 mounting(9)
    class MultiBoxYOLO(FakeYOLO):
        def predict(self, img, verbose=False):
            self.calls += 1
            return [FakeResult([FakeBox(0, 0.99), FakeBox(9, 0.52)])]

    monkeypatch.setattr(infer, "_load_mounting_model", lambda: MultiBoxYOLO([]))
    _patch_decode(monkeypatch)
    body = client.post("/api/v1/infer/mounting", json={
        "cow_id": "COW-0001", "image_base64": "AAAA"}).json()
    assert body["mocked"] is False
    assert len(body["detections"]) == 1
    assert body["detections"][0]["label"] == "mounting"
    assert body["confidence"] == 0.52


def test_infer_mounting_mock_branch(monkeypatch):
    monkeypatch.setattr(infer, "_load_mounting_model", lambda: None)
    body = client.post("/api/v1/infer/mounting", json={
        "cow_id": "COW-0001", "image_base64": "AAAA"}).json()
    assert body["mocked"] is True
    assert body["detections"][0]["label"] == "mounting"


def test_clip_real_branch_sessionized(monkeypatch):
    # 10 帧：2 低 + 3 高（开窗）+ 5 低（关窗）→ 恰好 1 个窗口
    confs = [0.0, 0.0, 0.5, 0.6, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0]
    monkeypatch.setattr(infer, "_load_mounting_model", lambda: FakeYOLO(confs))
    _patch_decode(monkeypatch)
    resp = client.post("/api/v1/infer/mounting/clip", json={
        "cow_id": "COW-0001", "device_id": "camera-01", "fps": 5,
        "frames": ["AAAA"] * 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mocked"] is False
    assert len(body["windows"]) == 1
    w = body["windows"][0]
    assert w["start_frame"] == 2
    assert w["end_frame"] == 4
    assert w["peak_confidence"] == 0.7
    assert w["peak_frame"] == 4


def test_clip_mock_branch_same_sessionize(monkeypatch):
    # 无权重走 mock：伪置信度跑同一 sessionize，结果可复现
    monkeypatch.setattr(infer, "_load_mounting_model", lambda: None)
    confs = iter([0.0, 0.0, 0.5, 0.6, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0])
    monkeypatch.setattr(infer, "_pseudo_confidence", lambda seed: next(confs))
    resp = client.post("/api/v1/infer/mounting/clip", json={
        "cow_id": "COW-0001", "fps": 5, "frames": ["AAAA"] * 10})
    body = resp.json()
    assert body["mocked"] is True
    assert len(body["windows"]) == 1
    assert (body["windows"][0]["start_frame"], body["windows"][0]["end_frame"]) == (2, 4)


def test_clip_frame_count_validation():
    resp = client.post("/api/v1/infer/mounting/clip", json={
        "cow_id": "COW-0001", "fps": 5, "frames": []})
    assert resp.status_code == 422
    resp = client.post("/api/v1/infer/mounting/clip", json={
        "cow_id": "COW-0001", "fps": 5, "frames": ["AAAA"] * 301})
    assert resp.status_code == 422
