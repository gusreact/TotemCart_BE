import os
import io
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

app = FastAPI(title="Backend TotemCart API")

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.dirname(UPLOAD_DIR)), name="static")

# Habilitar CORS para permitir llamadas desde React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint de prueba
@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Backend corriendo correctamente"}

# Endpoint para procesar y guardar imágenes a WebP
@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Procesamiento WebP
        output_buffer = io.BytesIO()
        image.save(output_buffer, format="WEBP", quality=80)
        output_buffer.seek(0)

        original_name = os.path.basename(file.filename or "upload")
        filename = f"{os.path.splitext(original_name)[0]}.webp"
        output_path = os.path.join(UPLOAD_DIR, filename)
        with open(output_path, "wb") as saved_file:
            saved_file.write(output_buffer.read())

        return {
            "status": "success",
            "filename": filename,
            "format": "WEBP",
            "url": f"/static/uploads/{filename}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))