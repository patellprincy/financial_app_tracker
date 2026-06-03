import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter
from app.routes.auth import router as auth_router
from app.routes.insights import router as insights_router
from app.routes.statements import router as statements_router
from app.routes.transactions import router as transaction_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FinSight AI", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

app.include_router(auth_router)
app.include_router(transaction_router)
app.include_router(statements_router)
app.include_router(insights_router)


@app.on_event("startup")
async def startup_event():
    from app.database import check_db_connection, check_users_table
    logger.info("=== FinSight AI startup diagnostics ===")

    if check_db_connection():
        logger.info("STARTUP: Database connection — OK")
    else:
        logger.error("STARTUP: Database connection — FAILED. Check DATABASE_URL in .env")

    if check_users_table():
        logger.info("STARTUP: 'users' table — OK")
    else:
        logger.error(
            "STARTUP: 'users' table — NOT FOUND. "
            "Run sql/create_tables.sql in the Supabase SQL Editor before using auth endpoints."
        )

    from app.config import settings
    logger.info(
        "STARTUP: AI cleanup — enabled=%s AI_BACKEND_URL=%s timeout=%ds",
        settings.AI_CLEANUP_ENABLED,
        settings.AI_BACKEND_URL,
        settings.AI_CLEANUP_TIMEOUT_SECONDS,
    )

    logger.info("=== startup diagnostics complete ===")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s\n%s", request.method, request.url, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
    )


@app.get("/")
async def root():
    return {"message": "FinSight AI backend is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/health/db")
async def health_db():
    from app.database import check_db_connection
    if check_db_connection():
        return {"status": "healthy", "database": "connected"}
    return JSONResponse(
        status_code=503,
        content={"status": "unhealthy", "database": "unreachable"},
    )
