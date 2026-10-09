import os
import io
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from PIL import Image
import vercel_blob

from database import get_db_connection
from routers.users import router as users_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="TotemCart API", lifespan=lifespan)
app.include_router(users_router)

# Habilitar CORS para recibir peticiones desde tu app en Vercel y localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción podés reemplazar "*" por tu dominio de Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Variables de Entorno
SECRET_KEY = os.getenv("JWT_SECRET") or os.getenv("LOCAL_JWT_SECRET") or "super-secret-key-totem-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas de sesión

# Usa Render en producción y variables locales en desarrollo
DATABASE_URL = os.getenv("DATABASE_URL")

# Vercel inyecta automáticamente esta variable al vincular el Blob Store
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS categorias (
            id SERIAL PRIMARY KEY,
            nombre_es VARCHAR(255) NOT NULL,
            nombre_en VARCHAR(255) NOT NULL,
            orden INTEGER NOT NULL DEFAULT 1,
            imagen_url TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            nombre VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'user',
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    conn.commit()
    cursor.close()
    conn.close()


def normalize_password_for_bcrypt(password: str) -> str:
    if password is None:
        return ""
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión expirada o token inválido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        return {"username": username, "role": role}
    except JWTError:
        raise credentials_exception
@app.post("/api/user/create")
def create_user(username: str = Form(...), password: str = Form(...), nombre: str = Form(...), role: str = Form("user")):
    try:
        hashed = pwd_context.hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO usuarios (username, password_hash, nombre, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id, username, nombre, role;
            """,
            (username, hashed, nombre, role),
        )

        user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error al procesar la solicitud: {str(e)}"
        )

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = %s;", (form_data.username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Usuario o contraseña incorrectos"
        )

    access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "username": user["username"],
        "nombre": user["nombre"],
        "role": user["role"]
    }

@app.post("/api/categorias", status_code=status.HTTP_201_CREATED)
async def crear_categoria(
    nombre_es: str = Form(...),
    nombre_en: str = Form(...),
    orden: int = Form(1),
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)  # <- Exige el Token Bearer
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
            "message": f"Categoría creada por el usuario {current_user}",
            "data": nueva_categoria
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error al procesar la solicitud: {str(e)}"
        )

@app.get("/api/admin-only")
def admin_only(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    return {"message": "Acceso permitido"}