"""
Async HTTP client that calls the AI microservice POST /statements/cleanup endpoint.

Design:
  - The AI cleanup service is the final authority on which rows to keep and what
    signs to assign. Its output is returned verbatim to the caller.
  - No deterministic noise filtering, sign normalization, or deduplication is
    applied after the AI responds.
  - Fallback: if the AI service is unavailable or returns nothing usable, the
    raw parser candidates are returned as-is so the upload always completes.
  - The caller (statement_parser_service) has already deduplicated structural
    duplicates, so the AI receives a compact, unmodified candidate set.
"""

import logging
import httpx
from app.config import settings
from app.services.statement_parser_service import ParsedTransaction

logger = logging.getLogger(__name__)

_CLEANUP_PATH = "/statements/cleanup"


async def ai_cleanup(
    candidates: list[ParsedTransaction],
    statement_type: str = "unknown",
) -> list[ParsedTransaction]:
    """
    Send parser candidates to the AI cleanup service and return its output
    directly.

    - When AI_CLEANUP_ENABLED=false: returns candidates as-is.
    - When the AI call succeeds: returns AI rows verbatim (no post-processing).
    - When the AI call fails for any reason: returns candidates as-is and logs
      the reason.
    """
    if not candidates:
        return candidates

    ai_enabled = settings.AI_CLEANUP_ENABLED
    logger.info(
        "statement_upload: AI cleanup enabled=%s statement_type=%s candidate_count=%d",
        ai_enabled, statement_type, len(candidates),
    )

    if not ai_enabled:
        logger.info("statement_upload: AI cleanup skipped — returning parser candidates as-is")
        return candidates

    url = settings.AI_BACKEND_URL.rstrip("/") + _CLEANUP_PATH
    timeout = settings.AI_CLEANUP_TIMEOUT_SECONDS

    logger.info(
        "statement_upload: calling AI cleanup endpoint=%s candidate_count=%d timeout=%ds",
        url, len(candidates), timeout,
    )

    payload = {
        "statement_type": statement_type,
        "transactions": [
            {
                "transaction_date": t.transaction_date,
                "description":      t.description,
                "amount":           t.amount,
                "raw_text":         t.raw_text,
            }
            for t in candidates
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        rows = data.get("transactions", [])
        parsed: list[ParsedTransaction] = []
        for row in rows:
            try:
                parsed.append(ParsedTransaction(
                    transaction_date=str(row["transaction_date"]),
                    description=str(row["description"]),
                    amount=float(row["amount"]),
                    raw_text=str(row["raw_text"]),
                ))
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("statement_upload: skipping malformed AI row (%s)", exc)

        if not parsed:
            logger.warning(
                "statement_upload: AI returned 0 valid rows — falling back to parser candidates"
            )
            return candidates

        logger.info(
            "statement_upload: AI cleanup success input=%d output=%d",
            len(candidates), len(parsed),
        )
        return parsed

    except httpx.TimeoutException:
        reason = f"timeout after {timeout}s"
    except httpx.HTTPStatusError as exc:
        reason = f"HTTP {exc.response.status_code} from AI service"
    except httpx.ConnectError:
        reason = f"cannot connect to AI service at {url}"
    except Exception as exc:
        reason = f"unexpected error: {type(exc).__name__}: {exc}"

    logger.warning(
        "statement_upload: AI cleanup failed (%s) — returning parser candidates as-is count=%d",
        reason, len(candidates),
    )
    return candidates
