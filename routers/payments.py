from fastapi import APIRouter, Depends

from schemas.checkout_schema import CheckoutRequest, CheckoutResponse
from services.payment_service import PaymentService


router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    service: PaymentService = Depends(),
):
    return await service.create_checkout(payload)
