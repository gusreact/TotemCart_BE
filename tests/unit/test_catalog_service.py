from unittest.mock import Mock

import psycopg2
import pytest
from fastapi import HTTPException, status

from repositories.catalog_repository import CatalogRepository
from services.catalog_service import CatalogService


@pytest.fixture
def repository():
    return Mock(spec=CatalogRepository)


def test_get_recipes_with_materials_groups_rows_by_recipe(repository):
    repository.get_recipes_with_materials.return_value = [
        {
            "receta_id": 1,
            "receta_nombre": "Soup",
            "id": 10,
            "nombre_es": "Salt",
            "nombre_en": "Salt",
            "unidad_medida": "g",
            "cantidad": 2,
            "requerido": True,
        },
        {
            "receta_id": 1,
            "receta_nombre": "Soup",
            "id": 11,
            "nombre_es": "Water",
            "nombre_en": "Water",
            "unidad_medida": "ml",
            "cantidad": 100,
            "requerido": False,
        },
    ]

    recipes = CatalogService(repository=repository).get_recipes_with_materials([1])

    assert len(recipes) == 1
    assert recipes[0]["receta_id"] == 1
    assert [item["id"] for item in recipes[0]["materias_primas"]] == [10, 11]
    repository.get_recipes_with_materials.assert_called_once_with([1])


def test_save_recipe_ingredients_rejects_duplicate_recipe_ids(repository):
    service = CatalogService(repository=repository)
    recipes = [
        {"receta_id": 1, "materias_primas": [{"id": 10}]},
        {"receta_id": 1, "materias_primas": [{"id": 11}]},
    ]

    with pytest.raises(HTTPException) as error:
        service.save_recipe_ingredients(recipes)

    assert error.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    repository.save_recipe_ingredients.assert_not_called()


def test_save_recipe_ingredients_rejects_duplicate_materials(repository):
    service = CatalogService(repository=repository)
    recipes = [
        {"receta_id": 1, "materias_primas": [{"id": 10}, {"id": 10}]},
    ]

    with pytest.raises(HTTPException) as error:
        service.save_recipe_ingredients(recipes)

    assert error.value.status_code == status.HTTP_409_CONFLICT
    repository.save_recipe_ingredients.assert_not_called()


def test_save_recipe_ingredients_maps_unique_violation(repository):
    repository.save_recipe_ingredients.side_effect = psycopg2.errors.UniqueViolation()

    with pytest.raises(HTTPException) as error:
        CatalogService(repository=repository).save_recipe_ingredients(
            [{"receta_id": 1, "materias_primas": [{"id": 10}]}]
        )

    assert error.value.status_code == status.HTTP_409_CONFLICT


def test_get_by_id_returns_not_found_when_missing(repository):
    repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        CatalogService(repository=repository).get_by_id("productos", 404)

    assert error.value.status_code == status.HTTP_404_NOT_FOUND


def test_update_with_empty_data_returns_existing_record(repository):
    existing = {"id": 1, "nombre_es": "Drink"}
    repository.get_by_id.return_value = existing

    result = CatalogService(repository=repository).update("productos", 1, {})

    assert result == existing
    repository.update.assert_not_called()


def test_create_maps_foreign_key_violation(repository):
    repository.create.side_effect = psycopg2.errors.ForeignKeyViolation()

    with pytest.raises(HTTPException) as error:
        CatalogService(repository=repository).create("productos", {"categoria_id": 8})

    assert error.value.status_code == status.HTTP_400_BAD_REQUEST


def test_delete_maps_foreign_key_violation(repository):
    repository.get_by_id.return_value = {"id": 1}
    repository.delete.side_effect = psycopg2.errors.ForeignKeyViolation()

    with pytest.raises(HTTPException) as error:
        CatalogService(repository=repository).delete("categorias", 1)

    assert error.value.status_code == status.HTTP_409_CONFLICT
