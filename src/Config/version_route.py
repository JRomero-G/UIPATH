# src/Config/version_route.py
from fastapi import APIRouter
from src.Config.version import CURRENT_VERSION

router = APIRouter(prefix="/config", tags=["Configuración"])

@router.get("/version")
def get_version():
    return {
        "version": CURRENT_VERSION,
        "url": "https://drive.google.com/uc?export=download&id=1oW-a486Cd2E2jnvge10LLwYGIV7pde87&confirm=t"
    }