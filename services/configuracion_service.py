from fastapi import Depends, HTTPException, status

from repositories.configuracion_repository import ConfiguracionRepository
from schemas.configuracion_schema import ConfiguracionCreate, ConfiguracionUpdate


class ConfiguracionService:
    def __init__(self, repository: ConfiguracionRepository = Depends()):
        self.repository = repository

    def get_all(self):
        return self.repository.get_all()

    def get_by_clave(self, clave: str):
        return self.repository.get_by_clave(clave)

    def create(self, payload: ConfiguracionCreate):
        configuracion = self.repository.create(payload.clave, payload.valor)
        if configuracion is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una configuración con esa clave.",
            )
        return configuracion

    def update(self, clave: str, payload: ConfiguracionUpdate):
        configuracion = self.repository.update(clave, payload.valor)
        if configuracion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Configuración no encontrada.",
            )
        return configuracion

    def delete(self, clave: str):
        if not self.repository.delete(clave):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Configuración no encontrada.",
            )
