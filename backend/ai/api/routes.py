"""
AI microservice — API routes.

Thin controllers only. All business logic lives in services/.
Three endpoints:
  POST /classify            — classify a financial transaction
  POST /statements/cleanup  — clean and sign-correct PDF-parsed candidates
  GET  /health              — liveness probe
"""

from fastapi import APIRouter

from ai.schemas.classification_schema import ClassifyRequest, ClassifyResponse
from ai.schemas.statement_cleanup_schema import (
    StatementCleanupRequest,
    StatementCleanupResponse,
    ParsedTransactionCandidate,
)
from ai.services.api_service import classify_transaction
from ai.services.statement_cleanup_service import clean_statement_transactions

router = APIRouter()


@router.post("/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest) -> ClassifyResponse:
    result = classify_transaction(
        merchant=request.merchant,
        amount=request.amount,
        notes=request.notes,
    )
    return ClassifyResponse(**result)


@router.post("/statements/cleanup", response_model=StatementCleanupResponse)
def cleanup_statement(request: StatementCleanupRequest) -> StatementCleanupResponse:
    candidates = [t.model_dump() for t in request.transactions]
    cleaned = clean_statement_transactions(candidates, request.statement_type or "unknown")
    return StatementCleanupResponse(
        transactions=[ParsedTransactionCandidate(**t) for t in cleaned]
    )


@router.get("/health")
def health() -> dict:
    from ai.core.config import settings
    return {
        "status": "ok",
        "service": settings.ai_service_name,
        "env": settings.ai_env,
        "model": settings.groq_model,
    }
