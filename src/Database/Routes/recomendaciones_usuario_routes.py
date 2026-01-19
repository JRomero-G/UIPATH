from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Models.usuarios_model import Usuario
from Controllers.recomendaciones_usuario_controller import asignar_infimas_a_usuarios,obtener_infimas_del_usuario
from Auth.Usuario_auth import usuario_actual

from database import get_db

router = APIRouter(
    prefix="/recomendaciones-usuario",
    tags=["Recomendaciones por Usuario"]
)

@router.post("/asignar-automaticamente")
def asignar_infimas(
    max_por_usuario: int = 15,
    db: Session = Depends(get_db)
):
    return asignar_infimas_a_usuarios(db, max_por_usuario)

@router.get("/mis-infimas")
def mis_infimas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(usuario_actual)
):
    return obtener_infimas_del_usuario(db, current_user.id_usuario)
