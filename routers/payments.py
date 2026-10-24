from fastapi import APIRouter, Depends, HTTPException, Request, status

from schemas.checkout_schema import CheckoutRequest, CheckoutResponse
from services.payment_service import PaymentService


router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    service: PaymentService = Depends(),
):
    return await service.create_checkout(payload)


@router.post("/mercadopago/webhook")
async def mercadopago_webhook(
    request: Request,
    service: PaymentService = Depends(),
):
    try:
        payload = await request.json()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La notificación de pago no contiene JSON válido.",
        ) from error

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La notificación de pago tiene un formato inválido.",
        )

    event_type = (
        request.query_params.get("type")
        or request.query_params.get("topic")
        or payload.get("type")
    )
    if event_type not in {"payment", "payments"}:
        return {"received": True, "processed": False}

    event_data = payload.get("data")
    payment_id = request.query_params.get("data.id")
    if not payment_id and isinstance(event_data, dict):
        payment_id = event_data.get("id")
    payment_id = payment_id or request.query_params.get("id")
    if not payment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta el identificador del pago en la notificación.",
        )
    print(f"Webhook recibido: event_type={event_type}, payment_id={payment_id}")
    payment_id = str(payment_id)
    if not service.verify_webhook_signature(
        payment_id,
        request.headers.get("x-request-id"),
        request.headers.get("x-signature"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La firma de la notificación de pago no es válida.",
        )
    print(f"Webhook recibido para el pago {payment_id}. Procesando...")
    return await service.process_payment_notification(payment_id)
