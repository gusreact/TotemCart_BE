import asyncio
import hashlib
import hmac
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, status

from repositories.catalog_repository import CatalogRepository
from repositories.payment_repository import PaymentRepository
from repositories.pedido_estado_repository import PedidoEstadoRepository
from schemas.checkout_schema import CheckoutRequest
from services.payment_service import PaymentService


@pytest.fixture
def dependencies():
    return (
        Mock(spec=CatalogRepository),
        Mock(spec=PaymentRepository),
        Mock(spec=PedidoEstadoRepository),
    )


def test_get_sale_by_code_returns_not_found(dependencies):
    catalog, payments, states = dependencies
    payments.get_sale_by_code.return_value = None

    with pytest.raises(HTTPException) as error:
        PaymentService(catalog, payments, states).get_sale_by_code("ABC1234")

    assert error.value.status_code == status.HTTP_404_NOT_FOUND


def test_update_sale_state_validates_state(dependencies):
    catalog, payments, states = dependencies
    states.get_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        PaymentService(catalog, payments, states).update_sale_state(1, 999)

    assert error.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    payments.update_sale_state.assert_not_called()


def test_update_sale_state_returns_not_found_when_order_missing(dependencies):
    catalog, payments, states = dependencies
    states.get_by_id.return_value = {"id": 2}
    payments.update_sale_state.return_value = None

    with pytest.raises(HTTPException) as error:
        PaymentService(catalog, payments, states).update_sale_state(404, 2)

    assert error.value.status_code == status.HTTP_404_NOT_FOUND


def test_checkout_requires_valid_frontend_url(dependencies, monkeypatch):
    monkeypatch.setenv("FRONT_END_URL", "not-a-url")
    checkout = CheckoutRequest(items=[{"product_id": 1, "quantity": 1}])

    with pytest.raises(HTTPException) as error:
        asyncio.run(PaymentService(*dependencies).create_checkout(checkout))

    assert error.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    dependencies[0].get_checkout_products.assert_not_called()


def test_local_checkout_creates_order_and_records_simulated_payment(
    dependencies, monkeypatch
):
    catalog, payments, _ = dependencies
    generated_characters = iter("AAAAAAABBBBBBB")
    monkeypatch.setattr(
        "services.payment_service.secrets.choice",
        lambda _: next(generated_characters),
    )
    monkeypatch.setenv("FRONT_END_URL", "http://localhost:3000")
    monkeypatch.setenv("LOCAL_PAYMENT_SIMULATION", "true")
    monkeypatch.delenv("MERCADOPAGO_ACCESS_TOKEN", raising=False)
    catalog.get_checkout_products.return_value = [
        {
            "id": 1,
            "nombre_es": "Cafe",
            "precio": Decimal("12.50"),
            "imagen_url": "/images/cafe.webp",
            "receta_id": None,
            "tiempo_preparacion": None,
        }
    ]
    catalog.get_checkout_recipe_ingredients.return_value = []
    payments.pedido_codigo_exists.side_effect = [True, False]
    payments.record_approved_payment.return_value = True
    checkout = CheckoutRequest(items=[{"product_id": 1, "quantity": 2}])

    result = asyncio.run(PaymentService(*dependencies).create_checkout(checkout))

    assert result["preference_id"].startswith("local-")
    assert result["pedido_codigo"] == "BBBBBBB"
    assert [
        call.args[0] for call in payments.pedido_codigo_exists.call_args_list
    ] == ["AAAAAAA", "BBBBBBB"]
    payments.create_pending_order.assert_called_once()
    order_args = payments.create_pending_order.call_args.args
    assert order_args[1] == "BBBBBBB"
    assert order_args[2] == Decimal("25.00")
    assert order_args[3] == 3
    payments.record_approved_payment.assert_called_once()
    assert result["checkout_url"].startswith("http://localhost:3000/success?")


def test_checkout_rejects_unavailable_products(dependencies, monkeypatch):
    monkeypatch.setenv("FRONT_END_URL", "http://localhost:3000")
    monkeypatch.setenv("LOCAL_PAYMENT_SIMULATION", "true")
    dependencies[0].get_checkout_products.return_value = []
    checkout = CheckoutRequest(items=[{"product_id": 1, "quantity": 1}])

    with pytest.raises(HTTPException) as error:
        asyncio.run(PaymentService(*dependencies).create_checkout(checkout))

    assert error.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    dependencies[1].create_pending_order.assert_not_called()


def test_checkout_rejects_missing_required_recipe_ingredient(
    dependencies, monkeypatch
):
    monkeypatch.setenv("FRONT_END_URL", "http://localhost:3000")
    monkeypatch.setenv("LOCAL_PAYMENT_SIMULATION", "true")
    dependencies[0].get_checkout_products.return_value = [
        {
            "id": 1,
            "nombre_es": "Cafe",
            "precio": Decimal("12.50"),
            "imagen_url": None,
            "receta_id": 10,
            "tiempo_preparacion": 5,
        }
    ]
    dependencies[0].get_checkout_recipe_ingredients.return_value = [
        {"receta_id": 10, "materia_prima_id": 30, "requerido": True}
    ]
    checkout = CheckoutRequest(items=[{"product_id": 1, "quantity": 1}])

    with pytest.raises(HTTPException) as error:
        asyncio.run(PaymentService(*dependencies).create_checkout(checkout))

    assert error.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    dependencies[1].create_pending_order.assert_not_called()


def test_verify_webhook_signature_accepts_correct_signature(monkeypatch):
    secret = "test-webhook-secret"
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", secret)
    manifest = "id:abc123;request-id:request-1;ts:123456;"
    signature = hmac.new(
        secret.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()

    valid = PaymentService.verify_webhook_signature(
        "ABC123", "request-1", f"ts=123456,v1={signature}"
    )

    assert valid is True


def test_verify_webhook_signature_rejects_wrong_signature(monkeypatch):
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "test-webhook-secret")

    valid = PaymentService.verify_webhook_signature(
        "ABC123", "request-1", "ts=123456,v1=invalid"
    )

    assert valid is False
