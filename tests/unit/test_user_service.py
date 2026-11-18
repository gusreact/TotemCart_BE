from unittest.mock import Mock

import pytest
from fastapi import HTTPException, status

from repositories.user_repository import UserRepository
from schemas.user_schema import UserCreate, UserUpdate
from services.user_service import UserService, pwd_context


@pytest.fixture
def repository():
    return Mock(spec=UserRepository)


def test_create_user_hashes_password_and_saves_user(repository):
    repository.exists_by_username.return_value = False
    repository.role_exists.return_value = True
    repository.create_user.return_value = {"id": 1, "username": "alice"}
    service = UserService(repository=repository)
    payload = UserCreate(
        username="alice",
        password="secret123",
        nombre="Alice",
    )

    result = service.create_user(payload)

    assert result == {"id": 1, "username": "alice"}
    saved_password_hash = repository.create_user.call_args.kwargs["password_hash"]
    assert saved_password_hash != payload.password
    assert pwd_context.verify(payload.password, saved_password_hash)
    repository.create_user.assert_called_once_with(
        username="alice",
        password_hash=saved_password_hash,
        nombre="Alice",
        role_id=2,
    )


def test_create_user_rejects_duplicate_username(repository):
    repository.exists_by_username.return_value = True
    service = UserService(repository=repository)
    payload = UserCreate(
        username="alice",
        password="secret123",
        nombre="Alice",
    )

    with pytest.raises(HTTPException) as error:
        service.create_user(payload)

    assert error.value.status_code == status.HTTP_400_BAD_REQUEST
    repository.role_exists.assert_not_called()
    repository.create_user.assert_not_called()


def test_create_user_rejects_unknown_role(repository):
    repository.exists_by_username.return_value = False
    repository.role_exists.return_value = False
    service = UserService(repository=repository)
    payload = UserCreate(
        username="alice",
        password="secret123",
        nombre="Alice",
        role_id=99,
    )

    with pytest.raises(HTTPException) as error:
        service.create_user(payload)

    assert error.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    repository.create_user.assert_not_called()


def test_update_user_hashes_new_password(repository):
    repository.get_by_id.return_value = {"id": 1, "username": "alice"}
    repository.update_user.return_value = {"id": 1, "username": "alice"}
    service = UserService(repository=repository)
    payload = UserUpdate(password="new-secret123")

    result = service.update_user(1, payload)

    assert result == {"id": 1, "username": "alice"}
    update_data = repository.update_user.call_args.args[1]
    assert update_data["password_hash"] != payload.password
    assert pwd_context.verify(payload.password, update_data["password_hash"])


def test_update_user_returns_not_found_for_unknown_user(repository):
    repository.get_by_id.return_value = None
    service = UserService(repository=repository)

    with pytest.raises(HTTPException) as error:
        service.update_user(404, UserUpdate(nombre="New name"))

    assert error.value.status_code == status.HTTP_404_NOT_FOUND
    repository.update_user.assert_not_called()
