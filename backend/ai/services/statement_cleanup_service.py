import json
import logging
import re
from groq import Groq
from ai.core.config import settings
from ai.services.prompt_loader import get_statement_cleanup_prompt

logger = logging.getLogger(__name__)

_MAX_CANDIDATES_PER_CHUNK = 50
_VALID_TRANSACTION_TYPES = {"expense", "income"}

# If the AI removes more than this fraction of candidate rows, treat the result
# as suspicious and fall back to the (already rule-cleaned) input — UNLESS every
# removed row is clearly statement metadata.  Protects against over-cleaning.
_MAX_REMOVAL_FRACTION = 0.40


# ── Markdown fence stripping ───────────────────────────────────────────────

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_markdown_fences(raw: str) -> str:
    return _FENCE_RE.sub("", raw).strip()


# ── Non-transaction (statement metadata) detection ─────────────────────────
# Used ONLY to judge whether the AI's removals were "clearly non-transaction".
# These patterns intentionally match summary / balance / header lines and must
# NOT match real posted transactions (including posted fees / posted interest).

_NOISE_RE = re.compile(
    r"""
    \b(
        opening\s*balance | closing\s*balance | previous\s*balance
      | new\s*balance     | balance\s*forward | balance\s*brought\s*forward
      | available\s*balance
      | amount\s+due      | total\s+amount\s+due | payment\s+due
      | minimum\s*payment | minimum\s+due
      | available\s*credit | credit\s+available | credit\s+limit
      | rewards?\s+summary | cash\s*back\s+summary | points\s+summary
      | rewards?\s+redeemed
      | interest\s+summary | total\s+interest | total\s+fees
      | sub\s*-?\s*total | grand\s+total | total\s+withdrawals | total\s+deposits
      | \btotals?\b
      | statement\s+(?:period|date|balance|summary)
      | account\s+(?:number|no\.?|summary|information)
      | card\s+number
      | (?:^|\s)page\s+\d
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _is_clearly_non_transaction(row: dict) -> bool:
    """True only when the row's description/raw_text clearly matches statement
    metadata.  Conservative on purpose: anything ambiguous returns False."""
    text = f"{row.get('description', '')} {row.get('raw_text', '')}"
    return bool(_NOISE_RE.search(text))


def _row_key(row: dict) -> str:
    """Stable identity for matching an input row against AI output.
    raw_text is never modified by the prompt, so it is the primary key;
    fall back to date+description+amount when raw_text is missing."""
    raw = str(row.get("raw_text", "")).strip()
    if raw:
        return raw
    return f"{row.get('transaction_date')}|{row.get('description')}|{row.get('amount')}"


# ── Sign correction ────────────────────────────────────────────────────────

def _apply_sign_correction(row: dict) -> tuple[dict, bool]:
    """
    Enforce FinSight AI sign convention using the transaction_type the model returned.

      expense → amount must be negative  (< 0)
      income  → amount must be positive  (> 0)

    Returns (corrected_row, was_corrected).
    If transaction_type is absent or unrecognised the amount is trusted as-is.
    """
    raw_type = row.get("transaction_type")
    if not raw_type:
        return row, False

    txn_type = str(raw_type).lower().strip()
    if txn_type not in _VALID_TRANSACTION_TYPES:
        logger.warning(
            "statement_cleanup: unrecognised transaction_type='%s' for '%s' — skipping sign correction",
            raw_type, row.get("description", ""),
        )
        return row, False

    amount = row["amount"]

    if txn_type == "expense" and amount > 0:
        corrected = {**row, "amount": -amount}
        logger.warning(
            "statement_cleanup: sign corrected expense '%s'  %.2f → %.2f",
            row.get("description", ""), amount, -amount,
        )
        return corrected, True

    if txn_type == "income" and amount < 0:
        corrected = {**row, "amount": abs(amount)}
        logger.warning(
            "statement_cleanup: sign corrected income  '%s'  %.2f → %.2f",
            row.get("description", ""), amount, abs(amount),
        )
        return corrected, True

    return row, False


# ── Response validator ─────────────────────────────────────────────────────

def _validate_and_parse(raw_json: str, fallback: list[dict]) -> tuple[list[dict], int]:
    """
    Parse the LLM JSON response, apply sign correction, and validate each row.
    Returns (validated_rows, sign_corrected_count), or (fallback, 0) on any
    structural error so the caller always receives at least the raw input.
    """
    logger.info("statement_cleanup: raw model response length=%d", len(raw_json))
    cleaned = _strip_markdown_fences(raw_json)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(
            "statement_cleanup: JSON decode failed (%s) — returning original chunk. "
            "First 200 chars: %s",
            e, raw_json[:200],
        )
        return fallback, 0

    rows = data.get("transactions")
    if rows is None:
        logger.warning(
            "statement_cleanup: response missing 'transactions' key — returning original chunk."
        )
        return fallback, 0

    validated: list[dict] = []
    sign_corrections = 0

    for row in rows:
        try:
            base = {
                "transaction_date": str(row["transaction_date"]),
                "description":      str(row["description"]),
                "amount":           float(row["amount"]),
                "raw_text":         str(row["raw_text"]),
            }
            # Carry transaction_type through if present (used for sign correction + logs)
            if "transaction_type" in row and row["transaction_type"]:
                base["transaction_type"] = str(row["transaction_type"]).lower().strip()

            corrected, was_corrected = _apply_sign_correction(base)
            if was_corrected:
                sign_corrections += 1
            validated.append(corrected)

        except (KeyError, ValueError, TypeError) as e:
            logger.warning("statement_cleanup: skipping malformed row from AI (%s)", e)

    expense_count = sum(1 for r in validated if r["amount"] < 0)
    income_count  = sum(1 for r in validated if r["amount"] >= 0)

    logger.info(
        "statement_cleanup: parsed transactions count=%d "
        "expense_count=%d income_count=%d sign_corrections_applied=%d",
        len(validated), expense_count, income_count, sign_corrections,
    )
    return validated, sign_corrections


# ── Main service ───────────────────────────────────────────────────────────

def clean_statement_transactions(candidates: list[dict]) -> list[dict]:
    """
    Send candidate rows to the LLM for noise filtering and sign correction.

    The static system prompt is loaded via prompt_loader (@lru_cache — disk
    read once per worker lifetime).  Candidate rows are always passed
    dynamically as the user message and are NEVER cached.

    On any per-chunk error the original chunk is kept so the caller always
    receives at least the raw parser output.
    """
    logger.info("statement_cleanup: request received candidate_count=%d", len(candidates))

    if not candidates:
        return candidates

    system_prompt = get_statement_cleanup_prompt()
    cache_info = get_statement_cleanup_prompt.cache_info()
    logger.info(
        "statement_cleanup: prompt loaded (lru_cache hits=%d misses=%d)",
        cache_info.hits, cache_info.misses,
    )

    client = Groq(api_key=settings.groq_api_key)
    logger.info(
        "statement_cleanup: calling LLM provider=groq model=%s", settings.groq_model
    )

    chunks = [
        candidates[i: i + _MAX_CANDIDATES_PER_CHUNK]
        for i in range(0, len(candidates), _MAX_CANDIDATES_PER_CHUNK)
    ]

    cleaned_all: list[dict] = []
    sign_corrected_count = 0
    for idx, chunk in enumerate(chunks, 1):
        logger.info(
            "statement_cleanup: chunk %d/%d sending %d candidates",
            idx, len(chunks), len(chunk),
        )
        user_message = json.dumps({"transactions": chunk}, ensure_ascii=False)

        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            validated, chunk_sign_corrections = _validate_and_parse(raw, chunk)
            sign_corrected_count += chunk_sign_corrections
            logger.info(
                "statement_cleanup: chunk %d/%d result %d → %d",
                idx, len(chunks), len(chunk), len(validated),
            )
            cleaned_all.extend(validated)

        except Exception as e:
            logger.error(
                "statement_cleanup: chunk %d/%d LLM call failed (%s) — keeping original chunk",
                idx, len(chunks), e,
            )
            cleaned_all.extend(chunk)

    # ── Over-cleaning guard + debug accounting ─────────────────────────────
    result = _guard_against_over_cleaning(candidates, cleaned_all, sign_corrected_count)

    total_expense = sum(1 for r in result if r["amount"] < 0)
    total_income  = sum(1 for r in result if r["amount"] >= 0)
    logger.info(
        "statement_cleanup: returning cleaned count=%d expense_count=%d income_count=%d",
        len(result), total_expense, total_income,
    )
    return result


# ── Over-cleaning guard ─────────────────────────────────────────────────────

def _guard_against_over_cleaning(
    candidates: list[dict],
    cleaned: list[dict],
    sign_corrected_count: int,
) -> list[dict]:
    """
    Compare the AI output against the input candidates and decide whether to
    trust it.  Logs internal debug counts and the description + reason of each
    removed row (without logging full account numbers).

    Fallback policy (rule 9):
      If the AI removed more than _MAX_REMOVAL_FRACTION of the candidates AND
      at least one removed row is NOT clearly statement metadata, treat the
      result as suspicious and fall back to the original (rule-cleaned) input.
      We never silently return an over-cleaned result.
    """
    input_count = len(candidates)
    kept_keys = {_row_key(r) for r in cleaned}
    removed = [c for c in candidates if _row_key(c) not in kept_keys]

    kept_count = input_count - len(removed)
    removed_count = len(removed)

    logger.info(
        "statement_cleanup: counts input_count=%d kept_count=%d "
        "removed_count=%d sign_corrected_count=%d",
        input_count, kept_count, removed_count, sign_corrected_count,
    )

    # Per-row removal audit (dev only). Descriptions can be truncated/redacted
    # by the parser already; we deliberately avoid logging raw_text.
    not_clearly_metadata: list[dict] = []
    for row in removed:
        clearly = _is_clearly_non_transaction(row)
        if not clearly:
            not_clearly_metadata.append(row)
        logger.debug(
            "statement_cleanup: removed row description=%r reason=%s",
            _redact(str(row.get("description", ""))),
            "clearly_non_transaction" if clearly else "ambiguous_removal",
        )

    if input_count == 0:
        return cleaned

    removal_fraction = removed_count / input_count
    if removal_fraction > _MAX_REMOVAL_FRACTION and not_clearly_metadata:
        logger.warning(
            "statement_cleanup: SUSPICIOUS over-cleaning — removed %d/%d (%.0f%%) "
            "candidates and %d removal(s) were not clearly metadata. "
            "Falling back to rule-cleaned input to avoid deleting real transactions.",
            removed_count, input_count, removal_fraction * 100,
            len(not_clearly_metadata),
        )
        return candidates

    if removal_fraction > _MAX_REMOVAL_FRACTION:
        logger.warning(
            "statement_cleanup: removed %d/%d (%.0f%%) candidates — above the "
            "%.0f%% threshold, but every removal was clearly statement metadata, "
            "so the cleaned result is accepted.",
            removed_count, input_count, removal_fraction * 100,
            _MAX_REMOVAL_FRACTION * 100,
        )

    return cleaned


# Account/card numbers: collapse any run of 6+ digits so we never log them.
_DIGIT_RUN_RE = re.compile(r"\d{6,}")


def _redact(text: str) -> str:
    return _DIGIT_RUN_RE.sub("[redacted]", text)
