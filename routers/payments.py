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


@router.post("/mercadopago/webhook2")
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

@router.post("/mercadopago/webhook")
async def mercadopago_webhook(request: Request, service: PaymentService = Depends()):
    # Parse JSON only if present; signature validation does not depend on the body
    payload = {}
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    # Detect request type
    data_id = request.query_params.get("data.id")  # Webhooks
    topic = request.query_params.get("topic")      # IPN
    ipn_id = request.query_params.get("id")        # IPN

    x_request_id = request.headers.get("x-request-id")
    x_signature = request.headers.get("x-signature")

    print(f"Webhook recibido: topic={topic}, data_id={data_id}, ipn_id={ipn_id}, x_request_id={x_request_id}, x_signature={x_signature}")
    # --- Webhooks path (validate HMAC) ---
    if data_id and x_request_id and x_signature:
        if not service.verify_webhook_signature(data_id, x_request_id, x_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
        # process using data_id (it’s the payment id for type=payment)
        return await service.process_payment_notification(str(data_id))

    # --- IPN path (NO HMAC secret validation) ---
    if topic in {"payment", "payments"} and ipn_id:
        # process using ipn_id (payment id)
        return await service.process_payment_notification(str(ipn_id))

    # Ignore other topics (e.g. merchant_order) or handle them separately
    return {"received": True, "processed": False}