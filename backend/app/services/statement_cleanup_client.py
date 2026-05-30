"""
Async HTTP client that calls the AI microservice POST /statements/cleanup endpoint.

Design:
  - Never raises: every error path is caught, logged with a reason, and the
    original candidate list is returned so the upload never fails.
  - Deterministic pre-clean runs FIRST (no LLM cost) to strip obvious noise.
  - AI call runs second when AI_CLEANUP_ENABLED=true.
"""

import logging
import re
import httpx
from app.config import settings
from app.services.statement_parser_service import ParsedTransaction

logger = logging.getLogger(__name__)

_CLEANUP_PATH = "/statements/cleanup"

# ── Deterministic pre-clean ────────────────────────────────────────────────
# Generic patterns that are never real transactions, regardless of bank.
# Uses \s* so "OpeningBalance" and "Opening Balance" both match.

_NOISE_RE = re.compile(
    r"""
    \b(
        opening\s*balance | closing\s*balance | previous\s*balance
      | new\s*balance     | balance\s*forward | balance\s*brought\s*forward
      | amount\s+due      | total\s+amount\s+due | payment\s+due
      | minimum\s*payment | minimum\s+due
      | available\s*credit | credit\s+limit
      | rewards?\s+summary | cash\s*back\s+summary | points\s+summary
      | rewards?\s+redeemed
      | \btotals?\b | sub\s*-?\s*total | grand\s+total
      | total\s+withdrawals | total\s+deposits
      | statement\s+period | statement\s+date | statement\s+balance
      | account\s+(?:number|no\.?|summary|information)
      | (?:^|\s)page\s+\d
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _rule_pre_clean(
    candidates: list[ParsedTransaction],
) -> tuple[list[ParsedTransaction], int]:
    """
    Fast deterministic filter applied before the AI call.
    Returns (kept_candidates, removed_count).
    """
    kept = [c for c in candidates if not _NOISE_RE.search(c.description)]
    return kept, len(candidates) - len(kept)


# ── AI cleanup client ──────────────────────────────────────────────────────

async def ai_cleanup(candidates: list[ParsedTransaction]) -> list[ParsedTransaction]:
    """
    Clean statement candidates:
      1. Deterministic rule pre-clean (always runs, free).
      2. AI microservice call (only when AI_CLEANUP_ENABLED=true).

    On any failure returns the best available candidate list and logs the reason.
    """
    if not candidates:
        return candidates

    # ── Step 1: Deterministic pre-clean ───────────────────────────────────
    after_rules, rules_removed = _rule_pre_clean(candidates)
    logger.info(
        "statement_upload: rule pre-clean removed=%d kept=%d",
        rules_removed, len(after_rules),
    )

    ai_enabled = settings.AI_CLEANUP_ENABLED
    logger.info("statement_upload: AI cleanup enabled=%s", ai_enabled)

    if not ai_enabled:
        logger.info(
            "statement_upload: AI cleanup skipped (AI_CLEANUP_ENABLED=false) "
            "final preview count=%d",
            len(after_rules),
        )
        return after_rules

    if not after_rules:
        logger.info("statement_upload: 0 candidates after rule pre-clean — skipping AI call")
        return after_rules

    # ── Step 2: AI microservice call ───────────────────────────────────────
    url = settings.AI_BACKEND_URL.rstrip("/") + _CLEANUP_PATH
    timeout = settings.AI_CLEANUP_TIMEOUT_SECONDS

    logger.info(
        "statement_upload: calling AI cleanup endpoint=%s candidate_count=%d timeout=%ds",
        url, len(after_rules), timeout,
    )

    payload = {
        "transactions": [
            {
                "transaction_date": t.transaction_date,
                "description":      t.description,
                "amount":           t.amount,
                "raw_text":         t.raw_text,
            }
            for t in after_rules
        ]
    }

    fallback_reason: str | None = None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()          # body buffered; safe inside context

        rows = data.get("transactions", [])

        cleaned: list[ParsedTransaction] = []
        for row in rows:
            try:
                cleaned.append(ParsedTransaction(
                    transaction_date=str(row["transaction_date"]),
                    description=str(row["description"]),
                    amount=float(row["amount"]),
                    raw_text=str(row["raw_text"]),
                ))
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "statement_upload: skipping malformed AI response row (%s)", e
                )

        if not cleaned:
            fallback_reason = "AI returned 0 valid rows"
        else:
            logger.info(
                "statement_upload: AI cleanup success input_count=%d output_count=%d",
                len(after_rules), len(cleaned),
            )
            return cleaned

    except httpx.TimeoutException:
        fallback_reason = f"timeout after {timeout}s"
    except httpx.HTTPStatusError as e:
        fallback_reason = f"HTTP {e.response.status_code} from AI service"
    except httpx.ConnectError:
        fallback_reason = f"cannot connect to AI service at {url}"
    except Exception as e:
        fallback_reason = f"unexpected error: {type(e).__name__}: {e}"

    # ── Fallback ───────────────────────────────────────────────────────────
    logger.warning(
        "statement_upload: AI cleanup fallback used reason=%s — "
        "returning rule-cleaned candidates count=%d",
        fallback_reason, len(after_rules),
    )
    return after_rules
