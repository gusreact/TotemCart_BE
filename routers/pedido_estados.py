from fastapi import APIRouter, Depends, HTTPException, status

from schemas.pedido_estado_schema import (
    PedidoEstadoCreate,
    PedidoEstadoOut,
    PedidoEstadoUpdate,
)
from services.pedido_estado_service import PedidoEstadoService
from services.security import require_admin, require_admin_or_cook


router = APIRouter(prefix="/api/pedido-estados", tags=["pedido-estados"])


@router.get("", response_model=list[PedidoEstadoOut])
def get_pedido_estados(
    current_user: dict = Depends(require_admin_or_cook),
    service: PedidoEstadoService = Depends(),
):
    return service.get_all()


@router.get("/{estado_id}", response_model=PedidoEstadoOut)
def get_pedido_estado(
    estado_id: int,
    current_user: dict = Depends(require_admin),
    service: PedidoEstadoService = Depends(),
):
    estado = service.get_by_id(estado_id)
    if estado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estado de pedido no encontrado.",
        )
    return estado


@router.post(
    "",
    response_model=PedidoEstadoOut,
    status_code=status.HTTP_201_CREATED,
)
def create_pedido_estado(
    payload: PedidoEstadoCreate,
    current_user: dict = Depends(require_admin),
    service: PedidoEstadoService = Depends(),
):
    return service.create(payload)


@router.put("/{estado_id}", response_model=PedidoEstadoOut)
def update_pedido_estado(
    estado_id: int,
    payload: PedidoEstadoUpdate,
    current_user: dict = Depends(require_admin),
    service: PedidoEstadoService = Depends(),
):
    return service.update(estado_id, payload)


@router.delete("/{estado_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pedido_estado(
    estado_id: int,
    current_user: dict = Depends(require_admin),
    service: PedidoEstadoService = Depends(),
):
    service.delete(estado_id)
    return None
