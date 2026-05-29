from uuid import UUID
from typing import Optional
from pydantic import BaseModel


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
