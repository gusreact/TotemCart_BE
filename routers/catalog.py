import io
import os
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from schemas.catalog_schema import (
    CategoriaCreate,
    CategoriaOut,
    CategoriaUpdate,
    MateriaPrimaCreate,
    MateriaPrimaOut,
    MateriaPrimaUpdate,
    ProductoCreate,
    ProductoOut,
    ProductoUpdate,
    RecetaConMateriasPrimasOut,
    RecetaCreate,
    RecetaIngredientesBulkInput,
    RecetaIngredienteCreate,
    RecetaIngredienteOut,
    RecetaOut,
    RecetaUpdate,
    UnidadMedidaCreate,
    UnidadMedidaOut,
    UnidadMedidaUpdate,
)
from services.catalog_service import CatalogService
from services.security import get_current_user

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/categorias", response_model=list[CategoriaOut])
def get_categorias(service: CatalogService = Depends()):
    return service.get_all("categorias")


@router.get("/categorias/{item_id}", response_model=CategoriaOut)
def get_categoria(item_id: int, service: CatalogService = Depends()):
    return service.get_by_id("categorias", item_id)


@router.post(
    "/categorias",
    response_model=CategoriaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_categoria(
    nombre_es: str = Form(...),
    nombre_en: str = Form(...),
    orden: int = Form(1),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    service: CatalogService = Depends(),
):
    try:
        payload = CategoriaCreate(
            nombre_es=nombre_es, nombre_en=nombre_en, orden=orden
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error

    data = payload.dict()
    data["imagen_url"] = await _upload_image(file, "categorias", "cat")
    return service.create("categorias", data)


@router.put("/categorias/{item_id}", response_model=CategoriaOut)
async def update_categoria(
    item_id: int,
    nombre_es: str | None = Form(None),
    nombre_en: str | None = Form(None),
    orden: int | None = Form(None),
    file: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user),
    service: CatalogService = Depends(),
):
    existing_category = service.get_by_id("categorias", item_id)
    data = {
        key: value
        for key, value in (
            ("nombre_es", nombre_es),
            ("nombre_en", nombre_en),
            ("orden", orden),
        )
        if value is not None
    }
    try:
        payload = CategoriaUpdate(**data)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error
    data = payload.dict(exclude_unset=True)

    if file is not None:
        data["imagen_url"] = await _upload_image(file, "categorias", "cat")
    elif not data:
        return existing_category

    return service.update("categorias", item_id, data)


@router.delete("/categorias/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_categoria(
    item_id: int,
    current_user: dict = Depends(get_current_user),
    service: CatalogService = Depends(),
):
    service.delete("categorias", item_id)


@router.get("/materias-primas", response_model=list[MateriaPrimaOut])
def get_materias_primas(service: CatalogService = Depends()):
    return service.get_all("materias_primas")


@router.get("/materias-primas/{item_id}", response_model=MateriaPrimaOut)
def get_materia_prima(item_id: int, service: CatalogService = Depends()):
    return service.get_by_id("materias_primas", item_id)


@router.post(
    "/materias-primas",
    response_model=MateriaPrimaOut,
    status_code=status.HTTP_201_CREATED,
)
def create_materia_prima(
    payload: MateriaPrimaCreate, service: CatalogService = Depends()
):
    return service.create("materias_primas", payload.dict())


@router.put("/materias-primas/{item_id}", response_model=MateriaPrimaOut)
def update_materia_prima(
    item_id: int,
    payload: MateriaPrimaUpdate,
    service: CatalogService = Depends(),
):
    return service.update(
        "materias_primas", item_id, payload.dict(exclude_unset=True)
    )


@router.delete("/materias-primas/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_materia_prima(item_id: int, service: CatalogService = Depends()):
    service.delete("materias_primas", item_id)


@router.get("/unidades-medida", response_model=list[UnidadMedidaOut])
def get_unidades_medida(service: CatalogService = Depends()):
    return service.get_all("unidades_medida")


@router.get("/unidades-medida/{item_id}", response_model=UnidadMedidaOut)
def get_unidad_medida(item_id: int, service: CatalogService = Depends()):
    return service.get_by_id("unidades_medida", item_id)


@router.post(
    "/unidades-medida",
    response_model=UnidadMedidaOut,
    status_code=status.HTTP_201_CREATED,
)
def create_unidad_medida(
    payload: UnidadMedidaCreate,
    current_user: dict = Depends(get_current_user),
    service: CatalogService = Depends(),
):
    return service.create("unidades_medida", payload.dict())


@router.put("/unidades-medida/{item_id}", response_model=UnidadMedidaOut)
def update_unidad_medida(
    item_id: int,
    payload: UnidadMedidaUpdate,
    current_user: dict = Depends(get_current_user),
    service: CatalogService = Depends(),
):
    return service.update(
        "unidades_medida", item_id, payload.dict(exclude_unset=True)
    )


@router.delete(
    "/unidades-medida/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_unidad_medida(
    item_id: int,
    current_user: dict = Depends(get_current_user),
    service: CatalogService = Depends(),
):
    service.delete("unidades_medida", item_id)


@router.get("/recetas", response_model=list[RecetaOut])
def get_recetas(service: CatalogService = Depends()):
    return service.get_all("recetas")


@router.get("/recetas/{item_id}", response_model=RecetaOut)
def get_receta(item_id: int, service: CatalogService = Depends()):
    return service.get_by_id("recetas", item_id)


@router.post("/recetas", response_model=RecetaOut, status_code=status.HTTP_201_CREATED)
def create_receta(payload: RecetaCreate, service: CatalogService = Depends()):
    return service.create("recetas", payload.dict())


@router.put("/recetas/{item_id}", response_model=RecetaOut)
def update_receta(
    item_id: int, payload: RecetaUpdate, service: CatalogService = Depends()
):
    return service.update("recetas", item_id, payload.dict(exclude_unset=True))


@router.delete("/recetas/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receta(item_id: int, service: CatalogService = Depends()):
    service.delete("recetas", item_id)


@router.get(
    "/receta-ingredientes",
    response_model=list[RecetaConMateriasPrimasOut],
)
def get_receta_ingredientes(service: CatalogService = Depends()):
    return service.get_recipes_with_materials()


@router.get("/receta-ingredientes/{item_id}", response_model=RecetaIngredienteOut)
def get_receta_ingrediente(item_id: int, service: CatalogService = Depends()):
    return service.get_by_id("receta_ingredientes", item_id)


@router.post(
    "/receta-ingredientes",
    response_model=list[RecetaConMateriasPrimasOut],
    status_code=status.HTTP_201_CREATED,
)
def create_receta_ingrediente(
    payload: list[RecetaIngredientesBulkInput], service: CatalogService = Depends()
):
    return service.save_recipe_ingredients(
        [recipe.dict() for recipe in payload], upsert=False
    )


@router.put(
    "/receta-ingredientes",
    response_model=list[RecetaConMateriasPrimasOut],
)
def update_receta_ingrediente(
    payload: list[RecetaIngredientesBulkInput],
    service: CatalogService = Depends(),
):
    return service.save_recipe_ingredients(
        [recipe.dict() for recipe in payload], upsert=True
    )


@router.delete(
    "/receta-ingredientes/{receta_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_receta_ingrediente(receta_id: int, service: CatalogService = Depends()):
    service.delete_recipe_ingredients(receta_id)


def _parse_optional_id(value: str | None, field_name: str) -> int | None:
    if value is None:
        return None
    if value == "" and field_name == "receta_id":
        return None
    try:
        parsed_value = int(value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} debe ser un número entero válido.",
        ) from error
    if parsed_value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} debe ser mayor que cero.",
        )
    return parsed_value


def _parse_optional_minutes(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed_value = int(value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tiempo_preparacion debe ser un número entero de minutos.",
        ) from error
    if parsed_value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tiempo_preparacion debe ser mayor que cero.",
        )
    return parsed_value


async def _upload_image(file: UploadFile, folder: str, prefix: str) -> str:
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El almacenamiento de imágenes no está configurado.",
        )

    try:
        import vercel_blob
    except ModuleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La dependencia de almacenamiento de imágenes no está instalada.",
        ) from error

    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo enviado no es una imagen válida.",
        ) from error

    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=80)
    filename = f"{folder}/{prefix}_{uuid4().hex}.webp"
    try:
        response = vercel_blob.put(
            filename,
            buffer.getvalue(),
            options={"access": "public", "token": token, "allowOverwrite": True},
        )
        image_url = response.get("url")
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo guardar la imagen.",
        ) from error

    if not image_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El almacenamiento no devolvió la URL de la imagen.",
        )
    return image_url


