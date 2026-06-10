"""
Merchant classification cache — DB-backed lookup and write helpers.

All public functions accept a SQLAlchemy Session and are safe to call from
the serial phases of any request handler.  They must NOT be called from
inside concurrent coroutines because they write to the shared session.

Cache key: (user_id, normalized_merchant, transaction_type)

Zero-confidence results (fallbacks produced when the AI service is
unavailable) are never persisted — the cache only stores real AI results.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.merchant_cache import MerchantClassificationCache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single-row lookup
# ---------------------------------------------------------------------------

def get_cached_classification(
    db: Session,
    user_id,
    normalized_merchant: str,
    transaction_type: str,
) -> dict | None:
    """
    Return the cached classification for (user_id, merchant, type) or None.

    Only queries the user-specific cache.  Returns None for empty merchant keys
    so callers can treat them as unconditional cache misses.
    """
    if not normalized_merchant:
        return None

    row = (
        db.query(MerchantClassificationCache)
        .filter(
            MerchantClassificationCache.user_id == user_id,
            MerchantClassificationCache.normalized_merchant == normalized_merchant,
            MerchantClassificationCache.transaction_type == transaction_type,
        )
        .first()
    )

    if row is None:
        return None

    return {
        "transaction_type": row.transaction_type,
        "category_name": row.category_name,
        "normalized_category": row.normalized_category,
        "confidence": row.confidence,
        "reason": row.reason,
    }


# ---------------------------------------------------------------------------
# Batch lookup (used by the import path to fetch all cache entries in one query)
# ---------------------------------------------------------------------------

def get_cached_batch(
    db: Session,
    user_id,
    merchant_type_pairs: list[tuple[str, str]],
) -> dict[tuple[str, str], dict]:
    """
    Bulk-lookup cached classifications for a list of (normalized_merchant, transaction_type) pairs.

    Returns a dict keyed by (normalized_merchant, transaction_type).
    Pairs with no cache entry are simply absent from the result dict.
    Empty normalized-merchant strings are silently skipped.
    """
    if not merchant_type_pairs:
        return {}

    # Filter out empty keys before hitting the DB.
    valid_pairs = [(m, t) for m, t in merchant_type_pairs if m]
    if not valid_pairs:
        return {}

    unique_merchants = list({m for m, _ in valid_pairs})

    rows = (
        db.query(MerchantClassificationCache)
        .filter(
            MerchantClassificationCache.user_id == user_id,
            MerchantClassificationCache.normalized_merchant.in_(unique_merchants),
        )
        .all()
    )

    valid_pair_set = set(valid_pairs)
    result: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.normalized_merchant, row.transaction_type)
        if key in valid_pair_set:
            result[key] = {
                "transaction_type": row.transaction_type,
                "category_name": row.category_name,
                "normalized_category": row.normalized_category,
                "confidence": row.confidence,
                "reason": row.reason,
            }

    return result


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save_classification_to_cache(
    db: Session,
    user_id,
    normalized_merchant: str,
    transaction_type: str,
    classification: dict,
) -> None:
    """
    Persist an AI classification result to the merchant cache.

    Rules:
    - Zero-confidence results (fallbacks) are never saved.
    - Empty normalized-merchant keys are never saved.
    - If an entry already exists and the new confidence is strictly higher,
      the existing entry is updated.
    - If a concurrent writer caused a uniqueness collision on INSERT, the
      error is swallowed — the existing entry wins.
    """
    if not normalized_merchant:
        return

    confidence = float(classification.get("confidence", 0.0))
    if confidence == 0.0:
        logger.debug(
            "[MerchantCache] Skipping save for %r — zero confidence (fallback)",
            normalized_merchant,
        )
        return

    existing = (
        db.query(MerchantClassificationCache)
        .filter(
            MerchantClassificationCache.user_id == user_id,
            MerchantClassificationCache.normalized_merchant == normalized_merchant,
            MerchantClassificationCache.transaction_type == transaction_type,
        )
        .first()
    )

    if existing is not None:
        if confidence > existing.confidence:
            existing.category_name = classification["category_name"]
            existing.normalized_category = classification["normalized_category"]
            existing.confidence = confidence
            existing.reason = classification.get("reason", "")
            existing.source = "ai"
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            logger.debug(
                "[MerchantCache] Updated %r → %s (confidence %.2f → %.2f)",
                normalized_merchant,
                classification["category_name"],
                existing.confidence,
                confidence,
            )
        return

    row = MerchantClassificationCache(
        user_id=user_id,
        normalized_merchant=normalized_merchant,
        transaction_type=transaction_type,
        category_name=classification["category_name"],
        normalized_category=classification["normalized_category"],
        confidence=confidence,
        reason=classification.get("reason", ""),
        source="ai",
    )
    try:
        db.add(row)
        db.commit()
        logger.debug(
            "[MerchantCache] Saved %r → %s / %s (confidence %.2f)",
            normalized_merchant,
            classification["category_name"],
            transaction_type,
            confidence,
        )
    except IntegrityError:
        db.rollback()
        logger.debug(
            "[MerchantCache] Concurrent insert for %r — existing entry wins",
            normalized_merchant,
        )
