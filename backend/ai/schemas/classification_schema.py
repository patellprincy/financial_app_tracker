from pydantic import BaseModel
from typing import Literal, Optional


class ClassifyRequest(BaseModel):
    merchant: str
    amount: float
    notes: Optional[str] = None


class ClassifyResponse(BaseModel):
    transaction_type: Literal["income", "expense"]
    category_name: str
    normalized_category: str
    confidence: float
    reason: str
