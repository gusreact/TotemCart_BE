from unittest.mock import Mock

import pytest

import main
from repositories.user_repository import UserRepository
from schemas.user_schema import UserCreate


def test_ensure_initial_admin_skips_when_users_exist(monkeypatch):
    repository = Mock(spec=UserRepository)
    repository.has_any_users.return_value = True
    user_service = Mock()
    monkeypatch.setattr(main, "UserRepository", lambda: repository)
    monkeypatch.setattr(main, "UserService", lambda repository: user_service)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)

    main.ensure_initial_admin()

    user_service.create_user.assert_not_called()


def test_ensure_initial_admin_uses_user_service(monkeypatch):
    repository = Mock(spec=UserRepository)
    repository.has_any_users.return_value = False
    user_service = Mock()
    monkeypatch.setattr(main, "UserRepository", lambda: repository)
    monkeypatch.setattr(main, "UserService", lambda repository: user_service)
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "configured-test-password")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_NAME", "Administrator")

    main.ensure_initial_admin()

    payload = user_service.create_user.call_args.args[0]
    assert payload == UserCreate(
        username="admin",
        password="configured-test-password",
        nombre="Administrator",
        role_id=1,
    )


def test_ensure_initial_admin_requires_password_when_users_table_empty(monkeypatch):
    repository = Mock(spec=UserRepository)
    repository.has_any_users.return_value = False
    monkeypatch.setattr(main, "UserRepository", lambda: repository)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_PASSWORD"):
        main.ensure_initial_admin()
