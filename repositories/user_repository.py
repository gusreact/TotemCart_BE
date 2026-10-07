from psycopg2.extras import RealDictCursor

from database import get_db_connection


class UserRepository:
    def get_all_users(self):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, username, nombre, role, created_at FROM usuarios ORDER BY id;"
        )
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return users

    def get_by_id(self, user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, username, nombre, role, created_at FROM usuarios WHERE id = %s;",
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

    def create_user(self, username: str, password_hash: str, nombre: str, role: str):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            INSERT INTO usuarios (username, password_hash, nombre, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id, username, nombre, role, created_at;
            """,
            (username, password_hash, nombre, role),
        )
        created_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return created_user

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
            RETURNING id, username, nombre, role, created_at;
        """
        cursor.execute(query, tuple(values))
        updated_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return updated_user

    def delete_user(self, user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE id = %s;", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
