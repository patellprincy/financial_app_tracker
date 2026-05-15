import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ai.routes.classify import router as classify_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FinSight AI Classification Service",
    version="1.0.0",
    description="Standalone microservice: classifies financial transactions via Groq.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(classify_router)


@app.on_event("startup")
async def startup_event():
    from ai.core.config import settings
    logger.info("=== FinSight AI Classification Service starting ===")
    logger.info("STARTUP: model = %s", settings.groq_model)
    key_preview = (settings.groq_api_key[:8] + "...") if settings.groq_api_key else "NOT SET"
    logger.info("STARTUP: GROQ_API_KEY = %s", key_preview)
    if not settings.groq_api_key:
        logger.error("STARTUP: GROQ_API_KEY is missing — all classifications will fail")
    logger.info("=== AI Classification Service ready on /classify ===")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s\n%s",
        request.method, request.url, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"},
    )


@app.get("/")
async def root():
    return {"service": "FinSight AI Classification", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-classification"}
