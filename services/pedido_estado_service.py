from fastapi import Depends, HTTPException, status
from psycopg2.errors import ForeignKeyViolation, UniqueViolation

from repositories.pedido_estado_repository import PedidoEstadoRepository
from schemas.pedido_estado_schema import PedidoEstadoCreate, PedidoEstadoUpdate


class PedidoEstadoService:
    def __init__(self, repository: PedidoEstadoRepository = Depends()):
        self.repository = repository

    def get_all(self):
        return self.repository.get_all()

    def get_by_id(self, estado_id: int):
        return self.repository.get_by_id(estado_id)

    def create(self, payload: PedidoEstadoCreate):
        try:
            return self.repository.create(
                payload.descripcion_es,
                payload.descripcion_en,
            )
        except UniqueViolation as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un estado de pedido con ese ID.",
            ) from error

    def update(self, estado_id: int, payload: PedidoEstadoUpdate):
        if self.repository.get_by_id(estado_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estado de pedido no encontrado.",
            )
        values = payload.dict(exclude_unset=True, exclude_none=True)
        if not values:
            return self.repository.get_by_id(estado_id)
        return self.repository.update(estado_id, values)

    def delete(self, estado_id: int):
        if self.repository.get_by_id(estado_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estado de pedido no encontrado.",
            )
        try:
            deleted = self.repository.delete(estado_id)
        except ForeignKeyViolation as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar un estado asignado a pedidos.",
            ) from error
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estado de pedido no encontrado.",
            )
