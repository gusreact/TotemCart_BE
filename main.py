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
from routers.pedido_estados import router as pedido_estados_router
from routers.payments import router as payments_router
from routers.roles import router as roles_router
from routers.users import router as users_router
from services.security import (
    ALGORITHM,
    SECRET_KEY,
    require_admin,
)

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="TotemCart API", lifespan=lifespan)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(pedido_estados_router)
app.include_router(catalog_router)
app.include_router(payments_router)

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
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            nombre_es VARCHAR(100) NOT NULL,
            nombre_en VARCHAR(100) NOT NULL,
            inmutable BOOLEAN NOT NULL DEFAULT FALSE
        );

        ALTER TABLE roles
        ADD COLUMN IF NOT EXISTS inmutable BOOLEAN NOT NULL DEFAULT FALSE;

        INSERT INTO roles (id, nombre_es, nombre_en)
        VALUES
            (1, 'Administrador', 'Administrator'),
            (2, 'Cocinero', 'Cook')
        ON CONFLICT (id) DO NOTHING;

        UPDATE roles SET inmutable = TRUE WHERE id IN (1, 2);

        SELECT setval(
            pg_get_serial_sequence('roles', 'id'),
            GREATEST((SELECT MAX(id) FROM roles), 1),
            TRUE
        );

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
            role_id SMALLINT NOT NULL DEFAULT 2 REFERENCES roles(id),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );

        ALTER TABLE usuarios
        ADD COLUMN IF NOT EXISTS role_id SMALLINT;

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'usuarios'
                  AND column_name = 'role'
            ) THEN
                UPDATE usuarios
                SET role_id = CASE
                    WHEN lower(trim(role)) IN ('admin', '1') THEN 1
                    ELSE 2
                END
                WHERE role_id IS NULL;
            END IF;
        END;
        $$;

        UPDATE usuarios SET role_id = 2 WHERE role_id IS NULL;
        ALTER TABLE usuarios ALTER COLUMN role_id SET DEFAULT 2;
        ALTER TABLE usuarios ALTER COLUMN role_id SET NOT NULL;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'usuarios_role_id_fkey'
                  AND conrelid = 'usuarios'::regclass
            ) THEN
                ALTER TABLE usuarios
                ADD CONSTRAINT usuarios_role_id_fkey
                FOREIGN KEY (role_id) REFERENCES roles(id);
            END IF;
        END;
        $$;

        ALTER TABLE usuarios DROP COLUMN IF EXISTS role;
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS unidades_medida (
            id SERIAL PRIMARY KEY,
            medida_es VARCHAR(50) NOT NULL UNIQUE,
            medida_en VARCHAR(50) NOT NULL UNIQUE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS materias_primas (
            id SERIAL PRIMARY KEY,
            nombre_es VARCHAR(100) NOT NULL,
            nombre_en VARCHAR(100) NOT NULL,
            unidad_medida_id INT NOT NULL REFERENCES unidades_medida(id) ON DELETE RESTRICT,
            stock NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (stock >= 0),
            stock_min NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (stock_min >= 0),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        ALTER TABLE materias_primas
        ADD COLUMN IF NOT EXISTS unidad_medida_id INT REFERENCES unidades_medida(id) ON DELETE RESTRICT;

        ALTER TABLE materias_primas
        ADD COLUMN IF NOT EXISTS nombre_es VARCHAR(100);

        ALTER TABLE materias_primas
        ADD COLUMN IF NOT EXISTS nombre_en VARCHAR(100);
        """
    )

    cursor.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'materias_primas'
                  AND column_name = 'unidad_medida'
            ) THEN
                INSERT INTO unidades_medida (medida_es, medida_en)
                SELECT DISTINCT unidad_medida, unidad_medida
                FROM materias_primas
                WHERE unidad_medida IS NOT NULL
                                ON CONFLICT DO NOTHING;

                UPDATE materias_primas mp
                                SET unidad_medida_id = (
                                        SELECT um.id
                                        FROM unidades_medida um
                                        WHERE um.medida_es = mp.unidad_medida
                                             OR um.medida_en = mp.unidad_medida
                                        ORDER BY (um.medida_es = mp.unidad_medida) DESC
                                        LIMIT 1
                                )
                                WHERE mp.unidad_medida_id IS NULL
                                    AND EXISTS (
                                        SELECT 1
                                        FROM unidades_medida um
                                        WHERE um.medida_es = mp.unidad_medida
                                             OR um.medida_en = mp.unidad_medida
                                    );
            END IF;
        END $$;

        ALTER TABLE materias_primas
        ALTER COLUMN unidad_medida_id SET NOT NULL;

        ALTER TABLE materias_primas
        DROP COLUMN IF EXISTS unidad_medida;
        """
    )

    cursor.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'materias_primas'
                  AND column_name = 'nombre'
            ) THEN
                UPDATE materias_primas
                SET nombre_es = COALESCE(NULLIF(nombre_es, ''), nombre);
            END IF;
        END $$;

        UPDATE materias_primas
        SET nombre_en = COALESCE(NULLIF(nombre_en, ''), nombre_es);

        ALTER TABLE materias_primas
        ALTER COLUMN nombre_es SET NOT NULL;

        ALTER TABLE materias_primas
        ALTER COLUMN nombre_en SET NOT NULL;

        ALTER TABLE materias_primas
        DROP COLUMN IF EXISTS nombre;
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
        ALTER TABLE materias_primas
        ADD COLUMN IF NOT EXISTS stock_min NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (stock_min >= 0);
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recetas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            instrucciones_es TEXT,
            instrucciones_en TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'recetas'
                  AND column_name = 'instrucciones'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'recetas'
                  AND column_name = 'instrucciones_es'
            ) THEN
                ALTER TABLE recetas RENAME COLUMN instrucciones TO instrucciones_es;
            END IF;
        END $$;

        ALTER TABLE recetas
        ADD COLUMN IF NOT EXISTS instrucciones_es TEXT;

        ALTER TABLE recetas
        ADD COLUMN IF NOT EXISTS instrucciones_en TEXT;
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            categoria_id INT REFERENCES categorias(id) ON DELETE CASCADE,
            categoria_sugerida INT REFERENCES categorias(id) ON DELETE SET NULL,
            receta_id INT REFERENCES recetas(id) ON DELETE SET NULL,
            nombre_es VARCHAR(100) NOT NULL,
            nombre_en VARCHAR(100) NOT NULL,
            precio NUMERIC(10, 2) NOT NULL,
            imagen_url VARCHAR(255) NOT NULL,
            tiempo_preparacion INTEGER,
            disponible BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        ALTER TABLE productos
        ADD COLUMN IF NOT EXISTS tiempo_preparacion INTEGER;
        """
    )

    cursor.execute(
        """
        ALTER TABLE productos
        ADD COLUMN IF NOT EXISTS categoria_sugerida INT
        REFERENCES categorias(id) ON DELETE SET NULL;
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS receta_ingredientes (
            id SERIAL PRIMARY KEY,
            receta_id INT REFERENCES recetas(id) ON DELETE CASCADE,
            materia_prima_id INT REFERENCES materias_primas(id) ON DELETE RESTRICT,
            cantidad NUMERIC(10, 2) NOT NULL,
            requerido BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    cursor.execute(
        """
        ALTER TABLE receta_ingredientes
        ADD COLUMN IF NOT EXISTS requerido BOOLEAN NOT NULL DEFAULT TRUE;
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pedido_estado (
            id SMALLINT PRIMARY KEY CHECK (id BETWEEN 1 AND 5),
            descripcion_es VARCHAR(50) NOT NULL,
            descripcion_en VARCHAR(50) NOT NULL
        );

        INSERT INTO pedido_estado (id, descripcion_es, descripcion_en)
        VALUES
            (1, 'Recibido', 'Received'),
            (2, 'En Preparación', 'In Preparation'),
            (3, 'Listo para retirar', 'Ready for pickup'),
            (4, 'Entregado', 'Delivered'),
            (5, 'Cancelado', 'Cancelled')
        ON CONFLICT (id) DO NOTHING;

        CREATE TABLE IF NOT EXISTS checkout_orders (
            id SERIAL PRIMARY KEY,
            external_reference VARCHAR(36) NOT NULL UNIQUE,
            pedido_codigo VARCHAR(7),
            pedido_estado_id SMALLINT NOT NULL DEFAULT 1
                REFERENCES pedido_estado(id),
            preference_id TEXT,
            total NUMERIC(12, 2) NOT NULL CHECK (total >= 0),
            currency VARCHAR(3) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'paid')),
            payment_id TEXT UNIQUE,
            payer_identification_number VARCHAR(50),
            created_at TIMESTAMP WITHOUT TIME ZONE
                DEFAULT timezone('America/Argentina/Buenos_Aires', NOW()),
            paid_at TIMESTAMP WITHOUT TIME ZONE,
            preparation_at TIMESTAMP WITHOUT TIME ZONE
        );

        ALTER TABLE checkout_orders
        ADD COLUMN IF NOT EXISTS pedido_codigo VARCHAR(7);

        ALTER TABLE checkout_orders
        ADD COLUMN IF NOT EXISTS pedido_estado_id SMALLINT NOT NULL DEFAULT 1
            REFERENCES pedido_estado(id);

        ALTER TABLE checkout_orders
        ADD COLUMN IF NOT EXISTS preparation_at TIMESTAMP WITHOUT TIME ZONE;

        ALTER TABLE checkout_orders
        ALTER COLUMN created_at SET DEFAULT
            timezone('America/Argentina/Buenos_Aires', NOW());

        CREATE UNIQUE INDEX IF NOT EXISTS ux_checkout_orders_pedido_codigo
        ON checkout_orders (pedido_codigo);

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_checkout_orders_pedido_codigo_format'
                  AND conrelid = 'checkout_orders'::regclass
            ) THEN
                ALTER TABLE checkout_orders
                ADD CONSTRAINT ck_checkout_orders_pedido_codigo_format
                CHECK (
                    pedido_codigo IS NULL
                    OR pedido_codigo ~ '^[A-Z0-9]{7}$'
                );
            END IF;
        END;
        $$;

        ALTER TABLE checkout_orders
        DROP COLUMN IF EXISTS payer_first_name,
        DROP COLUMN IF EXISTS payer_last_name;

        ALTER TABLE checkout_orders
        ADD COLUMN IF NOT EXISTS payer_identification_number VARCHAR(50);

        CREATE TABLE IF NOT EXISTS checkout_order_items (
            id SERIAL PRIMARY KEY,
            order_id INT NOT NULL REFERENCES checkout_orders(id) ON DELETE CASCADE,
            product_id INT NOT NULL,
            product_name VARCHAR(100) NOT NULL,
            quantity INT NOT NULL CHECK (quantity > 0),
            unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0)
        );

        CREATE TABLE IF NOT EXISTS checkout_order_ingredients (
            id SERIAL PRIMARY KEY,
            order_item_id INT NOT NULL
                REFERENCES checkout_order_items(id) ON DELETE CASCADE,
            materia_prima_id INT NOT NULL,
            quantity_per_product NUMERIC(10, 2) NOT NULL
                CHECK (quantity_per_product > 0)
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
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
):
    try:
        hashed = pwd_context.hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO usuarios (username, password_hash, nombre, role_id)
            VALUES (%s, %s, %s, 2)
            RETURNING id, username, nombre, role_id;
            """,
            (username, hashed, nombre),
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
    cursor.execute(
        """
        SELECT usuario.*, rol.nombre_es, rol.nombre_en,
               CASE usuario.role_id
                   WHEN 1 THEN 'administrador'
                   WHEN 2 THEN 'cocinero'
                   ELSE rol.nombre_es
               END AS role
        FROM usuarios AS usuario
        JOIN roles AS rol ON rol.id = usuario.role_id
        WHERE usuario.username = %s;
        """,
        (form_data.username,),
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Usuario o contraseña incorrectos"
        )

    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role_id": user["role_id"],
            "role": user["role"],
        }
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "username": user["username"],
        "nombre": user["nombre"],
        "role_id": user["role_id"],
        "role": user["role"],
        "role_es": user["nombre_es"],
        "role_en": user["nombre_en"],
    }

@app.get("/api/admin-only")
def admin_only(current_user: dict = Depends(require_admin)):
    return {"message": "Acceso permitido"}

@app.get("/admin", include_in_schema=False)
def admin_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "admin.html")
    return FileResponse(dashboard_path)
