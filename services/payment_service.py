import hashlib
import hmac
import ipaddress
import logging
import os
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, status

from repositories.catalog_repository import CatalogRepository
from repositories.payment_repository import PaymentRepository
from schemas.checkout_schema import CheckoutRequest


logger = logging.getLogger(__name__)
MERCADO_PAGO_PREFERENCES_URL = (
    "https://api.mercadopago.com/checkout/preferences"
)
MERCADO_PAGO_PAYMENT_URL = "https://api.mercadopago.com/v1/payments"


class PaymentService:
    def __init__(
        self,
        repository: CatalogRepository = Depends(),
        payment_repository: PaymentRepository = Depends(),
    ):
        self.repository = repository
        self.payment_repository = payment_repository

    @staticmethod
    def _is_loopback_host(hostname: str | None) -> bool:
        if not hostname:
            return False
        normalized_hostname = hostname.lower().rstrip(".")
        if normalized_hostname == "localhost" or normalized_hostname.endswith(
            ".localhost"
        ):
            return True
        try:
            return ipaddress.ip_address(normalized_hostname).is_loopback
        except ValueError:
            return False

    async def create_checkout(self, checkout: CheckoutRequest):
        frontend_url = os.getenv("FRONT_END_URL", "").strip().rstrip("/")
        parsed_frontend_url = urlparse(frontend_url)
        if (
            parsed_frontend_url.scheme not in {"http", "https"}
            or not parsed_frontend_url.netloc
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="FRONT_END_URL debe ser una URL absoluta HTTP o HTTPS.",
            )

        local_payment_simulation = (
            os.getenv("LOCAL_PAYMENT_SIMULATION", "").strip().lower() == "true"
            and self._is_loopback_host(parsed_frontend_url.hostname)
        )
        access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip()
        if not local_payment_simulation and not access_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MERCADOPAGO_ACCESS_TOKEN no está configurada.",
            )

        backend_url = ""
        if not local_payment_simulation:
            backend_url = os.getenv("BACKEND_PUBLIC_URL", "").strip().rstrip("/")
            parsed_backend_url = urlparse(backend_url)
            if (
                parsed_backend_url.scheme != "https"
                or not parsed_backend_url.netloc
            ):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="BACKEND_PUBLIC_URL debe ser una URL pública HTTPS.",
                )

        product_ids = set()
        for item in checkout.items:
            product_ids.add(item.product_id)

        products = self.repository.get_checkout_products(list(product_ids))
        products_by_id = {product["id"]: product for product in products}
        if len(products_by_id) != len(product_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uno o más productos no existen o no están disponibles.",
            )

        recipe_ids = list(
            {
                product["receta_id"]
                for product in products
                if product["receta_id"] is not None
            }
        )
        recipe_ingredients = self.repository.get_checkout_recipe_ingredients(
            recipe_ids
        )
        ingredients_by_recipe = {}
        for ingredient in recipe_ingredients:
            ingredients_by_recipe.setdefault(ingredient["receta_id"], []).append(
                ingredient
            )

        preference_items = []
        order_items = []
        total = Decimal("0.00")
        for checkout_item in checkout.items:
            product = products_by_id[checkout_item.product_id]
            quantity = checkout_item.quantity
            selected_ids = checkout_item.materia_prima_ids
            if len(selected_ids) != len(set(selected_ids)):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No se puede repetir una materia prima seleccionada.",
                )

            recipe_id = product["receta_id"]
            recipe_ingredients_for_product = ingredients_by_recipe.get(recipe_id, [])
            recipe_ingredients_by_id = {
                ingredient["materia_prima_id"]: ingredient
                for ingredient in recipe_ingredients_for_product
            }
            selected_id_set = set(selected_ids)
            if recipe_id is None and selected_id_set:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No se pueden seleccionar materias primas para un producto sin receta.",
                )
            if not selected_id_set.issubset(recipe_ingredients_by_id):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Una materia prima seleccionada no pertenece a la receta del producto.",
                )

            required_ids = {
                ingredient_id
                for ingredient_id, ingredient in recipe_ingredients_by_id.items()
                if ingredient["requerido"]
            }
            if not required_ids.issubset(selected_id_set):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="La selección debe incluir todas las materias primas requeridas.",
                )

            selected_ingredients = [
                recipe_ingredients_by_id[ingredient_id]
                for ingredient_id in selected_ids
            ]

            total += product["precio"] * quantity
            item = {
                "id": str(product["id"]),
                "title": product["nombre_es"],
                "quantity": quantity,
                "currency_id": "ARS",
                "unit_price": float(product["precio"]),
            }
            image_url = product.get("imagen_url")
            parsed_image_url = urlparse(image_url or "")
            if (
                parsed_image_url.scheme in {"http", "https"}
                and parsed_image_url.netloc
            ):
                item["picture_url"] = image_url
            preference_items.append(item)
            order_items.append(
                {
                    "id": product["id"],
                    "nombre_es": product["nombre_es"],
                    "precio": product["precio"],
                    "quantity": quantity,
                    "ingredients": selected_ingredients,
                }
            )

        external_reference = str(uuid4())
        self.payment_repository.create_pending_order(
            external_reference,
            total,
            order_items,
        )
        if local_payment_simulation:
            local_payment_id = f"local-{external_reference}"
            recorded = self.payment_repository.record_approved_payment(
                external_reference,
                local_payment_id,
            )
            if not recorded:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No se pudo registrar el pago simulado local.",
                )
            logger.warning(
                "Simulated a successful local checkout and inventory deduction."
            )
            return {
                "preference_id": local_payment_id,
                "checkout_url": f"{frontend_url}/success",
                "sandbox_checkout_url": None,
                "external_reference": external_reference,
            }

        preference = {
            "items": preference_items,
            "back_urls": {
                "success": f"{frontend_url}/success",
                "failure": f"{frontend_url}/failure",
                "pending": f"{frontend_url}/pending",
            },
            "auto_return": "approved",
            "external_reference": external_reference,
            "notification_url": (
                f"{backend_url}/api/payments/mercadopago/webhook"
            ),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    MERCADO_PAGO_PREFERENCES_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=preference,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            logger.error(
                "Mercado Pago rejected preference creation with status %s",
                error.response.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Mercado Pago rechazó la creación del pago.",
            ) from error
        except httpx.RequestError as error:
            logger.exception("Could not reach Mercado Pago to create preference.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo conectar con Mercado Pago.",
            ) from error

        try:
            result = response.json()
            preference_id = result["id"]
            checkout_url = result["init_point"]
        except (ValueError, KeyError, TypeError) as error:
            logger.error("Mercado Pago returned an invalid preference response.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Mercado Pago devolvió una respuesta de pago inválida.",
            ) from error

        self.payment_repository.set_order_preference(
            external_reference,
            str(preference_id),
        )
        return {
            "preference_id": str(preference_id),
            "checkout_url": checkout_url,
            "sandbox_checkout_url": result.get("sandbox_init_point"),
            "external_reference": external_reference,
        }

    @staticmethod
    def verify_webhook_signature2(
        payment_id: str,
        request_id: str | None,
        signature: str | None,
    ) -> bool:
        secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
        print(f"verify_webhook_signature: payment_id={payment_id}, request_id={request_id}, signature={signature}, secret={'set' if secret else 'not set'}")
        if not secret or not request_id or not signature:
            return False

        signature_parts = {}
        for part in signature.split(","):
            key, separator, value = part.strip().partition("=")
            if separator:
                signature_parts[key] = value
        timestamp = signature_parts.get("ts")
        received_signature = signature_parts.get("v1")
        print(f"verify_webhook_signature: timestamp={timestamp}, received_signature={received_signature}")
        if not timestamp or not received_signature:
            return False

        manifest = f"id:{payment_id};request-id:{request_id};ts:{timestamp};"
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            manifest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        print(f"verify_webhook_signature: expected_signature={expected_signature}, received_signature={received_signature}")
        return hmac.compare_digest(expected_signature, received_signature)



    def verify_webhook_signature(data_id: str, x_request_id: str, x_signature: str) -> bool:
        secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
        if not (data_id and x_request_id and x_signature and secret):
            return False

        parts = {}
        for part in x_signature.split(","):
            k, _, v = part.strip().partition("=")
            if _:
                parts[k] = v

        ts = parts.get("ts")
        v1 = parts.get("v1")
        if not (ts and v1):
            return False

        # Required by docs when data.id is alphanumeric and uppercase
        if any(c.isalpha() for c in data_id):
            data_id = data_id.lower()

        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, v1)

    async def process_payment_notification(self, payment_id: str):
        access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip()
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MERCADOPAGO_ACCESS_TOKEN no está configurada.",
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{MERCADO_PAGO_PAYMENT_URL}/{payment_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            logger.error(
                "Mercado Pago payment lookup failed with status %s",
                error.response.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo verificar el pago con Mercado Pago.",
            ) from error
        except httpx.RequestError as error:
            logger.exception("Could not reach Mercado Pago to verify payment.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo conectar con Mercado Pago para verificar el pago.",
            ) from error

        try:
            payment = response.json()
            external_reference = payment["external_reference"]
            status_value = payment["status"]
            currency = payment["currency_id"]
            verified_payment_id = str(payment["id"])
            amount = Decimal(str(payment["transaction_amount"])).quantize(
                Decimal("0.01")
            )
            payer = payment.get("payer")
            if not isinstance(payer, dict):
                payer = {}
            identification = payer.get("identification")
            if not isinstance(identification, dict):
                identification = {}

            def optional_payer_value(value):
                if not isinstance(value, str):
                    return None
                value = value.strip()
                return value or None

            payer_first_name = optional_payer_value(payer.get("first_name"))
            payer_last_name = optional_payer_value(payer.get("last_name"))
            payer_identification_number = optional_payer_value(
                identification.get("number")
            )
        except (ValueError, KeyError, TypeError, InvalidOperation) as error:
            logger.error("Mercado Pago returned an invalid payment response.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Mercado Pago devolvió una respuesta de pago inválida.",
            ) from error

        if status_value != "approved":
            return {"received": True, "processed": False, "status": status_value}

        order = self.payment_repository.get_order_by_external_reference(
            external_reference
        )
        if order is None:
            logger.warning(
                "Approved Mercado Pago payment has no matching checkout order."
            )
            return {"received": True, "processed": False}
        if currency != order["currency"] or amount != order["total"]:
            logger.error(
                "Approved Mercado Pago payment does not match its checkout order."
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El pago aprobado no coincide con la orden.",
            )
        print("process_payment_notification: ",external_reference, verified_payment_id, payer_first_name, payer_last_name, payer_identification_number)
        recorded = self.payment_repository.record_approved_payment(
            external_reference,
            verified_payment_id,
            payer_first_name,
            payer_last_name,
            payer_identification_number,
        )
        return {"received": True, "processed": recorded}
