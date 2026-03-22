# src/Config/version_route.py
from fastapi import APIRouter
from src.Config.version import CURRENT_VERSION

router = APIRouter(prefix="/config", tags=["Configuración"])

@router.get("/version")
def get_version():
    return {
        "version": CURRENT_VERSION,
        # Esta url se actualiza dependiendo de la release publicada
        # v1.0.7 → Release v1.0.7 → URL .../v1.0.7/Installer_Gestorex_v1.0.7.exe
        # v1.0.8 → Release v1.0.8 → URL .../v1.0.8/Installer_Gestorex_v1.0.8.exe -> para futura version
        "url": "https://github.com/mmedinafv/UIPATH/releases/download/v1.0.8/Installer_Gestorex_v1.0.8.exe"   
    }