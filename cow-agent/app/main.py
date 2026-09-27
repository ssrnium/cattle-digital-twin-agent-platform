"""cow-agent FastAPI 入口（端口 8003）。

启动时：应用母版 patch → chdir 到 AGENT_HOME（BearCode 的 skills/会话/记忆
全部以 cwd 或 HOME 为基准，Docker 中另设 ENV HOME=/app/agent-home 固定 home 侧）。
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import agent_home_path, settings
from app.patch import apply_patches

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("cow-agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_patches()
    previous_cwd = Path.cwd()
    agent_home = agent_home_path()
    agent_home.mkdir(parents=True, exist_ok=True)
    os.chdir(agent_home)  # skills 发现、会话持久化均以 cwd 为基准
    logger.info("cow-agent started, AGENT_HOME=%s, model=%s", agent_home, settings.LLM_MODEL)
    try:
        yield
    finally:
        from app.agent_manager import agent_manager

        await agent_manager.shutdown()
        os.chdir(previous_cwd)


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ConfirmRequest(BaseModel):
    session_id: str
    approved: bool


class FeedbackRequest(BaseModel):
    skill_name: str
    lesson: str
    rationale: str = ""
    description: str = ""
    instructions: str = ""
    when_to_use: str = ""
    target: str = "project"
    evidence: str = ""


class FeedbackDecisionRequest(BaseModel):
    action: str


@app.post("/api/v1/agent/chat")
async def chat(req: ChatRequest) -> dict:
    from app.agent_manager import LLMNotConfigured, agent_manager

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message 不能为空")
    try:
        return await agent_manager.chat(req.session_id, req.message)
    except LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=502, detail=f"智能体调用失败: {e}")


@app.post("/api/v1/agent/confirm")
async def confirm(req: ConfirmRequest) -> dict:
    from app.agent_manager import agent_manager

    ok = agent_manager.confirm(req.session_id, req.approved)
    if not ok:
        raise HTTPException(status_code=404, detail="该会话没有待确认的操作（可能已超时自动拒绝）")
    return {"ok": True, "approved": req.approved}


@app.get("/api/v1/agent/sessions")
async def sessions() -> dict:
    from app.agent_manager import agent_manager

    return {"sessions": agent_manager.list_sessions()}


@app.post("/api/v1/agent/feedback")
async def submit_feedback(req: FeedbackRequest) -> dict:
    from app.feedback import FeedbackError, FeedbackLedger

    try:
        candidate = FeedbackLedger().submit(**req.model_dump())
    except FeedbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"candidate": candidate}


@app.post("/api/v1/agent/feedback/{candidate_id}/decision")
async def decide_feedback(candidate_id: str, req: FeedbackDecisionRequest) -> dict:
    from app.feedback import FeedbackError, FeedbackLedger

    try:
        result = FeedbackLedger().decide(candidate_id, req.action)
    except FeedbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"result": result}


@app.get("/api/v1/agent/feedback")
async def list_feedback() -> dict:
    from app.feedback import FeedbackLedger

    return {"candidates": FeedbackLedger().list()}


@app.post("/api/v1/agent/feedback/{skill_name}/rollback")
async def rollback_feedback(skill_name: str) -> dict:
    from app.feedback import FeedbackError, FeedbackLedger

    try:
        result = FeedbackLedger().rollback(skill_name)
    except FeedbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"result": result}


@app.get("/health")
def health() -> dict:
    return {
        "status": "UP",
        "service": settings.APP_NAME,
        "llm_configured": bool(settings.LLM_API_KEY),
    }
