"""Pydantic schemas for the ML anomaly detection API."""
from typing import Optional

from pydantic import BaseModel


class TransactionInput(BaseModel):
    transaction_id: str
    user_id: str
    transaction_date: str       # "2024-03-15 14:30:00" or "2024-03-15T14:30:00"
    merchant: str
    amount: float
    category: str
    transaction_type: str       # "expense" or "income"
    notes: Optional[str] = None


class AnomalyRequest(BaseModel):
    transaction: TransactionInput
    # Recent past transactions for the same user.
    # Used to compute behavioral features (z-score, percentile, frequency).
    # More history = better detection quality.
    history: list[TransactionInput] = []


class AnomalyResponse(BaseModel):
    transaction_id: str
    user_id: str
    is_anomaly: bool
    anomaly_status: str         # "normal" | "confirmed_anomaly" | "insufficient_history"
    confidence: float           # probability of anomaly (0.0 – 1.0)
    reason: Optional[str]       # human-readable explanation; None when normal
    model_version: Optional[str]
