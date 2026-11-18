import pytest
from pydantic import ValidationError

from schemas.catalog_schema import ProductoCreate
from schemas.checkout_schema import CheckoutItemInput, CheckoutRequest
from schemas.pedido_estado_schema import PedidoEstadoCreate
from schemas.role_schema import RoleCreate
from schemas.user_schema import UserCreate


def test_user_create_applies_default_role():
    payload = UserCreate(username="alice", password="secret123", nombre="Alice")

    assert payload.role_id == 2


def test_user_create_rejects_short_username():
    with pytest.raises(ValidationError):
        UserCreate(username="ab", password="secret123", nombre="Alice")


def test_checkout_request_requires_at_least_one_item():
    with pytest.raises(ValidationError):
        CheckoutRequest(items=[])


@pytest.mark.parametrize(
    "values",
    [
        {"product_id": 0, "quantity": 1},
        {"product_id": 1, "quantity": 0},
    ],
)
def test_checkout_item_requires_positive_ids_and_quantity(values):
    with pytest.raises(ValidationError):
        CheckoutItemInput(**values)


def test_product_suggested_category_is_nullable():
    product = ProductoCreate(
        categoria_id=1,
        nombre_es="Cafe",
        nombre_en="Coffee",
        precio="2.50",
    )

    assert product.categoria_sugerida is None


def test_product_suggested_category_must_be_positive_when_present():
    with pytest.raises(ValidationError):
        ProductoCreate(
            categoria_id=1,
            categoria_sugerida=0,
            nombre_es="Cafe",
            nombre_en="Coffee",
            precio="2.50",
        )


def test_pedido_estado_create_does_not_require_client_id():
    state = PedidoEstadoCreate(descripcion_es="Nuevo", descripcion_en="New")

    assert not hasattr(state, "id")


def test_role_create_requires_both_translations():
    with pytest.raises(ValidationError):
        RoleCreate(nombre_es="Administrador")
