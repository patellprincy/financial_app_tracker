from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class InsightSummaryResponse(BaseModel):
    total_insights: int
    unusual_count: int
    tips_count: int
    pattern_count: int


class InsightItemResponse(BaseModel):
    id: int
    type: str
    title: str
    description: str
    value: str
    transaction_id: Optional[int] = None
    severity: str
    created_at: datetime


class InsightsResponse(BaseModel):
    summary: InsightSummaryResponse
    items: list[InsightItemResponse]
