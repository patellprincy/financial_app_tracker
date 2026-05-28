import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

_FALLBACK: dict = {
    "transaction_type": "expense",
    "category_name": "Other",
    "normalized_category": "other",
    "confidence": 0.0,
    "reason": "AI service unavailable",
}

_REQUIRED_KEYS = {"transaction_type", "category_name", "normalized_category", "confidence", "reason"}
_TIMEOUT_SECONDS = 10.0
_MAX_RETRIES = 1  # 1 retry = 2 total attempts


async def classify_transaction(
    merchant: str,
    amount: float,
    notes: str | None = None,
) -> dict:
    """
    Calls the AI classification microservice via HTTP POST.

    Never raises — returns _FALLBACK on any failure so the main backend
    always completes the transaction save even when the AI service is down.
    """
    url = f"{settings.AI_BACKEND_URL.rstrip('/')}/classify"
    payload = {"merchant": merchant, "amount": amount, "notes": notes}

    logger.info(
        "[ClassificationClient] → POST %s | merchant=%r amount=%.2f",
        url, merchant, amount,
    )

    last_error: Exception | None = None
    total_attempts = _MAX_RETRIES + 1

    for attempt in range(1, total_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            if not isinstance(data, dict) or not _REQUIRED_KEYS.issubset(data.keys()):
                logger.warning(
                    "[ClassificationClient] Invalid response shape on attempt %d/%d: %s",
                    attempt, total_attempts, data,
                )
                return _FALLBACK.copy()

            logger.info(
                "[ClassificationClient] ← HTTP %d | type=%s category=%r confidence=%.2f",
                response.status_code,
                data.get("transaction_type"),
                data.get("category_name"),
                float(data.get("confidence", 0.0)),
            )
            return data

        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning(
                "[ClassificationClient] Timeout on attempt %d/%d (%.1fs limit)",
                attempt, total_attempts, _TIMEOUT_SECONDS,
            )

        except httpx.ConnectError as exc:
            last_error = exc
            logger.error(
                "[ClassificationClient] Cannot connect to AI backend at %s (attempt %d/%d)",
                url, attempt, total_attempts,
            )
            break  # Connection refused will not resolve on retry

        except httpx.HTTPStatusError as exc:
            last_error = exc
            logger.error(
                "[ClassificationClient] HTTP %d from AI backend on attempt %d/%d: %s",
                exc.response.status_code, attempt, total_attempts, exc,
            )
            break  # 4xx/5xx errors will not resolve on retry

        except Exception as exc:
            last_error = exc
            logger.error(
                "[ClassificationClient] Unexpected error on attempt %d/%d: %s",
                attempt, total_attempts, exc,
            )
            break

    logger.error(
        "[ClassificationClient] All %d attempt(s) failed — using fallback. Last error: %s",
        total_attempts, last_error,
    )
    return _FALLBACK.copy()
