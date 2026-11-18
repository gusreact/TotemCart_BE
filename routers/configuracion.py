from fastapi import APIRouter, Depends, HTTPException, status

from schemas.configuracion_schema import (
    ConfiguracionCreate,
    ConfiguracionOut,
    ConfiguracionUpdate,
)
from services.configuracion_service import ConfiguracionService
from services.security import require_admin


router = APIRouter(prefix="/api/configuracion", tags=["configuracion"])


@router.get("", response_model=list[ConfiguracionOut])
def get_configuraciones(
    current_user: dict = Depends(require_admin),
    service: ConfiguracionService = Depends(),
):
    return service.get_all()


@router.get("/{clave}", response_model=ConfiguracionOut)
def get_configuracion(
    clave: str,
    service: ConfiguracionService = Depends(),
):
    configuracion = service.get_by_clave(clave)
    if configuracion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuración no encontrada.",
        )
    return configuracion


@router.post(
    "",
    response_model=ConfiguracionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_configuracion(
    payload: ConfiguracionCreate,
    current_user: dict = Depends(require_admin),
    service: ConfiguracionService = Depends(),
):
    return service.create(payload)


@router.put("/{clave}", response_model=ConfiguracionOut)
def update_configuracion(
    clave: str,
    payload: ConfiguracionUpdate,
    current_user: dict = Depends(require_admin),
    service: ConfiguracionService = Depends(),
):
    return service.update(clave, payload)


@router.delete("/{clave}", status_code=status.HTTP_204_NO_CONTENT)
def delete_configuracion(
    clave: str,
    current_user: dict = Depends(require_admin),
    service: ConfiguracionService = Depends(),
):
    service.delete(clave)
    return None
