from fastapi import APIRouter
from app.schemas.classification_schema import ClassifyRequest, ClassifyResponse
from app.services.api_service import classify_transaction

router = APIRouter()


@router.post("/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest) -> ClassifyResponse:
    result = classify_transaction(
        merchant=request.merchant,
        amount=request.amount,
        notes=request.notes,
    )
    return ClassifyResponse(**result)
