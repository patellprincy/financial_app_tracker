from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from app.schemas.transaction import TransactionResponse


class ParsedTransactionPreview(BaseModel):
    transaction_date: str
    description: str
    amount: float
    raw_text: str


class StatementUploadResponse(BaseModel):
    upload_id: UUID
    file_name: str
    status: str
    total_transactions: int
    transactions: list[ParsedTransactionPreview]
    parse_error: Optional[str]

    model_config = {"from_attributes": True}


# ── Phase 3A: preview import ────────────────────────────────────────────────

class ImportTransactionItem(BaseModel):
    """A single user-approved row sent back from the Android preview screen."""
    transaction_date: str
    description: str
    amount: float
    raw_text: Optional[str] = ""


class StatementImportRequest(BaseModel):
    transactions: list[ImportTransactionItem]


class StatementImportResponse(BaseModel):
    upload_id: UUID
    status: str
    imported_transactions: int
    failed_transactions: int
    transactions: list[TransactionResponse]

    model_config = {"from_attributes": True}
