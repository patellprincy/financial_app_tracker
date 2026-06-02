"""
Phase 3A — Statement Preview Import (concurrent).

Imports user-approved transactions coming back from the Android preview screen
into the transactions table.  This endpoint does NOT re-parse the PDF; it trusts
the rows the user kept/edited and runs them through the same AI classification +
ML anomaly flow used by manual transaction creation.

Concurrency model (see import_statement_transactions for the phase breakdown):
  - The slow work is network I/O to the AI (/classify) and ML (/anomaly/detect)
    microservices.  Those calls run CONCURRENTLY, bounded by an asyncio.Semaphore.
  - All database access stays SERIALIZED on the single request-scoped Session.
    SQLAlchemy's sync Session is not safe to use from multiple concurrent tasks,
    so concurrent tasks never touch `db`; they operate on detached snapshots.

Guarantees (unchanged from the sequential version):
  - Per-row isolation: one bad row is logged, counted as failed, and skipped;
    the rest still import.
  - Never leaks backend error details to the client; only counts are returned.
  - User ownership is validated before anything is imported.
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
from app.services.ml_service import check_transaction_anomaly
# Reuse the helpers that back manual transaction creation so import behaves
# identically (same category de-duplication and response shape).
from app.services.transaction_service import _get_or_create_category, _to_response

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 200

# Max number of AI/ML calls in flight at once. Keeps us from launching one
# request per transaction against the microservices on a large statement.
# 5–10 is the safe band; 8 is a reasonable middle.
_CONCURRENCY_LIMIT = 8

# Local fallbacks used only if the client coroutines raise unexpectedly. The
# clients themselves already return their own fallbacks on handled failures.
_CLASSIFY_FALLBACK = {
    "category_name": "Other",
    "normalized_category": "other",
    "confidence": 0.0,
    "reason": "AI classification unavailable",
}
_ANOMALY_FALLBACK = {
    "is_anomaly": False,
    "anomaly_status": None,
    "anomaly_score": None,
    "anomaly_reason": "ML anomaly check unavailable",
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


# ── Validation ───────────────────────────────────────────────────────────────

def _parse_transaction_date(raw_date: str) -> datetime:
    """
    Parse an ISO 'YYYY-MM-DD' (or full ISO) date from the preview row and return
    a timezone-aware datetime used as the transaction's created_at.

    Raises ValueError if the date is missing or unparseable so the caller can
    treat the row as a per-row failure.
    """
    if not raw_date or not raw_date.strip():
        raise ValueError("empty transaction_date")

    text = raw_date.strip()
    try:
        # date.fromisoformat handles 'YYYY-MM-DD'; combine to midnight UTC.
        d = datetime.fromisoformat(text)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        # Fall back to date-only parsing for plain 'YYYY-MM-DD'.
        from datetime import date as _date
        d = _date.fromisoformat(text)
        return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _validate_row(item: ImportTransactionItem) -> tuple[str, datetime, str]:
    """
    Validate a single preview row.

    Returns (description, created_at, transaction_type) on success.
    Raises ValueError with a safe, non-sensitive reason on failure.
    """
    description = (item.description or "").strip()
    if not description:
        raise ValueError("description is empty")

    if item.amount == 0:
        raise ValueError("amount is zero")

    created_at = _parse_transaction_date(item.transaction_date)

    # Sign determines type: negative = expense, positive = income.
    transaction_type = "expense" if item.amount < 0 else "income"
    return description, created_at, transaction_type


# ── Detached snapshots (so concurrent ML tasks never touch the Session) ───────

def _snapshot_for_ml(t: Transaction) -> SimpleNamespace:
    """
    Copy the fields the ML client reads into a plain object detached from the
    SQLAlchemy session. Concurrent anomaly tasks only read these attributes, so
    they never trigger a lazy load / refresh on the shared session.
    """
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
    """Load the user's recent transactions once (serially) as detached snapshots."""
    rows = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(_HISTORY_LIMIT)
        .all()
    )
    return [_snapshot_for_ml(t) for t in rows]


