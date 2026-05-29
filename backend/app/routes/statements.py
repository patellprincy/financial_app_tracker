from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.statement_upload import StatementUpload
from app.schemas.statement import ParsedTransactionPreview, StatementUploadResponse
from app.services.statement_parser_service import debug_parse, parse_statement

router = APIRouter(prefix="/statements", tags=["statements"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/debug", summary="Diagnose PDF parsing (dev only)")
async def debug_statement(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Returns raw pdfplumber diagnostics: extracted text, detected dates/amounts
    per line, and table contents. Use this to understand why a PDF fails to parse.
    """
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

    record = StatementUpload(
        user_id=current_user.id,
        file_name=file.filename,
        status="uploaded",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    result = parse_statement(contents)

    record.status = "parsed" if result.transactions else "parse_failed"
    record.total_transactions = len(result.transactions)
    db.commit()
    db.refresh(record)

    return StatementUploadResponse(
        upload_id=record.id,
        file_name=record.file_name,
        status=record.status,
        total_transactions=len(result.transactions),
        transactions=[
            ParsedTransactionPreview(
                transaction_date=t.transaction_date,
                description=t.description,
                amount=t.amount,
                raw_text=t.raw_text,
            )
            for t in result.transactions
        ],
        parse_error=result.error,
    )
