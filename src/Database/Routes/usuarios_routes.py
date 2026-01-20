from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..Controllers.usuarios_controller import registrar_usuario, listar_usuarios
from ..Auth.Usuario_auth import usuario_actual
from ..Models.usuarios_model import Usuario
from ..database import get_db

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.post("/")
def registrar(data: dict, db: Session = Depends(get_db)):
    return registrar_usuario(db, data)


@router.get("/")
def listar(db: Session = Depends(get_db)):
    return listar_usuarios(db)


@router.get("/perfil")
def perfil(current_user: Usuario = Depends(usuario_actual)):
    return current_user
