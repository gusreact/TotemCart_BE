import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import jwt

from database import get_db_connection
from routers.catalog import router as catalog_router
from routers.users import router as users_router
from services.security import ALGORITHM, SECRET_KEY, get_current_user

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="TotemCart API", lifespan=lifespan)
app.include_router(users_router)
app.include_router(catalog_router)

# Habilitar CORS para recibir peticiones desde tu app en Vercel y localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción podés reemplazar "*" por tu dominio de Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Variables de Entorno
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas de sesión

# Usa Render en producción y variables locales en desarrollo
DATABASE_URL = os.getenv("DATABASE_URL")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS materias_primas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            unidad_medida VARCHAR(20) NOT NULL,
            stock NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (stock >= 0),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        ALTER TABLE materias_primas
        ADD COLUMN IF NOT EXISTS stock NUMERIC(10, 2) NOT NULL DEFAULT 0;
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recetas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            instrucciones TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            categoria_id INT REFERENCES categorias(id) ON DELETE CASCADE,
            receta_id INT REFERENCES recetas(id) ON DELETE SET NULL,
            nombre_es VARCHAR(100) NOT NULL,
            nombre_en VARCHAR(100) NOT NULL,
            precio NUMERIC(10, 2) NOT NULL,
            imagen_url VARCHAR(255) NOT NULL,
            disponible BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS receta_ingredientes (
            id SERIAL PRIMARY KEY,
            receta_id INT REFERENCES recetas(id) ON DELETE CASCADE,
            materia_prima_id INT REFERENCES materias_primas(id) ON DELETE RESTRICT,
            cantidad NUMERIC(10, 2) NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        DROP INDEX IF EXISTS ux_receta_ingredientes_producto_materia;
        ALTER TABLE receta_ingredientes DROP COLUMN IF EXISTS producto_id;
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_receta_ingredientes_receta_materia
        ON receta_ingredientes (receta_id, materia_prima_id);
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

@app.get("/api/admin-only")
def admin_only(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    return {"message": "Acceso permitido"}

@app.get("/admin", include_in_schema=False)
def admin_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "admin.html")
    return FileResponse(dashboard_path)



