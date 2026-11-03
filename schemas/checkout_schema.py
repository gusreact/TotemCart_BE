from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CheckoutItemInput(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    materia_prima_ids: list[int] = Field(default_factory=list)


class CheckoutRequest(BaseModel):
    items: list[CheckoutItemInput] = Field(..., min_length=1)


class CheckoutResponse(BaseModel):
    preference_id: str
    checkout_url: str
    sandbox_checkout_url: str | None = None
    external_reference: str
    pedido_codigo: str = Field(..., pattern=r"^[A-Z0-9]{7}$")


class PedidoEstadoOut(BaseModel):
    id: int
    descripcion_es: str
    descripcion_en: str


class CheckoutOrderIngredientOut(BaseModel):
    materia_prima_id: int
    nombre_es: str | None = None
    nombre_en: str | None = None
    quantity_per_product: Decimal


class CheckoutOrderItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    ingredients: list[CheckoutOrderIngredientOut]


class CheckoutSaleOut(BaseModel):
    id: int
    external_reference: str
    pedido_codigo: str | None = None
    pedido_estado_id: int
    pedido_estado: PedidoEstadoOut
    preference_id: str | None = None
    total: Decimal
    currency: str
    payment_status: str
    payment_id: str | None = None
    payer_identification_number: str | None = None
    created_at: datetime | None = None
    paid_at: datetime | None = None
    preparation_at: datetime | None = None
    items: list[CheckoutOrderItemOut]


class CheckoutSaleStatusUpdate(BaseModel):
    pedido_estado_id: int = Field(..., gt=0)


class CheckoutSaleStatusOut(BaseModel):
    id: int
    pedido_estado_id: int
    preparation_at: datetime | None = None
    pedido_estado: PedidoEstadoOut


class CheckoutSaleByCodeItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: int


class CheckoutSaleByCodeOut(BaseModel):
    pedido_estado_id: int
    pedido_estado: PedidoEstadoOut
    preparation_at: datetime | None = None
    items: list[CheckoutSaleByCodeItemOut]
