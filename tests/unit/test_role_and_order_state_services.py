from unittest.mock import Mock

import psycopg2
import pytest
from fastapi import HTTPException, status

from repositories.pedido_estado_repository import PedidoEstadoRepository
from repositories.role_repository import RoleRepository
from schemas.pedido_estado_schema import PedidoEstadoCreate, PedidoEstadoUpdate
from schemas.role_schema import RoleCreate, RoleUpdate
from services.pedido_estado_service import PedidoEstadoService
from services.role_service import RoleService


def test_role_create_passes_descriptions_to_repository():
    repository = Mock(spec=RoleRepository)
    repository.create.return_value = {"id": 3}

    result = RoleService(repository=repository).create(
        RoleCreate(nombre_es="Cocinero", nombre_en="Cook")
    )

    assert result == {"id": 3}
    repository.create.assert_called_once_with("Cocinero", "Cook")


def test_role_update_returns_not_found_for_missing_role():
    repository = Mock(spec=RoleRepository)
    repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        RoleService(repository=repository).update(42, RoleUpdate(nombre_es="Nuevo"))

    assert error.value.status_code == status.HTTP_404_NOT_FOUND
    repository.update.assert_not_called()


def test_role_update_with_empty_payload_returns_current_role():
    repository = Mock(spec=RoleRepository)
    role = {"id": 2, "nombre_es": "Cook", "inmutable": True}
    repository.get_by_id.return_value = role

    result = RoleService(repository=repository).update(2, RoleUpdate())

    assert result == role
    assert repository.get_by_id.call_count == 2
    repository.update.assert_not_called()


def test_role_delete_rejects_immutable_role():
    repository = Mock(spec=RoleRepository)
    repository.get_by_id.return_value = {"id": 1, "inmutable": True}

    with pytest.raises(HTTPException) as error:
        RoleService(repository=repository).delete(1)

    assert error.value.status_code == status.HTTP_409_CONFLICT
    repository.delete.assert_not_called()


def test_role_delete_maps_foreign_key_violation():
    repository = Mock(spec=RoleRepository)
    repository.get_by_id.return_value = {"id": 3, "inmutable": False}
    repository.delete.side_effect = psycopg2.errors.ForeignKeyViolation()

    with pytest.raises(HTTPException) as error:
        RoleService(repository=repository).delete(3)

    assert error.value.status_code == status.HTTP_409_CONFLICT


def test_pedido_estado_create_uses_database_generated_id():
    repository = Mock(spec=PedidoEstadoRepository)
    repository.create.return_value = {"id": 6}

    result = PedidoEstadoService(repository=repository).create(
        PedidoEstadoCreate(descripcion_es="Nuevo", descripcion_en="New")
    )

    assert result == {"id": 6}
    repository.create.assert_called_once_with("Nuevo", "New")


def test_pedido_estado_update_returns_not_found_for_missing_state():
    repository = Mock(spec=PedidoEstadoRepository)
    repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        PedidoEstadoService(repository=repository).update(
            99, PedidoEstadoUpdate(descripcion_es="Nuevo")
        )

    assert error.value.status_code == status.HTTP_404_NOT_FOUND
    repository.update.assert_not_called()


def test_pedido_estado_delete_maps_foreign_key_violation():
    repository = Mock(spec=PedidoEstadoRepository)
    repository.get_by_id.return_value = {"id": 1}
    repository.delete.side_effect = psycopg2.errors.ForeignKeyViolation()

    with pytest.raises(HTTPException) as error:
        PedidoEstadoService(repository=repository).delete(1)

    assert error.value.status_code == status.HTTP_409_CONFLICT

