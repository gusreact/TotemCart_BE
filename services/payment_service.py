import logging
import os
from uuid import uuid4
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, status

from repositories.catalog_repository import CatalogRepository
from schemas.checkout_schema import CheckoutRequest


logger = logging.getLogger(__name__)
MERCADO_PAGO_PREFERENCES_URL = (
    "https://api.mercadopago.com/checkout/preferences"
)


class PaymentService:
    def __init__(self, repository: CatalogRepository = Depends()):
        self.repository = repository

    async def create_checkout(self, checkout: CheckoutRequest):
        access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip()
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MERCADOPAGO_ACCESS_TOKEN no está configurada.",
            )

        frontend_url = os.getenv("FRONT_END_URL", "").strip().rstrip("/")
        parsed_frontend_url = urlparse(frontend_url)
        if parsed_frontend_url.scheme not in {"http", "https"} or not parsed_frontend_url.netloc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="FRONT_END_URL debe ser una URL absoluta HTTP o HTTPS.",
            )

        quantities = {}
        for item in checkout.items:
            quantities[item.product_id] = (
                quantities.get(item.product_id, 0) + item.quantity
            )

        products = self.repository.get_checkout_products(list(quantities))
        products_by_id = {product["id"]: product for product in products}
        if len(products_by_id) != len(quantities):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uno o más productos no existen o no están disponibles.",
            )

        preference_items = []
        for product_id, quantity in quantities.items():
            product = products_by_id[product_id]
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

        external_reference = str(uuid4())
        preference = {
            "items": preference_items,
            "back_urls": {
                "success": f"{frontend_url}/success",
                "failure": f"{frontend_url}/failure",
                "pending": f"{frontend_url}/pending",
            },
            "auto_return": "approved",
            "external_reference": external_reference,
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
                detail="Mercado Pago rechazó la creación del pago."+error.response.text,
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

        return {
            "preference_id": str(preference_id),
            "checkout_url": checkout_url,
            "sandbox_checkout_url": result.get("sandbox_init_point"),
            "external_reference": external_reference,
        }
