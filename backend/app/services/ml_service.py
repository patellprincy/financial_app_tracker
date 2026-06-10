import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10.0
# Batch requests process many transactions in one call; allow more time for
# large imports and for Render free-tier cold-start warm-up.
_BATCH_TIMEOUT_SECONDS = 60.0

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


def _map_single_result(data: dict) -> dict[str, Any]:
    """Map the ML service response fields to the backend anomaly field names."""
    return {
        "is_anomaly": bool(data.get("is_anomaly", False)),
        "anomaly_status": data.get("anomaly_status"),
        "anomaly_score": float(data["confidence"]) if data.get("confidence") is not None else None,
        "anomaly_reason": data.get("reason"),
        "ml_model_version": data.get("model_version"),
    }


async def check_transaction_anomaly(
    transaction,
    history: list,
) -> dict[str, Any]:
    """
    Posts a single transaction + history to the ML anomaly detection service.

    Used by manual transaction creation.  Never raises — returns _FALLBACK on
    any failure so transaction creation always completes even when ML is down.
    """
    url = f"{settings.ML_SERVICE_URL.rstrip('/')}/anomaly/detect"
    payload = {
        "transaction": _build_transaction_input(transaction),
        "history": [_build_transaction_input(t) for t in history],
    }

    logger.info(
        "[MLClient] → POST %s | transaction_id=%s merchant=%r history_len=%d",
        url, transaction.id, transaction.merchant, len(history),
    )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        result = _map_single_result(data)

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
        sc = exc.response.status_code
        if sc == 429:
            logger.warning(
                "[MLClient] HTTP 429 Too Many Requests — source: Render free-tier "
                "infrastructure rate limit (no app-level limiter exists in the ML service). "
                "transaction_id=%s will use fallback. "
                "Verify statement imports are using /anomaly/detect-batch, not this endpoint.",
                transaction.id,
            )
        else:
            logger.error("[MLClient] HTTP %d from ML service (single endpoint): %s", sc, exc)

    except Exception as exc:
        logger.error("[MLClient] Unexpected error: %s", exc)

    return _FALLBACK.copy()


async def check_transactions_anomaly_batch(
    transactions: list,
    history: list,
) -> list[dict[str, Any]]:
    """
    Post all transactions in a single batch call to the ML anomaly detection service.

    Used by PDF statement import to reduce N HTTP calls to 1.
    The shared history list should contain the user's pre-existing transactions
    (the batch members themselves should be excluded from history).

    Returns a list of anomaly result dicts in the same order as transactions.
    On any failure the import is not aborted — every transaction receives a
    _FALLBACK dict instead so anomaly fields are safely populated.
    Never raises.
    """
    if not transactions:
        return []

    url = f"{settings.ML_SERVICE_URL.rstrip('/')}/anomaly/detect-batch"
    payload = {
        "transactions": [_build_transaction_input(t) for t in transactions],
        "history": [_build_transaction_input(h) for h in history],
    }

    logger.info(
        "[MLClient] → POST %s | batch transactions=%d history_len=%d",
        url, len(transactions), len(history),
    )

    try:
        async with httpx.AsyncClient(timeout=_BATCH_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        raw_results: list[dict] = data.get("results", [])

        if len(raw_results) != len(transactions):
            logger.error(
                "[MLClient] Batch result count mismatch: sent=%d got=%d — using fallbacks",
                len(transactions), len(raw_results),
            )
            return [_FALLBACK.copy() for _ in transactions]

        results = [_map_single_result(r) for r in raw_results]
        anomaly_count = sum(1 for r in results if r["is_anomaly"])

        logger.info(
            "[MLClient] ← HTTP %d | batch processed=%d anomalies=%d model=%s",
            response.status_code,
            len(results),
            anomaly_count,
            data.get("model_version"),
        )
        return results

    except httpx.TimeoutException:
        logger.warning(
            "[MLClient] Batch timeout after %.1fs for %d transactions — using fallbacks",
            _BATCH_TIMEOUT_SECONDS, len(transactions),
        )

    except httpx.ConnectError as exc:
        logger.error(
            "[MLClient] Cannot connect to ML service at %s: %s", url, exc
        )

    except httpx.HTTPStatusError as exc:
        sc = exc.response.status_code
        if sc == 429:
            logger.warning(
                "[MLClient] HTTP 429 Too Many Requests on batch endpoint — source: Render "
                "free-tier infrastructure rate limit (no app-level limiter in ML service). "
                "batch_size=%d will use fallbacks.",
                len(transactions),
            )
        else:
            logger.error("[MLClient] HTTP %d from ML batch endpoint: %s", sc, exc)

    except Exception as exc:
        logger.error("[MLClient] Unexpected error in batch call: %s", exc)

    fallbacks = [_FALLBACK.copy() for _ in transactions]
    logger.warning(
        "[MLClient] Batch call failed — returning %d fallback result(s)",
        len(fallbacks),
    )
    return fallbacks
