# src/Config/version_route.py
from fastapi import APIRouter
from src.Config.version import CURRENT_VERSION

router = APIRouter(prefix="/config", tags=["Configuración"])

@router.get("/version")
def get_version():
    return {
        "version": CURRENT_VERSION,
        "url": "https://gestorex-desarrollo.onrender.com/download/Installer_Gestorex.exe"
        # Esta URL la actualizaremos cuando implementes la descarga
    }