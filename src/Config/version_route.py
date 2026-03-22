# src/Config/version_route.py
from fastapi import APIRouter
from src.Config.version import CURRENT_VERSION

router = APIRouter(prefix="/config", tags=["Configuración"])

GITHUB_REPO = "mmedinafv/UIPATH"

@router.get("/version")
def get_version():
    return {
        "version": CURRENT_VERSION,
        "tag": f"v{CURRENT_VERSION}",
        "filename": f"Installer_Gestorex_v{CURRENT_VERSION}.exe",
        "repo": GITHUB_REPO
    }