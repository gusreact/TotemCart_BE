import os
import io
import pymysql
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

app = FastAPI(title="TotemCart API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📂 Configuración del sistema de archivos local en PythonAnywhere
# Ejemplo de ruta en PythonAnywhere: /home/tu_usuario/mi_proyecto/static/uploads
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Servir imágenes estáticas vía HTTP
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# 🗄️ Conexión a MySQL (Configurar credenciales de PythonAnywhere)
def get_db_connection():
    return pymysql.connect(
        host="localhost", # "gusvillagran.mysql.pythonanywhere-services.com", # o 'localhost' en desarrollo local
        user="root", # "gusvillagran",
        password="mommommom", # "bp@s3dM8qXd_5uG",
        database="gusvillagran$totemcart",
        cursorclass=pymysql.cursors.DictCursor
    )

# 🔄 Función auxiliar de procesamiento a WebP y guardado en disco
def guardar_imagen_webp(file_bytes: bytes, filename_base: str, carpeta_destino: str) -> str:
    image = Image.open(io.BytesIO(file_bytes))
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    
    nombre_limpio = filename_base.lower().replace(" ", "_")
    nombre_archivo = f"{nombre_limpio}.webp"
    ruta_absoluta = os.path.join(UPLOAD_DIR, carpeta_destino, nombre_archivo)
    
    os.makedirs(os.path.dirname(ruta_absoluta), exist_ok=True)
    
    # Comprimir y guardar en el disco de PythonAnywhere
    image.save(ruta_absoluta, format="WEBP", quality=80)
    
    # URL pública servida por el servidor
    return f"/static/uploads/{carpeta_destino}/{nombre_archivo}"

# 🚀 1. Endpoint PoC: Crear Categoría con Imagen
@app.post("/api/categorias")
async def crear_categoria(
    nombre_es: str = Form(...),
    nombre_en: str = Form(...),
    orden: int = Form(1),
    file: UploadFile = File(...)
):
    try:
        contents = await file.read()
        rel_path = guardar_imagen_webp(contents, f"cat_{nombre_es}", "categorias")
        
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """INSERT INTO categorias (nombre_es, nombre_en, imagen_url, orden) 
                     VALUES (%s, %s, %s, %s)"""
            cursor.execute(sql, (nombre_es, nombre_en, rel_path, orden))
        connection.commit()
        connection.close()

        return {"status": "success", "message": "Categoría creada", "imagen_url": rel_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 🚀 2. Endpoint PoC: Crear Producto con Imagen y Guardar en MySQL
@app.post("/api/productos")
async def crear_producto(
    categoria_id: int = Form(...),
    nombre_es: str = Form(...),
    nombre_en: str = Form(...),
    precio: float = Form(...),
    file: UploadFile = File(...)
):
    try:
        contents = await file.read()
        rel_path = guardar_imagen_webp(contents, f"prod_{nombre_es}", "productos")

        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """INSERT INTO productos (categoria_id, nombre_es, nombre_en, precio, imagen_url) 
                     VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(sql, (categoria_id, nombre_es, nombre_en, precio, rel_path))
            producto_id = cursor.lastrowid
        connection.commit()
        connection.close()

        return {
            "status": "success",
            "producto_id": producto_id,
            "imagen_url": rel_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))