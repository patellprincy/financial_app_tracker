from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, field_validator


class ManualTransactionRequest(BaseModel):
    merchant: str
    amount: float
    notes: str
    transaction_type: Optional[Literal["expense", "income"]] = None

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalise_transaction_type(cls, v):
        if isinstance(v, str):
            v = v.strip().lower()
            if v not in ("expense", "income"):
                raise ValueError("transaction_type must be 'expense' or 'income'")
        return v


class TransactionResponse(BaseModel):
    id: int
    user_id: str
    merchant: str
    amount: float
    notes: str
    transaction_type: str
    category_id: int
    category_name: str
    confidence: float
    reason: str
    created_at: datetime
    is_anomaly: bool
    anomaly_status: Optional[str] = None    # "normal" | "confirmed_anomaly" | "insufficient_history"
    anomaly_score: Optional[float] = None
    anomaly_reason: Optional[str] = None
    anomaly_checked_at: Optional[datetime] = None
    ml_model_version: Optional[str] = None

    model_config = {"from_attributes": True}


class CategoryBreakdownResponse(BaseModel):
    category_id: int
    category_name: str
    amount: float
    percentage: float


class DashboardResponse(BaseModel):
    total_expense: float
    total_income: float
    category_breakdown: list[CategoryBreakdownResponse]
    recent_transactions: list[TransactionResponse]
