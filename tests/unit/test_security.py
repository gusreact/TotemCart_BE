import asyncio

import pytest
from fastapi import HTTPException, status
from jose import jwt

from services.security import (
    ALGORITHM,
    SECRET_KEY,
    get_current_user,
    require_admin,
    require_admin_or_cook,
)


def make_token(payload):
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def test_get_current_user_decodes_user_and_role():
    token = make_token({"sub": "alice", "role_id": 1})

    user = asyncio.run(get_current_user(token))

    assert user == {"username": "alice", "role_id": 1, "role": "admin"}


def test_get_current_user_supports_legacy_role_claim():
    token = make_token({"sub": "alice", "role": "admin"})

    user = asyncio.run(get_current_user(token))

    assert user["role_id"] == 1
    assert user["role"] == "admin"


@pytest.mark.parametrize("token", ["not-a-token", make_token({"role_id": 1})])
def test_get_current_user_rejects_invalid_or_incomplete_token(token):
    with pytest.raises(HTTPException) as error:
        asyncio.run(get_current_user(token))

    assert error.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_require_admin_rejects_non_admin_user():
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_admin({"username": "cook", "role_id": 2}))

    assert error.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("role_id", [1, 2])
def test_require_admin_or_cook_accepts_admin_and_cook(role_id):
    user = {"username": "staff", "role_id": role_id}

    assert asyncio.run(require_admin_or_cook(user)) == user


def test_require_admin_or_cook_rejects_other_roles():
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_admin_or_cook({"username": "guest", "role_id": 3}))

    assert error.value.status_code == status.HTTP_403_FORBIDDEN
