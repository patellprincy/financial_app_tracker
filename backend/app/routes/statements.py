import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.statement_upload import StatementUpload
from app.schemas.statement import ParsedTransactionPreview, StatementUploadResponse
from app.services.statement_parser_service import debug_parse, parse_statement
from app.services.statement_cleanup_client import ai_cleanup

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/statements", tags=["statements"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/debug", summary="Diagnose PDF parsing (dev only)")
async def debug_statement(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    contents = await file.read()
    return debug_parse(contents)


@router.post("/upload", response_model=StatementUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_statement(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted.",
        )

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB limit.",
        )

    # ── Save initial upload record ─────────────────────────────────────────
    record = StatementUpload(
        user_id=current_user.id,
        file_name=file.filename,
        status="uploaded",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # ── Step 1: PDF parsing ────────────────────────────────────────────────
    result = parse_statement(contents)
    candidates = result.transactions

    logger.info(
        "statement_upload: parser candidates count=%d strategy=%s upload_id=%s",
        len(candidates), result.parse_strategy, record.id,
    )
    logger.info(
        "statement_upload: AI cleanup enabled=%s AI_BACKEND_URL=%s",
        settings.AI_CLEANUP_ENABLED, settings.AI_BACKEND_URL,
    )

    # ── Step 2: Cleanup (rule pre-clean + optional AI) ────────────────────
    # ai_cleanup() always runs; it does rule-based pre-clean first,
    # then calls the AI microservice only when AI_CLEANUP_ENABLED=true.
    final_transactions = await ai_cleanup(candidates)

    logger.info(
        "statement_upload: final preview count=%d upload_id=%s",
        len(final_transactions), record.id,
    )

    # ── Step 3: Persist status ─────────────────────────────────────────────
    record.status = "parsed" if final_transactions else "parse_failed"
    record.total_transactions = len(final_transactions)
    db.commit()
    db.refresh(record)

    return StatementUploadResponse(
        upload_id=record.id,
        file_name=record.file_name,
        status=record.status,
        total_transactions=len(final_transactions),
        transactions=[
            ParsedTransactionPreview(
                transaction_date=t.transaction_date,
                description=t.description,
                amount=t.amount,
                raw_text=t.raw_text,
            )
            for t in final_transactions
        ],
        parse_error=result.error,
    )
