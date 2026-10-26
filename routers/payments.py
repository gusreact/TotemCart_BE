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