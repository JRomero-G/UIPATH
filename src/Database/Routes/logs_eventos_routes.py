from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Controllers.logs_eventos_controller import (
    registrar_log,
    listar_logs
)
from database import get_db

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.post("/")
def registrar(data: dict, db: Session = Depends(get_db)):
    return registrar_log(db, data)


@router.get("/")
def listar(db: Session = Depends(get_db)):
    return listar_logs(db)
