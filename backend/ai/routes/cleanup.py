from fastapi import APIRouter
from ai.schemas.statement_cleanup_schema import (
    ParsedTransactionCandidate,
    StatementCleanupRequest,
    StatementCleanupResponse,
)
from ai.services.statement_cleanup_service import clean_statement_transactions

router = APIRouter()


@router.post("/statements/cleanup", response_model=StatementCleanupResponse)
def cleanup_statement(request: StatementCleanupRequest) -> StatementCleanupResponse:
    candidates = [t.model_dump() for t in request.transactions]
    cleaned = clean_statement_transactions(candidates)
    return StatementCleanupResponse(
        transactions=[ParsedTransactionCandidate(**t) for t in cleaned]
    )
