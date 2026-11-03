from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    nombre_es: str = Field(..., min_length=1, max_length=100)
    nombre_en: str = Field(..., min_length=1, max_length=100)


class RoleUpdate(BaseModel):
    nombre_es: str | None = Field(default=None, min_length=1, max_length=100)
    nombre_en: str | None = Field(default=None, min_length=1, max_length=100)


class RoleOut(RoleCreate):
    id: int
    inmutable: bool
