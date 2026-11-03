import os

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

load_dotenv()

SECRET_KEY = (
    os.getenv("JWT_SECRET")
    or os.getenv("LOCAL_JWT_SECRET")
    or "super-secret-key-totem-2026"
)
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión expirada o token inválido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        role_id = payload.get("role_id")
        if username is None:
            raise credentials_exception
        if role_id is None:
            role_id = 1 if role == "admin" else 2
        try:
            role_id = int(role_id)
        except (TypeError, ValueError) as error:
            raise credentials_exception from error
        return {
            "username": username,
            "role_id": role_id,
            "role": {
                1: "admin",
                2: "cocinero",
            }.get(role_id, "user"),
        }
    except JWTError as error:
        raise credentials_exception from error


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role_id"] != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado",
        )
    return current_user


async def require_admin_or_cook(current_user: dict = Depends(get_current_user)):
    print(current_user)
    if current_user["role_id"] not in {1, 2}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado",
        )
    return current_user