@router.get("/productos", response_model=list[ProductoOut])
def get_productos(service: CatalogService = Depends()):
    return service.get_all("productos")


@router.get("/productos/{item_id}", response_model=ProductoOut)
def get_producto(item_id: int, service: CatalogService = Depends()):
    return service.get_by_id("productos", item_id)


@router.post(
    "/productos", response_model=ProductoOut, status_code=status.HTTP_201_CREATED
)
async def create_producto(
    categoria_id: int = Form(...),
    nombre_es: str = Form(...),
    nombre_en: str = Form(...),
    precio: Decimal = Form(...),
    tiempo_preparacion: str | None = Form(None),
    receta_id: str | None = Form(None),
    disponible: bool = Form(True),
    file: UploadFile = File(...),
    service: CatalogService = Depends(),
):
    try:
        payload = ProductoCreate(
            categoria_id=categoria_id,
            receta_id=_parse_optional_id(receta_id, "receta_id"),
            nombre_es=nombre_es,
            nombre_en=nombre_en,
            precio=precio,
            tiempo_preparacion=_parse_optional_minutes(tiempo_preparacion),
            disponible=disponible,
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error

    image_url = await _upload_image(file, "productos", "prod")
    data = payload.dict()
    data["imagen_url"] = image_url
    return service.create("productos", data)


@router.put("/productos/{item_id}", response_model=ProductoOut)
async def update_producto(
    item_id: int,
    categoria_id: str | None = Form(None),
    receta_id: str | None = Form(None),
    nombre_es: str | None = Form(None),
    nombre_en: str | None = Form(None),
    precio: Decimal | None = Form(None),
    tiempo_preparacion: str | None = Form(None),
    disponible: bool | None = Form(None),
    file: UploadFile | None = File(None),
    service: CatalogService = Depends(),
):
    data = {}
    if categoria_id is not None:
        data["categoria_id"] = _parse_optional_id(categoria_id, "categoria_id")
    if receta_id is not None:
        data["receta_id"] = _parse_optional_id(receta_id, "receta_id")
    if tiempo_preparacion is not None:
        data["tiempo_preparacion"] = _parse_optional_minutes(
            tiempo_preparacion
        )
    for field_name, value in (
        ("nombre_es", nombre_es),
        ("nombre_en", nombre_en),
        ("precio", precio),
        ("disponible", disponible),
    ):
        if value is not None:
            data[field_name] = value

    try:
        payload = ProductoUpdate(**data)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error
    data = payload.dict(exclude_unset=True)

    if file is not None:
        service.get_by_id("productos", item_id)
        data["imagen_url"] = await _upload_image(file, "productos", "prod")

    return service.update("productos", item_id, data)


@router.delete("/productos/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_producto(item_id: int, service: CatalogService = Depends()):
    service.delete("productos", item_id)
