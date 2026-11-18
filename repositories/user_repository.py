from psycopg2.extras import RealDictCursor

from database import get_db_connection


class UserRepository:
    @staticmethod
    def _user_select():
        return """
            SELECT usuario.id, usuario.username, usuario.nombre,
                   usuario.role_id,
                   CASE usuario.role_id
                       WHEN 1 THEN 'administrador'
                       WHEN 2 THEN 'cocinero'
                       ELSE rol.nombre_es
                   END AS role,
                   rol.nombre_es AS role_es,
                   rol.nombre_en AS role_en,
                   usuario.created_at
            FROM usuarios AS usuario
            JOIN roles AS rol ON rol.id = usuario.role_id
        """

    def get_all_users(self):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(self._user_select() + " ORDER BY usuario.id;")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return users

    def get_by_id(self, user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            self._user_select() + " WHERE usuario.id = %s;",
            (user_id,),
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user

    def exists_by_username(self, username: str) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM usuarios WHERE username = %s;", (username,))
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists

    def has_any_users(self) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM usuarios) AS has_users;"
                )
                return cursor.fetchone()["has_users"]
        finally:
            conn.close()

    def role_exists(self, role_id: int) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM roles WHERE id = %s;", (role_id,))
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists

    def create_user(
        self, username: str, password_hash: str, nombre: str, role_id: int
    ):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            INSERT INTO usuarios (username, password_hash, nombre, role_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (username, password_hash, nombre, role_id),
        )
        created_user_id = cursor.fetchone()["id"]
        conn.commit()
        cursor.close()
        conn.close()
        return self.get_by_id(created_user_id)

    def update_user(self, user_id: int, update_data: dict):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        fields = []
        values = []
        for key, value in update_data.items():
            fields.append(f"{key} = %s")
            values.append(value)
        values.append(user_id)

        query = f"""
            UPDATE usuarios
            SET {', '.join(fields)}
            WHERE id = %s
            RETURNING id;
        """
        cursor.execute(query, tuple(values))
        updated_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return self.get_by_id(user_id) if updated_user else None

    def delete_user(self, user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE id = %s;", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
