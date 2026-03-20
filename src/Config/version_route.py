from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# aqui es de donde descargaremos las versiones de la aplicacion
@router.get("/version")
def get_version():
    return {
        "version": "1.1.0",
        "url": "https://tu-servidor.com/download/run.exe"
    }