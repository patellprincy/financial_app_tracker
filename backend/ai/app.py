"""
FinSight AI Microservice — entry point.
Port: 8001

Run from backend/:
    uvicorn ai.app:app --reload --host 0.0.0.0 --port 8001

Run from inside backend/ai/:
    uvicorn app:app --reload --host 0.0.0.0 --port 8001

Communication rule:
    Android  →  Main Backend (8000)  →  AI Service (8001)
    AI results flow back to the main backend only — never directly to Android.
"""

import logging
import os
import sys
import traceback

# Make the service importable both as `ai.app` (from backend/) and as `app`
# (from inside backend/ai/), mirroring the ML service's sys.path approach.
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai.api.routes import router as ai_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FinSight AI Microservice",
    version="1.0.0",
    description=(
        "AI classification and statement cleanup microservice. "
        "Internal service — called by the main backend only."
    ),
)

# Only accept calls from the main backend, not from external clients.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(ai_router)


@app.on_event("startup")
async def startup_event() -> None:
    from ai.core.config import settings
    logger.info("=== FinSight AI Microservice starting on port 8001 ===")
    logger.info("STARTUP: model=%s  env=%s", settings.groq_model, settings.ai_env)
    key_set = bool(settings.groq_api_key)
    key_preview = (settings.groq_api_key[:8] + "...") if key_set else "NOT SET"
    logger.info("STARTUP: GROQ_API_KEY=%s", key_preview)
    if not key_set:
        logger.error("STARTUP: GROQ_API_KEY is missing — all AI calls will fail")
    logger.info("=== Ready — POST /classify  POST /statements/cleanup  GET /health ===")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s\n%s",
        request.method, request.url, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"},
    )


@app.get("/")
def root() -> dict:
    return {
        "service": "FinSight AI Microservice",
        "status": "running",
        "port": 8001,
        "endpoints": ["/classify", "/statements/cleanup", "/health"],
    }
