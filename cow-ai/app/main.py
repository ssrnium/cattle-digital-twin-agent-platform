from fastapi import FastAPI

from app.core.config import settings
from app.routers import infer

app = FastAPI(title=settings.APP_NAME, version="0.1.0")
app.include_router(infer.router)


@app.get("/health")
def health() -> dict:
    return {"status": "UP", "service": settings.APP_NAME}
