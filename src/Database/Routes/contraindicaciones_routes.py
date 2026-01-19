from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Controllers.contraindicaciones_controller import (
    registrar_contraindicacion,
    listar_contraindicaciones
)
from database import get_db

router = APIRouter(
    prefix="/contraindicaciones",
    tags=["Contraindicaciones"]
)


@router.post("/")
def registrar(data: dict, db: Session = Depends(get_db)):
    return registrar_contraindicacion(db, data)


@router.get("/")
def listar(db: Session = Depends(get_db)):
    return listar_contraindicaciones(db)
