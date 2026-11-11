from database import get_db_connection


class PedidoEstadoRepository:
    def get_all(self):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, descripcion_es, descripcion_en
                    FROM pedido_estado
                    ORDER BY id;
                    """
                )
                return cursor.fetchall()
        finally:
            conn.close()

    def get_by_id(self, estado_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, descripcion_es, descripcion_en
                    FROM pedido_estado
                    WHERE id = %s;
                    """,
                    (estado_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def create(self, descripcion_es: str, descripcion_en: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pedido_estado (descripcion_es, descripcion_en)
                    VALUES (%s, %s)
                    RETURNING id, descripcion_es, descripcion_en;
                    """,
                    (descripcion_es, descripcion_en),
                )
                estado = cursor.fetchone()
            conn.commit()
            return estado
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update(self, estado_id: int, values: dict):
        columns = [
            column
            for column in ("descripcion_es", "descripcion_en")
            if column in values
        ]
        if not columns:
            return self.get_by_id(estado_id)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                assignments = ", ".join(f"{column} = %s" for column in columns)
                cursor.execute(
                    f"""
                    UPDATE pedido_estado
                    SET {assignments}
                    WHERE id = %s
                    RETURNING id, descripcion_es, descripcion_en;
                    """,
                    tuple(values[column] for column in columns) + (estado_id,),
                )
                estado = cursor.fetchone()
            conn.commit()
            return estado
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, estado_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM pedido_estado WHERE id = %s;", (estado_id,))
                deleted = cursor.rowcount == 1
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
