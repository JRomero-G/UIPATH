# src/Config/version_route.py
from fastapi import APIRouter
from src.Config.version import CURRENT_VERSION

router = APIRouter(prefix="/config", tags=["Configuración"])

@router.get("/version")
def get_version():
    return {
        "version": CURRENT_VERSION,
        "url": "https://github.com/TU_USUARIO/TU_REPO/releases/download/v1.0.7/Installer_Gestorex_v1.0.7.exe"
    }