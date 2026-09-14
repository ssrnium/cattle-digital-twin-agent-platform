from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """cow-agent 服务配置，全部可用环境变量覆盖（LLM key 只走环境变量 / .env，不进代码）。"""

    APP_NAME: str = "cow-agent"
    PORT: int = 8003

    # LLM：OpenAI 兼容协议（DeepSeek / Kimi 均可），默认 DeepSeek V4.1 Flash
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-flash"
    LLM_API_KEY: str = ""
    AGENT_MAX_TURNS: int = 12

    # 领域工具回调的业务后端
    COW_ADMIN_BASE_URL: str = "http://localhost:8081"
    AGENT_USER: str = "svc-agent"
    AGENT_PASSWORD: str = "SvcAgent@123"

    # BearCode 运行目录：skills / 会话 / 记忆全部落在其下（启动时 chdir 到此）
    AGENT_HOME: str = "./agent-home"
    # 写操作前端确认超时（秒），超时自动拒绝
    CONFIRM_TIMEOUT_SECONDS: int = 120

    class Config:
        env_file = ".env"


settings = Settings()
