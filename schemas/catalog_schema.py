from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CategoriaCreate(BaseModel):
    nombre_es: str = Field(..., min_length=1, max_length=100)
    nombre_en: str = Field(..., min_length=1, max_length=100)
    orden: int = Field(default=1, ge=1)


class CategoriaUpdate(BaseModel):
    nombre_es: Optional[str] = Field(default=None, min_length=1, max_length=100)
    nombre_en: Optional[str] = Field(default=None, min_length=1, max_length=100)
    orden: Optional[int] = Field(default=None, ge=1)


class CategoriaOut(CategoriaCreate):
    id: int
    imagen_url: str
    created_at: Optional[datetime] = None


class MateriaPrimaCreate(BaseModel):
    nombre_es: str = Field(..., min_length=1, max_length=100)
    nombre_en: str = Field(..., min_length=1, max_length=100)
    unidad_medida_id: int = Field(..., gt=0)
    stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    stock_min: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=10, decimal_places=2
    )


class MateriaPrimaUpdate(BaseModel):
    nombre_es: Optional[str] = Field(default=None, min_length=1, max_length=100)
    nombre_en: Optional[str] = Field(default=None, min_length=1, max_length=100)
    unidad_medida_id: Optional[int] = Field(default=None, gt=0)
    stock: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    stock_min: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )


class MateriaPrimaOut(MateriaPrimaCreate):
    id: int
    created_at: Optional[datetime] = None
    medida_es: Optional[str] = None
    medida_en: Optional[str] = None


class UnidadMedidaCreate(BaseModel):
    medida_es: str = Field(..., min_length=1, max_length=50)
    medida_en: str = Field(..., min_length=1, max_length=50)


class UnidadMedidaUpdate(BaseModel):
    medida_es: Optional[str] = Field(default=None, min_length=1, max_length=50)
    medida_en: Optional[str] = Field(default=None, min_length=1, max_length=50)


class UnidadMedidaOut(UnidadMedidaCreate):
    id: int
    created_at: Optional[datetime] = None


class RecetaCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    instrucciones_es: Optional[str] = None
    instrucciones_en: Optional[str] = None


class RecetaUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    instrucciones_es: Optional[str] = None
    instrucciones_en: Optional[str] = None


class RecetaOut(RecetaCreate):
    id: int
    created_at: Optional[datetime] = None


class RecetaIngredienteCreate(BaseModel):
    receta_id: Optional[int] = Field(default=None, gt=0)
    materia_prima_id: int = Field(..., gt=0)
    cantidad: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    requerido: bool = True


class RecetaIngredienteUpdate(BaseModel):
    receta_id: Optional[int] = Field(default=None, gt=0)
    materia_prima_id: Optional[int] = Field(default=None, gt=0)
    cantidad: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    requerido: Optional[bool] = None


class RecetaIngredienteMateriaPrimaInput(BaseModel):
    id: int = Field(..., gt=0)
    cantidad: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    requerido: Optional[bool] = None


class RecetaIngredientesBulkInput(BaseModel):
    receta_id: int = Field(..., gt=0)
    materias_primas: list[RecetaIngredienteMateriaPrimaInput] = Field(
        ..., min_length=1
    )


class RecetaIngredienteOut(RecetaIngredienteCreate):
    id: int
    created_at: Optional[datetime] = None
    producto_nombre: Optional[str] = None
    receta_nombre: Optional[str] = None
    materia_prima_nombre: Optional[str] = None
    materia_prima_nombre_en: Optional[str] = None
    unidad_medida: Optional[str] = None


class RecetaMateriaPrimaOut(BaseModel):
    id: int
    nombre_es: str
    nombre_en: str
    unidad_medida: str
    cantidad: Decimal
    requerido: bool


class RecetaConMateriasPrimasOut(BaseModel):
    receta_id: int
    receta_nombre: str
    materias_primas: list[RecetaMateriaPrimaOut]


class ProductoOut(BaseModel):
    id: int
    categoria_id: int
    receta_id: Optional[int] = None
    nombre_es: str
    nombre_en: str
    precio: Decimal
    imagen_url: str
    tiempo_preparacion: Optional[int] = Field(default=None, gt=0)
    disponible: Optional[bool] = True
    created_at: Optional[datetime] = None
    categoria_nombre_es: Optional[str] = None
    categoria_nombre_en: Optional[str] = None
    receta_nombre: Optional[str] = None


class ProductoCreate(BaseModel):
    categoria_id: int = Field(..., gt=0)
    receta_id: Optional[int] = Field(default=None, gt=0)
    nombre_es: str = Field(..., min_length=1, max_length=100)
    nombre_en: str = Field(..., min_length=1, max_length=100)
    precio: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    tiempo_preparacion: Optional[int] = Field(default=None, gt=0)
    disponible: bool = True


class ProductoUpdate(BaseModel):
    categoria_id: Optional[int] = Field(default=None, gt=0)
    receta_id: Optional[int] = Field(default=None, gt=0)
    nombre_es: Optional[str] = Field(default=None, min_length=1, max_length=100)
    nombre_en: Optional[str] = Field(default=None, min_length=1, max_length=100)
    precio: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    tiempo_preparacion: Optional[int] = Field(default=None, gt=0)
    disponible: Optional[bool] = None