from database import get_db_connection


class RoleRepository:
    def get_all(self):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, nombre_es, nombre_en, inmutable
                    FROM roles
                    ORDER BY id;
                    """
                )
                return cursor.fetchall()
        finally:
            conn.close()

    def get_by_id(self, role_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, nombre_es, nombre_en, inmutable
                    FROM roles
                    WHERE id = %s;
                    """,
                    (role_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def create(self, nombre_es: str, nombre_en: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO roles (nombre_es, nombre_en)
                    VALUES (%s, %s)
                    RETURNING id, nombre_es, nombre_en, inmutable;
                    """,
                    (nombre_es, nombre_en),
                )
                role = cursor.fetchone()
            conn.commit()
            return role
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update(self, role_id: int, values: dict):
        columns = [column for column in ("nombre_es", "nombre_en") if column in values]
        if not columns:
            return self.get_by_id(role_id)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                assignments = ", ".join(f"{column} = %s" for column in columns)
                cursor.execute(
                    f"""
                    UPDATE roles
                    SET {assignments}
                    WHERE id = %s
                    RETURNING id, nombre_es, nombre_en, inmutable;
                    """,
                    tuple(values[column] for column in columns) + (role_id,),
                )
                role = cursor.fetchone()
            conn.commit()
            return role
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, role_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM roles
                    WHERE id = %s AND inmutable = FALSE;
                    """,
                    (role_id,),
                )
                deleted = cursor.rowcount == 1
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
