from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.transaction import ManualTransactionRequest, TransactionResponse, DashboardResponse
from app.services.transaction_service import (
    create_manual_transaction,
    get_transactions,
    get_transaction_by_id,
    get_dashboard,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/manual", response_model=TransactionResponse)
async def add_manual_transaction(
    request: ManualTransactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await create_manual_transaction(request, current_user.id, db)


@router.get("", response_model=list[TransactionResponse])
def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_transactions(current_user.id, db)


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_dashboard(current_user.id, db)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction_detail(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_transaction_by_id(transaction_id, current_user.id, db)
