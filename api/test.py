import os
import io
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from PIL import Image
import vercel_blob

app = FastAPI(title="Admin Panel API - Tótem")

# Habilitar CORS para tu frontend en Vercel y desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Variables de Entorno
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-totem-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas de sesión

DATABASE_URL = os.getenv("DATABASE_URL")
BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# --- UTILIDADES DE SEGURIDAD ---
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
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception

# --- ENDPOINT DE LOGIN ---
@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db()
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

    access_token = create_access_token(data={"sub": user["username"]})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "username": user["username"],
        "nombre": user["nombre"]
    }

# --- ENDPOINT PROTEGIDO: CREAR CATEGORÍA ---
@app.post("/api/categorias", status_code=status.HTTP_201_CREATED)
async def crear_categoria_admin(
    nombre_es: str = Form(...),
    nombre_en: str = Form(...),
    orden: int = Form(1),
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)  # <- Exige el Token Bearer
):
    try:
        # 1. Convertir a WebP en memoria
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=80)
        
        # 2. Subir a Vercel Blob
        filename = f"categorias/cat_{nombre_es.lower().replace(' ', '_')}.webp"
        blob_res = vercel_blob.put(
            filename, 
            buffer.getvalue(), 
            options={"access": "public", "token": BLOB_TOKEN}
        )
        public_url = blob_res.get("url")

        # 3. Guardar en DB
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO categorias (nombre_es, nombre_en, orden, imagen_url)
            VALUES (%s, %s, %s, %s)
            RETURNING id, nombre_es, nombre_en, orden, imagen_url, created_at;
        """, (nombre_es, nombre_en, orden, public_url))
        nueva_cat = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status": "success",
            "message": f"Categoría creada por el usuario {current_user}",
            "data": nueva_cat
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))