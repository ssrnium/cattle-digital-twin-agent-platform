from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """服务配置，全部可用环境变量覆盖。"""

    APP_NAME: str = "cow-ai"
    # 第一阶段已训练权重路径；文件存在则走真推理，否则 mock
    # 插入点：爬跨 YOLOv8n 权重（如 weights/mounting_yolov8n.pt）
    MOUNTING_WEIGHTS_PATH: str = "weights/mounting_yolov8n.pt"
    # 插入点：跛行 YOLOv11 + RTMPose + XGBoost 推理链所需权重目录
    LAMENESS_WEIGHTS_PATH: str = "weights/lameness_pipeline"
    MOUNTING_MODEL_VERSION: str = "mock-mounting-0.1"
    LAMENESS_MODEL_VERSION: str = "mock-lameness-0.1"

    class Config:
        env_file = ".env"


settings = Settings()
