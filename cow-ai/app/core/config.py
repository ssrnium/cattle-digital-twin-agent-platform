from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """服务配置，全部可用环境变量覆盖。"""

    APP_NAME: str = "cow-ai"
    # 爬跨/行为识别权重：采购 YOLOv8m 10 类牛只行为模型（含 mounting），
    # 文件存在且 ultralytics 可用则走真实推理，否则回落 mock；权重不随仓库分发
    MOUNTING_WEIGHTS_PATH: str = "/root/autodl-tmp/models/cow-behavior/yolov8m-behavior.pt"
    # 插入点：跛行 YOLOv11 + RTMPose + XGBoost 推理链所需权重目录
    LAMENESS_WEIGHTS_PATH: str = "weights/lameness_pipeline"
    MOUNTING_MODEL_VERSION: str = "yolov8m-behavior-10cls-1.0"
    LAMENESS_MODEL_VERSION: str = "mock-lameness-0.1"

    class Config:
        env_file = ".env"


settings = Settings()
