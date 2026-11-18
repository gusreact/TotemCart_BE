from fastapi import Depends, HTTPException, status
from psycopg2.errors import ForeignKeyViolation

from repositories.role_repository import RoleRepository
from schemas.role_schema import RoleCreate, RoleUpdate


class RoleService:
    def __init__(self, repository: RoleRepository = Depends()):
        self.repository = repository

    def get_all(self):
        return self.repository.get_all()

    def get_by_id(self, role_id: int):
        return self.repository.get_by_id(role_id)

    def create(self, payload: RoleCreate):
        return self.repository.create(payload.nombre_es, payload.nombre_en)

    def update(self, role_id: int, payload: RoleUpdate):
        if self.repository.get_by_id(role_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rol no encontrado",
            )
        values = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not values:
            return self.repository.get_by_id(role_id)
        return self.repository.update(role_id, values)

    def delete(self, role_id: int):
        role = self.repository.get_by_id(role_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rol no encontrado",
            )
        if role["inmutable"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar un rol inmutable.",
            )
        try:
            if not self.repository.delete(role_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No se puede eliminar un rol inmutable.",
                )
        except Exception as error:
            if isinstance(error, ForeignKeyViolation):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No se puede eliminar un rol asignado a usuarios.",
                ) from error
            raise
