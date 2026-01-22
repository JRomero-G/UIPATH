from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..Controllers.evaluacion_controller import registrar_evaluacion, listar_evaluaciones
from ..database import get_db

router = APIRouter(prefix="/evaluaciones", tags=["Evaluaciones"])


@router.post("/")
def registrar(data: dict, db: Session = Depends(get_db)):
    return registrar_evaluacion(db, data)


@router.get("/")
def listar(db: Session = Depends(get_db)):
    return listar_evaluaciones(db)
