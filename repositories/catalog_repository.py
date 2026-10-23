from psycopg2.extras import RealDictCursor

from database import get_db_connection


RESOURCE_CONFIG = {
    "categorias": {
        "table": "categorias",
        "columns": ("nombre_es", "nombre_en", "orden", "imagen_url"),
        "id_column": "c.id",
        "order_by": "c.orden, c.id",
        "select": "SELECT c.* FROM categorias c",
    },
    "materias_primas": {
        "table": "materias_primas",
        "columns": ("nombre_es", "nombre_en", "unidad_medida_id", "stock", "stock_min"),
        "id_column": "mp.id",
        "select": """
            SELECT mp.*, um.medida_es, um.medida_en
            FROM materias_primas mp
            JOIN unidades_medida um ON um.id = mp.unidad_medida_id
        """,
    },
    "unidades_medida": {
        "table": "unidades_medida",
        "columns": ("medida_es", "medida_en"),
        "id_column": "um.id",
        "select": "SELECT um.* FROM unidades_medida um",
    },
    "recetas": {
        "table": "recetas",
        "columns": ("nombre", "instrucciones_es", "instrucciones_en"),
        "id_column": "r.id",
        "select": "SELECT r.* FROM recetas r",
    },
    "receta_ingredientes": {
        "table": "receta_ingredientes",
        "columns": ("receta_id", "materia_prima_id", "cantidad", "requerido"),
        "id_column": "ri.id",
        "select": """
            SELECT ri.*,
                   r.nombre AS receta_nombre,
                   mp.nombre_es AS materia_prima_nombre,
                   mp.nombre_en AS materia_prima_nombre_en,
                   um.medida_es AS unidad_medida
            FROM receta_ingredientes ri
            LEFT JOIN recetas r ON r.id = ri.receta_id
            LEFT JOIN materias_primas mp ON mp.id = ri.materia_prima_id
                 LEFT JOIN unidades_medida um ON um.id = mp.unidad_medida_id
        """,
    },
    "productos": {
        "table": "productos",
        "columns": (
            "categoria_id",
            "receta_id",
            "nombre_es",
            "nombre_en",
            "precio",
            "imagen_url",
            "disponible",
        ),
        "id_column": "p.id",
        "select": """
            SELECT p.*, c.nombre_es AS categoria_nombre_es,
                   c.nombre_en AS categoria_nombre_en,
                   r.nombre AS receta_nombre
            FROM productos p
            LEFT JOIN categorias c ON c.id = p.categoria_id
            LEFT JOIN recetas r ON r.id = p.receta_id
        """,
    },
}


class CatalogRepository:
    def _execute(self, query: str, values=(), fetch: str = "one", commit=False):
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, values)
                if commit:
                    conn.commit()
                if fetch == "all":
                    return cursor.fetchall()
                if fetch == "one":
                    return cursor.fetchone()
                return None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _select(self, resource: str) -> str:
        return RESOURCE_CONFIG[resource]["select"]

    def get_all(self, resource: str):
        order_by = RESOURCE_CONFIG[resource].get(
            "order_by", RESOURCE_CONFIG[resource]["id_column"]
        )
        return self._execute(
            f"{self._select(resource)} ORDER BY {order_by};",
            fetch="all",
        )

    def get_recipes_with_materials(self, recipe_ids: list[int] | None = None):
        query = """
            SELECT r.id AS receta_id,
                   r.nombre AS receta_nombre,
                   mp.id,
                   mp.nombre_es,
                   mp.nombre_en,
                   um.medida_es AS unidad_medida,
                   ri.cantidad,
                   ri.requerido
            FROM recetas r
            JOIN receta_ingredientes ri ON ri.receta_id = r.id
            JOIN materias_primas mp ON mp.id = ri.materia_prima_id
                 JOIN unidades_medida um ON um.id = mp.unidad_medida_id
        """
        values = ()
        if recipe_ids is not None:
            query += " WHERE r.id = ANY(%s)"
            values = (recipe_ids,)
        query += " ORDER BY r.id, mp.id;"
        return self._execute(query, values, fetch="all")

    def save_recipe_ingredients(self, recipes: list[dict], upsert: bool = False):
        values = [
            (
                recipe["receta_id"],
                material["id"],
                material["cantidad"],
                material.get("requerido"),
                material.get("requerido"),
            )
            for recipe in recipes
            for material in recipe["materias_primas"]
        ]
        query = """
            INSERT INTO receta_ingredientes (
                receta_id, materia_prima_id, cantidad, requerido
            )
            VALUES (%s, %s, %s, COALESCE(%s, TRUE))
        """
        if upsert:
            query += """
                ON CONFLICT (receta_id, materia_prima_id)
                DO UPDATE SET
                    cantidad = EXCLUDED.cantidad,
                    requerido = CASE
                        WHEN %s IS NULL THEN receta_ingredientes.requerido
                        ELSE EXCLUDED.requerido
                    END
            """
        query += ";"

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(
                    query,
                    values if upsert else [value[:4] for value in values],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_by_id(self, resource: str, item_id: int):
        return self._execute(
            f"{self._select(resource)} WHERE {RESOURCE_CONFIG[resource]['id_column']} = %s;",
            (item_id,),
        )

    def get_checkout_products(self, product_ids: list[int]):
        return self._execute(
            """
            SELECT id, nombre_es, precio, imagen_url, receta_id
            FROM productos
            WHERE id = ANY(%s) AND COALESCE(disponible, TRUE) = TRUE;
            """,
            (product_ids,),
            fetch="all",
        )

    def get_checkout_recipe_ingredients(self, recipe_ids: list[int]):
        if not recipe_ids:
            return []
        return self._execute(
            """
            SELECT receta_id, materia_prima_id, cantidad, requerido
            FROM receta_ingredientes
            WHERE receta_id = ANY(%s)
            ORDER BY receta_id, materia_prima_id;
            """,
            (recipe_ids,),
            fetch="all",
        )

    def create(self, resource: str, data: dict):
        config = RESOURCE_CONFIG[resource]
        columns = tuple(data)
        if not columns or any(column not in config["columns"] for column in columns):
            raise ValueError("Columnas inválidas para el recurso solicitado.")
        placeholders = ", ".join("%s" for _ in columns)
        query = f"""
            INSERT INTO {config['table']} ({', '.join(columns)})
            VALUES ({placeholders})
            RETURNING id;
        """
        created = self._execute(
            query, tuple(data[column] for column in columns), commit=True
        )
        return self.get_by_id(resource, created["id"])

    def update(self, resource: str, item_id: int, data: dict):
        config = RESOURCE_CONFIG[resource]
        if any(column not in config["columns"] for column in data):
            raise ValueError("Columnas inválidas para el recurso solicitado.")
        assignments = ", ".join(f"{column} = %s" for column in data)
        query = f"""
            UPDATE {config['table']}
            SET {assignments}
            WHERE id = %s
            RETURNING id;
        """
        updated = self._execute(
            query, (*data.values(), item_id), commit=True
        )
        if updated is None:
            return None
        return self.get_by_id(resource, updated["id"])

    def delete(self, resource: str, item_id: int) -> bool:
        table = RESOURCE_CONFIG[resource]["table"]
        deleted = self._execute(
            f"DELETE FROM {table} WHERE id = %s RETURNING id;",
            (item_id,),
            commit=True,
        )
        return deleted is not None

    def delete_recipe_ingredients(self, recipe_id: int) -> None:
        self._execute(
            "DELETE FROM receta_ingredientes WHERE receta_id = %s;",
            (recipe_id,),
            fetch=None,
            commit=True,
        )
