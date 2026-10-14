import psycopg2
from fastapi import Depends, HTTPException, status

from repositories.catalog_repository import CatalogRepository


class CatalogService:
    def __init__(self, repository: CatalogRepository = Depends()):
        self.repository = repository

    def get_all(self, resource: str):
        return self.repository.get_all(resource)

    def get_recipes_with_materials(self, recipe_ids: list[int] | None = None):
        recipes = {}
        for row in self.repository.get_recipes_with_materials(recipe_ids):
            recipe_id = row["receta_id"]
            if recipe_id not in recipes:
                recipes[recipe_id] = {
                    "receta_id": recipe_id,
                    "receta_nombre": row["receta_nombre"],
                    "materias_primas": [],
                }
            recipes[recipe_id]["materias_primas"].append(
                {
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "unidad_medida": row["unidad_medida"],
                    "cantidad": row["cantidad"],
                }
            )
        return list(recipes.values())

    def save_recipe_ingredients(self, recipes: list[dict], upsert: bool = False):
        recipe_ids = []
        seen_recipe_ids = set()
        for recipe in recipes:
            recipe_id = recipe["receta_id"]
            if recipe_id in seen_recipe_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Cada receta debe aparecer una sola vez en la solicitud.",
                )
            seen_recipe_ids.add(recipe_id)
            recipe_ids.append(recipe_id)

            seen_material_ids = set()
            for material in recipe["materias_primas"]:
                material_id = material["id"]
                if material_id in seen_material_ids:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="No se permite repetir una materia prima dentro de una receta.",
                    )
                seen_material_ids.add(material_id)

        try:
            self.repository.save_recipe_ingredients(recipes, upsert=upsert)
        except psycopg2.errors.UniqueViolation as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta materia prima ya está asignada a la receta.",
            ) from error
        except psycopg2.errors.ForeignKeyViolation as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La receta o materia prima relacionada no existe.",
            ) from error

        return self.get_recipes_with_materials(recipe_ids)

    def get_by_id(self, resource: str, item_id: int):
        item = self.repository.get_by_id(resource, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro no encontrado.",
            )
        return item

    def create(self, resource: str, data: dict):
        try:
            return self.repository.create(resource, data)
        except psycopg2.errors.UniqueViolation as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta materia prima ya está asignada a la receta.",
            ) from error
        except psycopg2.errors.ForeignKeyViolation as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una categoría, receta o materia prima relacionada no existe.",
            ) from error

    def update(self, resource: str, item_id: int, data: dict):
        existing_item = self.repository.get_by_id(resource, item_id)
        if existing_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro no encontrado.",
            )
        if not data:
            return existing_item

        try:
            return self.repository.update(resource, item_id, data)
        except psycopg2.errors.UniqueViolation as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta materia prima ya está asignada a la receta.",
            ) from error
        except psycopg2.errors.ForeignKeyViolation as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una categoría, receta o materia prima relacionada no existe.",
            ) from error

    def delete(self, resource: str, item_id: int):
        existing_item = self.repository.get_by_id(resource, item_id)
        if existing_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro no encontrado.",
            )

        try:
            self.repository.delete(resource, item_id)
        except psycopg2.errors.ForeignKeyViolation as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar porque el registro está siendo utilizado.",
            ) from error

    def delete_recipe_ingredients(self, recipe_id: int):
        self.get_by_id("recetas", recipe_id)
        self.repository.delete_recipe_ingredients(recipe_id)

