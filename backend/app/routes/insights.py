import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.transaction import Transaction
from app.schemas.insight import InsightItemResponse, InsightSummaryResponse, InsightsResponse

router = APIRouter(prefix="/insights", tags=["insights"])
logger = logging.getLogger(__name__)


def _severity(score: float | None) -> str:
    if score is None or score < 0.5:
        return "low"
    if score < 0.8:
        return "medium"
    return "high"


def _build_insight(t: Transaction, insight_id: int) -> InsightItemResponse:
    amount_str = f"${t.amount:,.2f}"
    return InsightItemResponse(
        id=insight_id,
        type="unusual",
        title=f"Unusual {t.category_name} transaction",
        description=(
            t.anomaly_reason
            or f"Your {amount_str} {t.merchant} transaction was flagged as unusual."
        ),
        value=amount_str,
        transaction_id=t.id,
        severity=_severity(t.anomaly_score),
        created_at=t.created_at or datetime.now(timezone.utc),
    )


@router.get("", response_model=InsightsResponse)
def get_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomalous = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.is_anomaly == True,  # noqa: E712 — SQLAlchemy requires == True
            # Exclude cold-start transactions and user-dismissed anomalies.
            # NULL anomaly_status (legacy rows) is treated as visible.
            or_(
                Transaction.anomaly_status == "confirmed_anomaly",
                Transaction.anomaly_status == None,  # noqa: E711
            ),
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )

    items = [_build_insight(t, idx + 1) for idx, t in enumerate(anomalous)]

    logger.info("[Insights] user=%s unusual=%d", current_user.id, len(items))

    return InsightsResponse(
        summary=InsightSummaryResponse(
            total_insights=len(items),
            unusual_count=len(items),
            tips_count=0,
            pattern_count=0,
        ),
        items=items,
    )
