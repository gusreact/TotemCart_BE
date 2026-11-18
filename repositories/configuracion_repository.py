from database import get_db_connection


class ConfiguracionRepository:
    def get_all(self):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT clave, valor
                    FROM configuracion
                    ORDER BY clave;
                    """
                )
                return cursor.fetchall()
        finally:
            conn.close()

    def get_by_clave(self, clave: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT clave, valor
                    FROM configuracion
                    WHERE clave = %s;
                    """,
                    (clave,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def create(self, clave: str, valor: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO configuracion (clave, valor)
                    VALUES (%s, %s)
                    ON CONFLICT (clave) DO NOTHING
                    RETURNING clave, valor;
                    """,
                    (clave, valor),
                )
                configuracion = cursor.fetchone()
            conn.commit()
            return configuracion
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update(self, clave: str, valor: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE configuracion
                    SET valor = %s
                    WHERE clave = %s
                    RETURNING clave, valor;
                    """,
                    (valor, clave),
                )
                configuracion = cursor.fetchone()
            conn.commit()
            return configuracion
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, clave: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM configuracion
                    WHERE clave = %s;
                    """,
                    (clave,),
                )
                deleted = cursor.rowcount == 1
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
