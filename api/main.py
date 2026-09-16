import os
import io
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.staticfiles import StaticFiles
from PIL import Image

app = FastAPI(title="TotemCart API")

# Configuración de carpetas para guardar imágenes
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(os.path.join(UPLOAD_DIR, "categorias"), exist_ok=True)

# Montar el directorio estático para servir las imágenes mediante URL pública
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Variable de entorno de PostgreSQL (Render la inyecta automáticamente)
DATABASE_URL = os.getenv("DATABASE_URL")

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

# Endpoint para crear las tablas al iniciar (o podés correrlo manualmente)
@app.on_event("startup")
def init_db():
    if DATABASE_URL:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categorias (
                id SERIAL PRIMARY KEY,
                nombre_es VARCHAR(100) NOT NULL,
                nombre_en VARCHAR(100) NOT NULL,
                imagen_url VARCHAR(255),
                orden INT DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()

@app.post("/api/categorias", status_code=status.HTTP_201_CREATED)
async def crear_categoria(
    nombre_es: str = Form(...),
    nombre_en: str = Form(...),
    orden: int = Form(1),
    file: UploadFile = File(...)
):
    try:
        # 1. Leer el stream de la imagen asincrónicamente
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # 2. Guardar imagen convertida a WebP en disco
        nombre_limpio = nombre_es.lower().replace(" ", "_")
        filename_webp = f"cat_{nombre_limpio}.webp"
        file_path = os.path.join(UPLOAD_DIR, "categorias", filename_webp)

        image.save(file_path, format="WEBP", quality=80)
        
        # Ruta relativa servida públicamente
        rel_path = f"/static/uploads/categorias/{filename_webp}"

        # 3. Insertar registro en PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO categorias (nombre_es, nombre_en, orden, imagen_url)
            VALUES (%s, %s, %s, %s)
            RETURNING id, nombre_es, nombre_en, orden, imagen_url, created_at;
        """
        cursor.execute(query, (nombre_es, nombre_en, orden, rel_path))
        nueva_categoria = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status": "success",
            "message": "Categoría creada con éxito",
            "data": nueva_categoria
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error procesando la solicitud: {str(e)}"
        )