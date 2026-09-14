import hashlib
import os
from typing import Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(prefix="/api/v1/infer", tags=["infer"])


class InferRequest(BaseModel):
    """推理请求：图片 base64 或视频帧元信息（MVP 占位契约）。"""

    cow_id: str = Field(default="COW-0001")
    device_id: str = Field(default="camera-01")
    image_base64: Optional[str] = None
    frame_meta: Optional[Dict] = None


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: List[float]


class InferResponse(BaseModel):
    detections: List[Detection]
    confidence: float
    model_version: str
    mocked: bool


def _pseudo_confidence(seed: str) -> float:
    """按输入生成确定性的伪置信度，mock 模式下保证演示可复现。"""
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return round(0.6 + (int(digest[:4], 16) % 4000) / 10000.0, 4)  # 0.60 ~ 1.00


@router.post("/mounting", response_model=InferResponse)
def infer_mounting(req: InferRequest) -> InferResponse:
    # ================================================================
    # 第一阶段已训练权重插入点：爬跨检测 YOLOv8n
    # if os.path.exists(settings.MOUNTING_WEIGHTS_PATH):
    #     model = YOLO(settings.MOUNTING_WEIGHTS_PATH)
    #     results = model.predict(decode_image(req.image_base64))
    #     ...转换为 Detection 列表后返回
    # ================================================================
    if os.path.exists(settings.MOUNTING_WEIGHTS_PATH):
        # TODO: 接入真实 YOLOv8n 爬跨权重推理（见上方插入点注释）
        pass
    conf = _pseudo_confidence("mounting:" + req.cow_id + (req.image_base64 or "")[:64])
    return InferResponse(
        detections=[Detection(label="mounting", confidence=conf,
                              bbox=[120.0, 60.0, 340.0, 260.0])],
        confidence=conf,
        model_version=settings.MOUNTING_MODEL_VERSION,
        mocked=True,
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
