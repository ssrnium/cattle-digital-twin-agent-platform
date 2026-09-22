import base64
import hashlib
import os
from dataclasses import asdict
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.behavior_session import FrameDetection, sessionize

router = APIRouter(prefix="/api/v1/infer", tags=["infer"])

MOUNTING_LABEL = "mounting"


class InferRequest(BaseModel):
    """推理请求：图片 base64 或视频帧元信息。"""

    cow_id: str = Field(default="COW-0001")
    device_id: str = Field(default="camera-01")
    image_base64: Optional[str] = None
    frame_meta: Optional[dict] = None


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: List[float]


class InferResponse(BaseModel):
    detections: List[Detection]
    confidence: float
    model_version: str
    mocked: bool


class ClipInferRequest(BaseModel):
    """连续帧推理请求：base64 帧列表（<=300 帧）。"""

    cow_id: str = Field(default="COW-0001")
    device_id: str = Field(default="camera-01")
    fps: float = Field(default=5.0, gt=0)
    frames: List[str] = Field(..., min_length=1, max_length=300)


class WindowOut(BaseModel):
    start_frame: int
    end_frame: int
    peak_confidence: float
    peak_frame: int
    best_bbox: Optional[List[float]] = None
    avg_confidence: float


class ClipInferResponse(BaseModel):
    windows: List[WindowOut]
    model_version: str
    mocked: bool


def _pseudo_confidence(seed: str) -> float:
    """按输入生成确定性的伪置信度，mock 模式下保证演示可复现。"""
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return round(0.6 + (int(digest[:4], 16) % 4000) / 10000.0, 4)  # 0.60 ~ 1.00


_MOUNTING_MODEL = None
_MOUNTING_MODEL_LOADED = False


def _load_mounting_model():
    """进程级缓存加载 YOLO 权重；权重缺失或 ultralytics 未安装时返回 None（回落 mock）。

    ultralytics/torch 为重量级依赖，仅真实推理主机安装（见 requirements-vision.txt），
    因此这里懒导入，缺依赖不影响 cow-ai 其余功能与测试。
    """
    global _MOUNTING_MODEL, _MOUNTING_MODEL_LOADED
    if _MOUNTING_MODEL_LOADED:
        return _MOUNTING_MODEL
    _MOUNTING_MODEL_LOADED = True
    path = settings.MOUNTING_WEIGHTS_PATH
    if not path or not os.path.exists(path):
        return None
    try:
        from ultralytics import YOLO
    except ImportError:
        return None
    _MOUNTING_MODEL = YOLO(path)
    return _MOUNTING_MODEL


def _decode_image(image_base64: str):
    """base64 -> BGR ndarray。cv2/numpy 懒导入，仅真实推理路径需要。"""
    import cv2
    import numpy as np

    raw = base64.b64decode(image_base64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("image_base64 无法解码为图像")
    return img


def _predict_mounting(model, image_base64: str) -> List[Detection]:
    """真实推理：按 model.names 名字过滤 mounting 类（不写死 class index）。"""
    img = _decode_image(image_base64)
    results = model.predict(img, verbose=False)
    names = getattr(model, "names", None) or {}
    mounting_ids = {idx for idx, name in names.items() if name == MOUNTING_LABEL}
    detections: List[Detection] = []
    for result in results:
        for box in result.boxes:
            if int(box.cls[0]) not in mounting_ids:
                continue
            detections.append(Detection(
                label=MOUNTING_LABEL,
                confidence=round(float(box.conf[0]), 4),
                bbox=[round(float(v), 2) for v in box.xyxy[0].tolist()],
            ))
    detections.sort(key=lambda d: d.confidence, reverse=True)
    return detections


_MOCK_BBOX = [120.0, 60.0, 340.0, 260.0]


@router.post("/mounting", response_model=InferResponse)
def infer_mounting(req: InferRequest) -> InferResponse:
    model = _load_mounting_model()
    if model is not None and req.image_base64:
        detections = _predict_mounting(model, req.image_base64)
        conf = detections[0].confidence if detections else 0.0
        return InferResponse(
            detections=detections,
            confidence=conf,
            model_version=settings.MOUNTING_MODEL_VERSION,
            mocked=False,
        )
    conf = _pseudo_confidence("mounting:" + req.cow_id + (req.image_base64 or "")[:64])
    return InferResponse(
        detections=[Detection(label=MOUNTING_LABEL, confidence=conf, bbox=_MOCK_BBOX)],
        confidence=conf,
        model_version=settings.MOUNTING_MODEL_VERSION,
        mocked=True,
    )


@router.post("/mounting/clip", response_model=ClipInferResponse)
def infer_mounting_clip(req: ClipInferRequest) -> ClipInferResponse:
    """连续帧爬跨识别：逐帧推理 + 会话化，一个行为窗口 = 一个事件。"""
    model = _load_mounting_model()
    mocked = model is None
    frame_dets: List[FrameDetection] = []
    for idx, image_b64 in enumerate(req.frames):
        if not mocked:
            dets = _predict_mounting(model, image_b64)
            best = dets[0] if dets else None
            frame_dets.append(FrameDetection(
                frame_index=idx,
                confidence=best.confidence if best else 0.0,
                bbox=best.bbox if best else None,
            ))
        else:
            conf = _pseudo_confidence(
                "mounting-clip:" + req.cow_id + ":" + str(idx) + ":" + image_b64[:64])
            frame_dets.append(FrameDetection(
                frame_index=idx, confidence=conf, bbox=list(_MOCK_BBOX)))
    windows = sessionize(frame_dets)
    return ClipInferResponse(
        windows=[WindowOut(**asdict(w)) for w in windows],
        model_version=settings.MOUNTING_MODEL_VERSION,
        mocked=mocked,
    )


@router.post("/lameness", response_model=InferResponse)
def infer_lameness(req: InferRequest) -> InferResponse:
    # ================================================================
    # 第一阶段已训练权重插入点：跛行检测推理链
    #   YOLOv11（牛体检测）→ RTMPose（关键点）→ 步态特征 → XGBoost（跛行分级）
    # if os.path.isdir(settings.LAMENESS_WEIGHTS_PATH):
    #     ...按推理链加载并返回分级结果
    # ================================================================
    if os.path.exists(settings.LAMENESS_WEIGHTS_PATH):
        # TODO: 接入真实跛行推理链（见上方插入点注释）
        pass
    conf = _pseudo_confidence("lameness:" + req.cow_id + (req.image_base64 or "")[:64])
    return InferResponse(
        detections=[Detection(label="lameness", confidence=conf,
                              bbox=[100.0, 80.0, 360.0, 280.0])],
        confidence=conf,
        model_version=settings.LAMENESS_MODEL_VERSION,
        mocked=True,
    )
