from fastapi import Depends, HTTPException, status
from passlib.context import CryptContext

from repositories.user_repository import UserRepository
from schemas.user_schema import UserCreate, UserUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    def __init__(self, repository: UserRepository = Depends()):
        self.repository = repository

    def get_all_users(self):
        return self.repository.get_all_users()

    def create_user(self, payload: UserCreate):
        if self.repository.exists_by_username(payload.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario ya existe",
            )

        password_hash = pwd_context.hash(payload.password)
        return self.repository.create_user(
            username=payload.username,
            password_hash=password_hash,
            nombre=payload.nombre,
            role=payload.role,
        )

    def update_user(self, user_id: int, payload: UserUpdate):
        existing_user = self.repository.get_by_id(user_id)
        if existing_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        update_data = {}

        if payload.username is not None:
            if payload.username != existing_user["username"] and self.repository.exists_by_username(payload.username):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El username ya existe",
                )
            update_data["username"] = payload.username

        if payload.nombre is not None:
            update_data["nombre"] = payload.nombre

        if payload.role is not None:
            update_data["role"] = payload.role

        if payload.password is not None:
            update_data["password_hash"] = pwd_context.hash(payload.password)

        if not update_data:
            return existing_user

        return self.repository.update_user(user_id, update_data)

    def delete_user(self, user_id: int):
        existing_user = self.repository.get_by_id(user_id)
        if existing_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        self.repository.delete_user(user_id)
        return None
