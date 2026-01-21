from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..Controllers.infima_controller import (
    registrar_infima,
    obtener_infima_por_codigo,
    listar_infimas,
    procesar_lote_infimas,
    listar_infimas_seleccionadas
)
from ..database import get_db

router = APIRouter(prefix="/infimas", tags=["Infimas"])


@router.post("/registro-masivo")
def registro_masivo(payload: dict, db: Session = Depends(get_db)):
    return procesar_lote_infimas(db, payload)


@router.post("/")
def registrar(data: dict, db: Session = Depends(get_db)):
    return registrar_infima(db, data)


@router.get("/")
def listar(db: Session = Depends(get_db)):
    return listar_infimas(db)

#solo infimas seleccionadas
@router.get("/seleccionadas")
def listar_seleccionadas(db: Session = Depends(get_db)):
    return listar_infimas_seleccionadas(db)

@router.get("/codigo/{codigo}")
def obtener_por_codigo(codigo: str, db: Session = Depends(get_db)):
    return obtener_infima_por_codigo(db, codigo)
