"""
Phase 3A — Statement Preview Import (concurrent, cache-aware).

Imports user-approved transactions coming back from the Android preview screen
into the transactions table.  This endpoint does NOT re-parse the PDF; it trusts
the rows the user kept/edited and runs them through AI classification + ML anomaly.

Concurrency model:
  - Classification (Phase 2) is the slow AI I/O work.  Only unique, uncached
    merchants are sent to the AI service, running CONCURRENTLY, bounded by a
    Semaphore.
  - Anomaly detection (Phase 4) is a single HTTP call to /anomaly/detect-batch
    that sends all imported transactions at once — no per-transaction concurrency.
  - All database access stays SERIALIZED on the single request-scoped Session.

Classification optimization:
  - Merchant strings are normalised before lookup so "STARBUCKS #4421" and
    "STARBUCKS #8903" resolve to the same cache key.
  - A single batch DB query fetches all cached entries for unique merchants.
  - Only merchants absent from the cache are sent to the AI service.
  - New (non-fallback) results are written back to the cache after the gather.
  - Every row — including duplicates of the same merchant — receives a result.

Anomaly optimization:
  - All saved transactions are sent to /anomaly/detect-batch in one HTTP call.
  - History is loaded once and all batch members are excluded from it, so
    behavioral features are computed against the user's pre-import history only.

Guarantees (unchanged from the original version):
  - Per-row isolation: one bad row is logged, counted as failed, and skipped.
  - Never leaks backend error details to the client; only counts are returned.
  - User ownership is validated before anything is imported.
  - Fallback classifications (confidence == 0.0) are never persisted to cache.
  - Batch ML failure does not abort the import — fallback anomaly fields are set.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.statement_upload import StatementUpload
from app.models.transaction import Transaction
from app.schemas.statement import (
    ImportTransactionItem,
    StatementImportRequest,
    StatementImportResponse,
)
from app.services.classification_service import classify_transaction
from app.services.merchant_cache_service import (
    get_cached_batch,
    save_classification_to_cache,
)
from app.services.ml_service import check_transactions_anomaly_batch
from app.services.transaction_service import _get_or_create_category, _to_response
from app.utils.merchant_normalizer import normalize_merchant

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 200

# Max concurrent AI classification calls in flight at once.
_CONCURRENCY_LIMIT = 8

_CLASSIFY_FALLBACK = {
    "category_name": "Other",
    "normalized_category": "other",
    "confidence": 0.0,
    "reason": "AI classification unavailable during import",
}
_ANOMALY_FALLBACK = {
    "is_anomaly": False,
    "anomaly_status": None,
    "anomaly_score": None,
    "anomaly_reason": "Anomaly check unavailable during import",
    "ml_model_version": None,
}


@dataclass
class _PreparedRow:
    """A validated input row, ready for classification + insertion."""
    index: int
    item: ImportTransactionItem
    description: str
    created_at: datetime
    transaction_type: str


# ── Helpers — validation ──────────────────────────────────────────────────────

def _parse_transaction_date(raw_date: str) -> datetime:
    if not raw_date or not raw_date.strip():
        raise ValueError("empty transaction_date")
    text = raw_date.strip()
    try:
        d = datetime.fromisoformat(text)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        from datetime import date as _date
        d = _date.fromisoformat(text)
        return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _validate_row(item: ImportTransactionItem) -> tuple[str, datetime, str]:
    description = (item.description or "").strip()
    if not description:
        raise ValueError("description is empty")
    if item.amount == 0:
        raise ValueError("amount is zero")
    created_at = _parse_transaction_date(item.transaction_date)
    transaction_type = "expense" if item.amount < 0 else "income"
    return description, created_at, transaction_type


# ── Helpers — ML snapshots ────────────────────────────────────────────────────

def _snapshot_for_ml(t: Transaction) -> SimpleNamespace:
    return SimpleNamespace(
        id=t.id,
        user_id=t.user_id,
        created_at=t.created_at,
        merchant=t.merchant,
        amount=t.amount,
        category_name=t.category_name,
        transaction_type=t.transaction_type,
        notes=t.notes,
    )


def _load_history_snapshot(db: Session, user_id) -> list[SimpleNamespace]:
    rows = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(_HISTORY_LIMIT)
        .all()
    )
    return [_snapshot_for_ml(t) for t in rows]


# ── Helpers — bounded concurrent classification workers ───────────────────────

async def _classify_row(sem: asyncio.Semaphore, prepared: _PreparedRow) -> dict:
    """Classify one row via the AI service; bounded by the semaphore.  Never raises."""
    async with sem:
        try:
            return await classify_transaction(
                merchant=prepared.description,
                amount=prepared.item.amount,
                notes=(prepared.item.raw_text or "") or None,
            )
        except Exception as exc:
            logger.error(
                "statement_import: classification raised for %r — using fallback: %s",
                prepared.description, exc,
            )
            return {"transaction_type": prepared.transaction_type, **_CLASSIFY_FALLBACK}


# ── Phase 2 helper — cache-aware batch classification ────────────────────────

async def _classify_with_cache(
    sem: asyncio.Semaphore,
    prepared: list[_PreparedRow],
    user_id,
    db: Session,
    upload_id,
) -> list[dict]:
    """
    Classify all prepared rows with merchant-cache deduplication.

    Steps:
      1. Normalise each row's description to a stable cache key.
      2. Collect unique (normalized_merchant, transaction_type) pairs.
      3. Batch-fetch all matching cache entries in a single DB query.
      4. For unique pairs absent from the cache, send ONE AI request each
         (concurrently, bounded by the semaphore).
      5. Persist non-fallback AI results to the cache.
      6. Map every prepared row (including duplicates) to its result.
    """
    # Step 1: per-row cache keys
    row_keys: list[tuple[str, str]] = [
        (normalize_merchant(p.description), p.transaction_type)
        for p in prepared
    ]

    # Step 2: unique pairs in insertion order
    unique_pairs: list[tuple[str, str]] = list(dict.fromkeys(row_keys))

    # Step 3: batch cache lookup
    cache_map: dict[tuple[str, str], dict] = get_cached_batch(db, user_id, unique_pairs)
    cache_miss_pairs: list[tuple[str, str]] = [
        pair for pair in unique_pairs if pair not in cache_map
    ]

    hit_count = len(unique_pairs) - len(cache_miss_pairs)
    logger.info(
        "statement_import[cache]: total_rows=%d unique_merchants=%d "
        "cache_hits=%d cache_misses=%d ai_calls_needed=%d upload_id=%s",
        len(prepared),
        len(unique_pairs),
        hit_count,
        len(cache_miss_pairs),
        len(cache_miss_pairs),
        upload_id,
    )

    # Step 4: pick one representative _PreparedRow per uncached pair
    rep_rows: dict[tuple[str, str], _PreparedRow] = {}
    for p, key in zip(prepared, row_keys):
        if key in cache_miss_pairs and key not in rep_rows:
            rep_rows[key] = p

    # Step 5: classify uncached merchants concurrently
    fallback_count = 0
    if cache_miss_pairs:
        miss_results: list[dict] = await asyncio.gather(
            *[_classify_row(sem, rep_rows[pair]) for pair in cache_miss_pairs]
        )

        for pair, result in zip(cache_miss_pairs, miss_results):
            normalized_m, tx_type = pair
            is_fallback = result.get("confidence", 0.0) == 0.0
            if is_fallback:
                fallback_count += 1
            else:
                try:
                    save_classification_to_cache(db, user_id, normalized_m, tx_type, result)
                except Exception as exc:
                    logger.warning(
                        "statement_import[cache]: failed to save cache entry for %r: %s",
                        normalized_m, exc,
                    )
            cache_map[pair] = result

        logger.info(
            "statement_import[cache]: ai_calls_made=%d fallbacks=%d upload_id=%s",
            len(cache_miss_pairs), fallback_count, upload_id,
        )
    else:
        logger.info(
            "statement_import[cache]: all %d unique merchant(s) served from cache — "
            "0 AI calls made upload_id=%s",
            len(unique_pairs), upload_id,
        )

    # Step 6: map every prepared row to its classification
    results: list[dict] = []
    for key in row_keys:
        if key in cache_map:
            results.append(cache_map[key])
        else:
            results.append({"transaction_type": key[1], **_CLASSIFY_FALLBACK})

    return results


# ── Main entry point ──────────────────────────────────────────────────────────

async def import_statement_transactions(
    upload_id: UUID,
    request: StatementImportRequest,
    user_id,
    db: Session,
) -> StatementImportResponse:
    """
    Import the user-approved preview rows for a statement upload.

    Phases:
      1. Validate every row (serial, no I/O).                             -> _PreparedRow[]
      2. Classify with merchant cache (batch lookup + concurrent           -> dict[]
         AI only for uncached unique merchants).
      3. Insert transactions SERIALLY on the shared session.               -> Transaction[]
      4. Run anomaly detection via a SINGLE batch ML call,                 -> dict[]
         then apply results serially and commit.
    """
    upload = (
        db.query(StatementUpload)
        .filter(StatementUpload.id == upload_id, StatementUpload.user_id == user_id)
        .first()
    )
    if upload is None:
        logger.warning(
            "statement_import: upload not found or not owned — upload_id=%s user_id=%s",
            upload_id, user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement upload not found.",
        )

    if not request.transactions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No transactions provided to import.",
        )

    total_submitted = len(request.transactions)
    logger.info(
        "statement_import: starting upload_id=%s user_id=%s total=%d",
        upload_id, user_id, total_submitted,
    )

    failed = 0
    sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)

    # ── Phase 1: validate every row (serial, CPU only) ─────────────────────
    prepared: list[_PreparedRow] = []
    for index, item in enumerate(request.transactions):
        try:
            description, created_at, transaction_type = _validate_row(item)
            prepared.append(_PreparedRow(index, item, description, created_at, transaction_type))
        except ValueError as exc:
            failed += 1
            logger.warning(
                "statement_import: row %d/%d failed validation — %s (upload_id=%s)",
                index + 1, total_submitted, exc, upload_id,
            )

    # ── Phase 2: cache-aware classification (batch lookup + minimal AI calls) ─
    classifications: list[dict] = (
        await _classify_with_cache(sem, prepared, user_id, db, upload_id)
        if prepared else []
    )

    # ── Phase 3: insert transactions serially (DB writes single-threaded) ──
    saved: list[Transaction] = []
    for p, classification in zip(prepared, classifications):
        try:
            category = _get_or_create_category(
                db=db,
                name=classification["category_name"],
                normalized_name=classification["normalized_category"],
                transaction_type=p.transaction_type,
            )
            transaction = Transaction(
                user_id=user_id,
                merchant=p.description,
                amount=abs(p.item.amount),
                notes=p.item.raw_text or "",
                transaction_type=p.transaction_type,
                category_id=category.id,
                category_name=category.name,
                confidence=classification["confidence"],
                reason=classification["reason"],
                created_at=p.created_at,
            )
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            saved.append(transaction)
        except Exception as exc:
            failed += 1
            logger.error(
                "statement_import: row %d/%d insert failed (upload_id=%s): %s",
                p.index + 1, total_submitted, upload_id, exc,
            )
            db.rollback()

    # ── Phase 4: single batch anomaly detection + apply serially ───────────
    if saved:
        # Load history after Phase 3 then exclude the just-imported transactions
        # so behavioural features are computed against the user's PRE-IMPORT history.
        history_snaps = _load_history_snapshot(db, user_id)
        saved_ids = {t.id for t in saved}
        pre_import_history = [h for h in history_snaps if h.id not in saved_ids]

        transaction_snaps = [_snapshot_for_ml(t) for t in saved]

        logger.info(
            "statement_import[ml]: sending batch anomaly request — "
            "transactions=%d history=%d upload_id=%s",
            len(transaction_snaps), len(pre_import_history), upload_id,
        )

        anomalies: list[dict] = await check_transactions_anomaly_batch(
            transactions=transaction_snaps,
            history=pre_import_history,
        )

        # Sanity-check: the batch client guarantees same-length results, but
        # guard against any unexpected mismatch.
        if len(anomalies) != len(saved):
            logger.error(
                "statement_import[ml]: anomaly count mismatch saved=%d results=%d — "
                "applying fallbacks upload_id=%s",
                len(saved), len(anomalies), upload_id,
            )
            anomalies = [_ANOMALY_FALLBACK.copy() for _ in saved]

        anomaly_count = sum(1 for a in anomalies if a.get("is_anomaly"))
        fallback_ml_count = sum(1 for a in anomalies if a.get("anomaly_score") is None)
        logger.info(
            "statement_import[ml]: batch complete — anomalies=%d fallbacks=%d upload_id=%s",
            anomaly_count, fallback_ml_count, upload_id,
        )

        for txn, anomaly in zip(saved, anomalies):
            txn.is_anomaly = anomaly["is_anomaly"]
            txn.anomaly_status = anomaly["anomaly_status"]
            txn.anomaly_score = anomaly["anomaly_score"]
            txn.anomaly_reason = anomaly["anomaly_reason"]
            txn.ml_model_version = anomaly["ml_model_version"]
            txn.anomaly_checked_at = datetime.now(timezone.utc)

        try:
            db.commit()
            for txn in saved:
                db.refresh(txn)
        except Exception as exc:
            logger.error(
                "statement_import: applying anomaly fields failed (upload_id=%s): %s",
                upload_id, exc,
            )
            db.rollback()

    response_transactions = [_to_response(t) for t in saved]
    imported_count = len(saved)

    upload.status = "imported"
    upload.imported_transactions = imported_count
    upload.failed_transactions = failed
    upload.total_transactions = total_submitted
    db.commit()
    db.refresh(upload)

    logger.info(
        "statement_import: complete upload_id=%s imported=%d failed=%d total=%d",
        upload_id, imported_count, failed, total_submitted,
    )

    return StatementImportResponse(
        upload_id=upload.id,
        status=upload.status,
        imported_transactions=imported_count,
        failed_transactions=failed,
        transactions=response_transactions,
    )
