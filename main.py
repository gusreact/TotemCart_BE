import os
import io
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from PIL import Image
import vercel_blob

app = FastAPI(title="TotemCart API")


DATABASE_URL = os.getenv("DATABASE_URL")
# Vercel inyecta automáticamente esta variable al vincular el Blob Store
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")

def get_db_connection():
    if not DATABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="DATABASE_URL no está configurada."
        )
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error de conexión a PostgreSQL: {str(e)}"
        )

@app.post("/api/categorias", status_code=status.HTTP_201_CREATED)
async def crear_categoria(
    nombre_es: str = Form(...),
    nombre_en: str = Form(...),
    orden: int = Form(1),
    file: UploadFile = File(...)
):
    try:
        # 1. Leer el archivo cargado en memoria
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # 2. Convertir la imagen a formato WebP en un buffer en memoria (BytesIO)
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=80)
        buffer.seek(0)

        # 3. Definir nombre de archivo y subirlo directamente a Vercel Blob
        nombre_limpio = nombre_es.lower().replace(" ", "_")
        filename_webp = f"categorias/cat_{nombre_limpio}.webp"

        # La función put() sube los bytes y retorna los metadatos de la CDN
        blob_response = vercel_blob.put(
            filename_webp,
            buffer.getvalue(),
            options={
                "access": "public",
                "token": BLOB_READ_WRITE_TOKEN
            }
        )

        # La URL pública HTTPS generada por Vercel CDN
        public_url = blob_response.get("url")

        # 4. Guardar el registro con la URL pública en PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO categorias (nombre_es, nombre_en, orden, imagen_url)
            VALUES (%s, %s, %s, %s)
            RETURNING id, nombre_es, nombre_en, orden, imagen_url, created_at;
        """
        cursor.execute(query, (nombre_es, nombre_en, orden, public_url))
        nueva_categoria = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status": "success",
            "message": "Categoría creada exitosamente",
            "data": nueva_categoria
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error al procesar la solicitud: {str(e)}"
        )