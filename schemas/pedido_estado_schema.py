from pydantic import BaseModel, Field


class PedidoEstadoCreate(BaseModel):
    descripcion_es: str = Field(..., min_length=1, max_length=50)
    descripcion_en: str = Field(..., min_length=1, max_length=50)


class PedidoEstadoUpdate(BaseModel):
    descripcion_es: str | None = Field(default=None, min_length=1, max_length=50)
    descripcion_en: str | None = Field(default=None, min_length=1, max_length=50)


class PedidoEstadoOut(BaseModel):
    id: int
    descripcion_es: str
    descripcion_en: str
