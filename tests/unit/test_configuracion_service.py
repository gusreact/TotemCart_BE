from unittest.mock import Mock

import pytest
from fastapi import HTTPException, status

from repositories.configuracion_repository import ConfiguracionRepository
from schemas.configuracion_schema import ConfiguracionCreate, ConfiguracionUpdate
from services.configuracion_service import ConfiguracionService


def test_configuracion_create_passes_key_and_value_to_repository():
    repository = Mock(spec=ConfiguracionRepository)
    configuracion = {"clave": "moneda", "valor": "ARS"}
    repository.create.return_value = configuracion

    result = ConfiguracionService(repository=repository).create(
        ConfiguracionCreate(clave="moneda", valor="ARS")
    )

    assert result == configuracion
    repository.create.assert_called_once_with("moneda", "ARS")


def test_configuracion_create_rejects_duplicate_key():
    repository = Mock(spec=ConfiguracionRepository)
    repository.create.return_value = None

    with pytest.raises(HTTPException) as error:
        ConfiguracionService(repository=repository).create(
            ConfiguracionCreate(clave="moneda", valor="ARS")
        )

    assert error.value.status_code == status.HTTP_409_CONFLICT


def test_configuracion_update_returns_not_found_for_missing_key():
    repository = Mock(spec=ConfiguracionRepository)
    repository.update.return_value = None

    with pytest.raises(HTTPException) as error:
        ConfiguracionService(repository=repository).update(
            "inexistente", ConfiguracionUpdate(valor="valor")
        )

    assert error.value.status_code == status.HTTP_404_NOT_FOUND


def test_configuracion_delete_returns_not_found_for_missing_key():
    repository = Mock(spec=ConfiguracionRepository)
    repository.delete.return_value = False

    with pytest.raises(HTTPException) as error:
        ConfiguracionService(repository=repository).delete("inexistente")

    assert error.value.status_code == status.HTTP_404_NOT_FOUND
