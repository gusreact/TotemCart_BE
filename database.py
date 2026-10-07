import os
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2
from fastapi import HTTPException, status
from psycopg2.extras import RealDictCursor

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def normalize_database_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        return value

    if value.startswith("postgresql://") or value.startswith("postgres://"):
        parsed = urlparse(value)
        dbname = parsed.path.lstrip("/")
        user = parsed.username or ""
        password = parsed.password or ""
        host = parsed.hostname or "localhost"
        port = parsed.port or "5432"

        dsn_parts = [
            f"dbname={dbname}",
            f"user={user}",
            f"password={password}",
            f"host={host}",
            f"port={port}",
        ]
        return " ".join(dsn_parts)

    return value


def get_db_connection():
    if not DATABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URL no está configurada.",
        )
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error de conexión a PostgreSQL: {str(e)}",
        )
