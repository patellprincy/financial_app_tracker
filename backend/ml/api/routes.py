"""FastAPI route: POST /anomaly/detect"""
import logging

from fastapi import APIRouter, HTTPException

from schemas import AnomalyRequest, AnomalyResponse
from services.prediction_service import predict_anomaly

router = APIRouter(prefix="/anomaly", tags=["anomaly"])
logger = logging.getLogger(__name__)


@router.post("/detect", response_model=AnomalyResponse)
def detect_anomaly(payload: AnomalyRequest) -> AnomalyResponse:
    logger.info(
        "POST /anomaly/detect — txn_id=%s  user=%s  amount=%.2f  category=%s",
        payload.transaction.transaction_id,
        payload.transaction.user_id,
        payload.transaction.amount,
        payload.transaction.category,
    )
    try:
        result = predict_anomaly(
            transaction=payload.transaction.model_dump(),
            history=[h.model_dump() for h in payload.history],
        )
        return AnomalyResponse(**result)
    except FileNotFoundError as exc:
        logger.error("Model not ready: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Prediction failed for txn_id=%s", payload.transaction.transaction_id)
        raise HTTPException(status_code=500, detail=f"Prediction error: {exc}")
