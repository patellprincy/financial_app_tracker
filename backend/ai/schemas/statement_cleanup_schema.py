from typing import Optional
from pydantic import BaseModel


class ParsedTransactionCandidate(BaseModel):
    transaction_date: str
    description: str
    amount: float
    raw_text: str
    # Returned by the AI to aid sign validation; not part of the public API contract.
    transaction_type: Optional[str] = None


class StatementCleanupRequest(BaseModel):
    transactions: list[ParsedTransactionCandidate]


class StatementCleanupResponse(BaseModel):
    transactions: list[ParsedTransactionCandidate]
