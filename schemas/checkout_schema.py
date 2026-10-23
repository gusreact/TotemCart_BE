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
