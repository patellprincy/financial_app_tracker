import logging
from sqlalchemy.orm import Session
from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.transaction import (
    ManualTransactionRequest,
    TransactionResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
)
from app.services.classification_client import classify_transaction

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
    classification = await classify_transaction(
        merchant=request.merchant,
        amount=request.amount,
        notes=request.notes or None,
    )
    logger.info(
        "AI classified %r → %s / %s (confidence=%.2f)",
        request.merchant,
        classification["transaction_type"],
        classification["category_name"],
        classification["confidence"],
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
        amount=request.amount,
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

    return _to_response(transaction)


def get_transactions(user_id, db: Session) -> list[TransactionResponse]:
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return [_to_response(t) for t in transactions]


def get_dashboard(user_id, db: Session) -> DashboardResponse:
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .all()
    )

    total_expense = sum(t.amount for t in transactions if t.transaction_type == "expense")
    total_income = sum(t.amount for t in transactions if t.transaction_type == "income")

    category_totals: dict[int, dict] = {}
    for t in transactions:
        if t.transaction_type == "expense":
            if t.category_id not in category_totals:
                category_totals[t.category_id] = {"name": t.category_name, "amount": 0.0}
            category_totals[t.category_id]["amount"] += t.amount

    breakdown = [
        CategoryBreakdownResponse(
            category_id=cat_id,
            category_name=data["name"],
            amount=round(data["amount"], 2),
            percentage=round(data["amount"] / total_expense * 100, 2) if total_expense > 0 else 0.0,
        )
        for cat_id, data in sorted(
            category_totals.items(), key=lambda x: x[1]["amount"], reverse=True
        )
    ]

    return DashboardResponse(
        total_expense=round(total_expense, 2),
        total_income=round(total_income, 2),
        category_breakdown=breakdown,
        recent_transactions=[_to_response(t) for t in transactions[:10]],
    )
