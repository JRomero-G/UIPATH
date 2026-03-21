from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.Database.Controllers.palabra_clave_controller import (
    registrar_palabra_clave,
    listar_palabras_clave
)
from src.Database.database import get_db

router = APIRouter(prefix="/palabras-clave", tags=["Palabras Clave"])


@router.post("/")
def registrar(data: dict, db: Session = Depends(get_db)):
    return registrar_palabra_clave(db, data)


@router.get("/")
def listar(db: Session = Depends(get_db)):
    return listar_palabras_clave(db)