# ── Bounded concurrent workers (network I/O only) ─────────────────────────────

async def _classify_row(sem: asyncio.Semaphore, prepared: _PreparedRow) -> dict:
    """Classify one row; bounded by the semaphore. Never raises."""
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


async def _detect_row(
    sem: asyncio.Semaphore,
    snapshot: SimpleNamespace,
    history: list[SimpleNamespace],
) -> dict:
    """Run anomaly detection for one saved transaction; bounded. Never raises."""
    async with sem:
        try:
            return await check_transaction_anomaly(snapshot, history)
        except Exception as exc:
            logger.error(
                "statement_import: anomaly check raised for txn_id=%s — using fallback: %s",
                snapshot.id, exc,
            )
            return dict(_ANOMALY_FALLBACK)


# ── Main entry point ──────────────────────────────────────────────────────────

async def import_statement_transactions(
    upload_id: UUID,
    request: StatementImportRequest,
    user_id,
    db: Session,
) -> StatementImportResponse:
    """
    Import the user-approved preview rows for a statement upload, processing the
    AI/ML calls concurrently.

    Request-level validation (raises HTTP errors, aborts the whole request):
      - upload_id exists AND belongs to the authenticated user (404 otherwise)
      - transactions list is not empty (400 otherwise)

    Phases:
      1. Validate every row (serial, no I/O).                    -> _PreparedRow[]
      2. Classify all valid rows CONCURRENTLY (bounded).         -> dict[]
      3. Insert transactions SERIALLY on the shared session.     -> Transaction[]
      4. Run anomaly detection CONCURRENTLY on detached snapshots (bounded).
      5. Apply anomaly fields SERIALLY and commit.
    Per-row validation/insert/processing failures are logged and counted; they
    never abort the rest of the batch.
    """
    # ── Ownership / existence check (combined to avoid leaking existence) ──
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
        "statement_import: starting (concurrent, limit=%d) upload_id=%s user_id=%s total=%d",
        _CONCURRENCY_LIMIT, upload_id, user_id, total_submitted,
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

    # ── Phase 2: classify all valid rows concurrently (network I/O) ────────
    classifications: list[dict] = (
        await asyncio.gather(*[_classify_row(sem, p) for p in prepared])
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
                amount=p.item.amount,
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

    # ── Phase 4 + 5: anomaly detection concurrently, then apply serially ───
    if saved:
        # Snapshot history once + each saved txn, all detached from the session.
        history_snaps = _load_history_snapshot(db, user_id)
        ml_jobs = [
            (txn, snap, [h for h in history_snaps if h.id != snap.id])
            for txn in saved
            for snap in (_snapshot_for_ml(txn),)
        ]

        anomalies = await asyncio.gather(
            *[_detect_row(sem, snap, hist) for (_, snap, hist) in ml_jobs]
        )

        # Apply results back onto the real ORM rows (serial), then one commit.
        for (txn, _, _), anomaly in zip(ml_jobs, anomalies):
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
            # Transactions were already committed in Phase 3, so they persist;
            # only the anomaly annotations are lost on failure.
            logger.error(
                "statement_import: applying anomaly fields failed (upload_id=%s): %s",
                upload_id, exc,
            )
            db.rollback()

    # Build the response payload while the rows are fresh (before mutating upload).
    response_transactions = [_to_response(t) for t in saved]
    imported_count = len(saved)

    # ── Update the upload record ───────────────────────────────────────────
    upload.status = "imported"
    upload.imported_transactions = imported_count
    upload.failed_transactions = failed
    upload.total_transactions = total_submitted
    db.commit()
    db.refresh(upload)

    logger.info(
        "statement_import: complete (concurrent) upload_id=%s imported=%d failed=%d total=%d",
        upload_id, imported_count, failed, total_submitted,
    )

    return StatementImportResponse(
        upload_id=upload.id,
        status=upload.status,
        imported_transactions=imported_count,
        failed_transactions=failed,
        transactions=response_transactions,
    )
