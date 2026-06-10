import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.category import Category
from app.models.transaction import Transaction
from fastapi import HTTPException, status
from app.schemas.transaction import (
    ManualTransactionRequest,
    TransactionResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
)

from app.services.classification_service import classify_transaction
from app.services.merchant_cache_service import (
    get_cached_classification,
    save_classification_to_cache,
)
from app.services.ml_service import check_transaction_anomaly
from app.utils.merchant_normalizer import normalize_merchant

logger = logging.getLogger(__name__)


def _to_response(t: Transaction) -> TransactionResponse:
    return TransactionResponse(
        id=t.id,
        user_id=str(t.user_id),
        merchant=t.merchant,
        amount=t.amount,
        notes=t.notes,
        transaction_type=t.transaction_type,
        category_id=t.category_id,
        category_name=t.category_name,
        confidence=t.confidence,
        reason=t.reason,
        created_at=t.created_at,
        is_anomaly=t.is_anomaly,
        anomaly_status=t.anomaly_status,
        anomaly_score=t.anomaly_score,
        anomaly_reason=t.anomaly_reason,
        anomaly_checked_at=t.anomaly_checked_at,
        ml_model_version=t.ml_model_version,
    )


def _get_or_create_category(
    db: Session, name: str, normalized_name: str, transaction_type: str
) -> Category:
    category = (
        db.query(Category)
        .filter(
            Category.normalized_name == normalized_name,
            Category.transaction_type == transaction_type,
        )
        .first()
    )
    if category is None:
        category = Category(
            name=name,
            normalized_name=normalized_name,
            transaction_type=transaction_type,
        )
        db.add(category)
        db.commit()
        db.refresh(category)
        logger.info("Created global category: %s (%s)", name, transaction_type)
    return category


async def create_manual_transaction(
    request: ManualTransactionRequest, user_id, db: Session
) -> TransactionResponse:
    # Derive the expected transaction type from the amount sign so we can use
    # it as part of the merchant cache key (same key used by the import path).
    preliminary_type = "expense" if request.amount < 0 else "income"
    normalized = normalize_merchant(request.merchant)

    # ── Cache lookup ──────────────────────────────────────────────────────────
    cached = get_cached_classification(db, user_id, normalized, preliminary_type)

    if cached is not None:
        logger.info(
            "[MerchantCache] HIT  merchant=%r normalized=%r → %s / %s (confidence=%.2f)",
            request.merchant,
            normalized,
            cached["transaction_type"],
            cached["category_name"],
            cached["confidence"],
        )
        classification = cached
    else:
        # ── Cache miss — call AI ──────────────────────────────────────────────
        logger.info(
            "[MerchantCache] MISS merchant=%r normalized=%r — calling AI",
            request.merchant,
            normalized,
        )
        classification = await classify_transaction(
            merchant=request.merchant,
            amount=request.amount,
            notes=request.notes or None,
        )
        logger.info(
            "[MerchantCache] AI classified %r → %s / %s (confidence=%.2f)",
            request.merchant,
            classification["transaction_type"],
            classification["category_name"],
            classification["confidence"],
        )

        # Save to cache using the sign-derived type as key so future lookups
        # from the import path (which also derives type from sign) hit the cache.
        save_classification_to_cache(
            db, user_id, normalized, preliminary_type, classification
        )

    category = _get_or_create_category(
        db=db,
        name=classification["category_name"],
        normalized_name=classification["normalized_category"],
        transaction_type=classification["transaction_type"],
    )

    transaction = Transaction(
        user_id=user_id,
        merchant=request.merchant,
        amount=abs(request.amount),
        notes=request.notes,
        transaction_type=classification["transaction_type"],
        category_id=category.id,
        category_name=category.name,
        confidence=classification["confidence"],
        reason=classification["reason"],
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    logger.info("Saved transaction id=%d for user=%s", transaction.id, user_id)

    history = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.id != transaction.id)
        .order_by(Transaction.created_at.desc())
        .limit(200)
        .all()
    )

    anomaly = await check_transaction_anomaly(transaction, history)
    transaction.is_anomaly = anomaly["is_anomaly"]
    transaction.anomaly_status = anomaly["anomaly_status"]
    transaction.anomaly_score = anomaly["anomaly_score"]
    transaction.anomaly_reason = anomaly["anomaly_reason"]
    transaction.ml_model_version = anomaly["ml_model_version"]
    transaction.anomaly_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(transaction)
    logger.info(
        "ML check complete — id=%d is_anomaly=%s score=%s",
        transaction.id, transaction.is_anomaly, transaction.anomaly_score,
    )

    return _to_response(transaction)


def get_transactions(user_id, db: Session) -> list[TransactionResponse]:
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return [_to_response(t) for t in transactions]


def get_transaction_by_id(transaction_id: int, user_id, db: Session) -> TransactionResponse:

    logger.info("get_transaction_by_id: transaction_id=%d user_id=%s", transaction_id, user_id)

    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == user_id)
        .first()
    )

    if transaction is None:
        logger.warning("get_transaction_by_id: transaction not found — id=%d user_id=%s", transaction_id, user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    logger.info("get_transaction_by_id: success — id=%d merchant=%s", transaction.id, transaction.merchant)
    return _to_response(transaction)


def get_dashboard(user_id, db: Session) -> DashboardResponse:
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .all()
    )

    total_expense = float(sum(t.amount for t in transactions if t.transaction_type == "expense") or 0.0)
    total_income = float(sum(t.amount for t in transactions if t.transaction_type == "income") or 0.0)

    category_totals: dict[int, dict] = {}
    for t in transactions:
        if t.transaction_type == "expense":
            if t.category_id not in category_totals:
                category_totals[t.category_id] = {"name": t.category_name, "amount": 0.0}
            category_totals[t.category_id]["amount"] += float(t.amount)

    breakdown = [
        CategoryBreakdownResponse(
            category_id=cat_id,
            category_name=data["name"],
            amount=float(round(data["amount"], 2)),
            percentage=float(round(data["amount"] / total_expense * 100, 2)) if total_expense > 0 else 0.0,
        )
        for cat_id, data in sorted(
            category_totals.items(), key=lambda x: x[1]["amount"], reverse=True
        )
    ]

    return DashboardResponse(
        total_expense=float(round(total_expense, 2)),
        total_income=float(round(total_income, 2)),
        category_breakdown=breakdown,
        recent_transactions=[_to_response(t) for t in transactions[:10]],
    )
