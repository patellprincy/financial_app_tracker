"""FastAPI routes: POST /anomaly/detect  and  POST /anomaly/detect-batch"""
import logging
import time

from fastapi import APIRouter, HTTPException

from schemas import (
    AnomalyBatchRequest,
    AnomalyBatchResponse,
    AnomalyRequest,
    AnomalyResponse,
)
from services.prediction_service import predict_anomaly, predict_anomaly_batch

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


@router.post("/detect-batch", response_model=AnomalyBatchResponse)
def detect_anomaly_batch(payload: AnomalyBatchRequest) -> AnomalyBatchResponse:
    """
    Run anomaly detection for multiple transactions in one request.

    The history list is shared — pass the user's existing transaction history
    (without the current batch members) so behavioral features are computed
    correctly for each transaction.

    Results are returned in the same order as the input transactions list.
    Individual prediction failures are returned as safe fallback results
    so one bad transaction cannot abort the whole batch.
    """
    n = len(payload.transactions)
    h = len(payload.history)

    logger.info(
        "POST /anomaly/detect-batch — transactions=%d  history=%d  user=%s",
        n,
        h,
        payload.transactions[0].user_id if payload.transactions else "none",
    )

    if n == 0:
        return AnomalyBatchResponse(
            results=[], total=0, anomaly_count=0, model_version=None
        )

    try:
        t0 = time.perf_counter()
        history_dicts = [h.model_dump() for h in payload.history]
        txn_dicts = [t.model_dump() for t in payload.transactions]

        result_dicts = predict_anomaly_batch(
            transactions=txn_dicts,
            history=history_dicts,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        results = [AnomalyResponse(**r) for r in result_dicts]
        anomaly_count = sum(1 for r in results if r.is_anomaly)
        model_version = results[0].model_version if results else None

        logger.info(
            "POST /anomaly/detect-batch — done  processed=%d  anomalies=%d  elapsed=%.1fms",
            len(results), anomaly_count, elapsed_ms,
        )

        return AnomalyBatchResponse(
            results=results,
            total=len(results),
            anomaly_count=anomaly_count,
            model_version=model_version,
        )

    except FileNotFoundError as exc:
        logger.error("Model not ready: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Batch prediction failed")
        raise HTTPException(status_code=500, detail=f"Batch prediction error: {exc}")
