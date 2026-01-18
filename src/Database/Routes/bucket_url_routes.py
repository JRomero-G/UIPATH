from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Controllers.bucket_url_controller import (
    registrar_bucket_url,
    listar_bucket_urls,
    listar_bucket_urls_por_codigo
)
from database import get_db

router = APIRouter(prefix="/bucket-url", tags=["Bucket URL"])


@router.post("/")
def registrar(data: dict, db: Session = Depends(get_db)):
    return registrar_bucket_url(db, data)


@router.get("/")
def listar(db: Session = Depends(get_db)):
    return listar_bucket_urls(db)


@router.get("/{codigo_necesidad}")
def listar_por_codigo(codigo_necesidad: str, db: Session = Depends(get_db)):
    return listar_bucket_urls_por_codigo(db, codigo_necesidad)
