import uvicorn
from api.upload_file_in_local_storage import app

if __name__ == "__main__":
    # Levanta el servidor local con Hot-Reload (se actualiza solo al guardar)
    uvicorn.run("api.index:app", host="127.0.0.1", port=8000, reload=True)