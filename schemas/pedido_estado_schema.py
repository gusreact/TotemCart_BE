from pydantic import BaseModel, Field


class PedidoEstadoCreate(BaseModel):
    id: int = Field(..., ge=1, le=5)
    descripcion_es: str = Field(..., min_length=1, max_length=50)
    descripcion_en: str = Field(..., min_length=1, max_length=50)


class PedidoEstadoUpdate(BaseModel):
    descripcion_es: str | None = Field(default=None, min_length=1, max_length=50)
    descripcion_en: str | None = Field(default=None, min_length=1, max_length=50)


class PedidoEstadoOut(PedidoEstadoCreate):
    pass
