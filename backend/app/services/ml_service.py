import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10.0

_FALLBACK: dict[str, Any] = {
    "is_anomaly": False,
    "anomaly_status": None,
    "anomaly_score": None,
    "anomaly_reason": "ML anomaly check unavailable",
    "ml_model_version": None,
}


def _build_transaction_input(t) -> dict:
    date_str = (
        t.created_at.isoformat()
        if t.created_at
        else datetime.now(timezone.utc).isoformat()
    )
    return {
        "transaction_id": str(t.id),
        "user_id": str(t.user_id),
        "transaction_date": date_str,
        "merchant": t.merchant,
        "amount": t.amount,
        "category": t.category_name,
        "transaction_type": t.transaction_type,
        "notes": t.notes or None,
    }


async def check_transaction_anomaly(
    transaction,
    history: list,
) -> dict[str, Any]:
    """
    Posts the transaction + user history to the ML anomaly detection service.

    Never raises — returns _FALLBACK on any failure so transaction creation
    always succeeds even when the ML service is down.
    """
    url = f"{settings.ML_SERVICE_URL.rstrip('/')}/anomaly/detect"
    payload = {
        "transaction": _build_transaction_input(transaction),
        "history": [_build_transaction_input(t) for t in history],
    }

    logger.info(
        "[MLClient] → POST %s | transaction_id=%d merchant=%r history_len=%d",
        url, transaction.id, transaction.merchant, len(history),
    )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        result: dict[str, Any] = {
            "is_anomaly": bool(data.get("is_anomaly", False)),
            "anomaly_status": data.get("anomaly_status"),
            "anomaly_score": float(data["confidence"]) if data.get("confidence") is not None else None,
            "anomaly_reason": data.get("reason"),
            "ml_model_version": data.get("model_version"),
        }

        logger.info(
            "[MLClient] ← HTTP %d | is_anomaly=%s score=%s reason=%r",
            response.status_code,
            result["is_anomaly"],
            result["anomaly_score"],
            result["anomaly_reason"],
        )
        return result

    except httpx.TimeoutException:
        logger.warning("[MLClient] Timeout after %.1fs — using fallback", _TIMEOUT_SECONDS)

    except httpx.ConnectError as exc:
        logger.error("[MLClient] Cannot connect to ML service at %s: %s", url, exc)

    except httpx.HTTPStatusError as exc:
        logger.error(
            "[MLClient] HTTP %d from ML service: %s",
            exc.response.status_code, exc,
        )

    except Exception as exc:
        logger.error("[MLClient] Unexpected error: %s", exc)

    return _FALLBACK.copy()
