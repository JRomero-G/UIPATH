from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..Controllers.usuarios_controller import registrar_usuario, listar_usuarios, UsuarioCreate
from ..Auth.Usuario_auth import usuario_actual
from ..Models.usuarios_model import Usuario
from ..database import get_db

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

# Endpoint para registrar usuario
@router.post("/")
def registrar(data: UsuarioCreate, db: Session = Depends(get_db)):
    usuario = registrar_usuario(db, data)
    return {
        "id": usuario.id_usuario,
        "usuario": usuario.usuario,
        "nombre": usuario.nombre,
        "correo": usuario.correo,
        "telefono": usuario.telefono,
        "es_admin": usuario.es_admin,
    }

# Endpoint para listar usuarios
@router.get("/")
def listar(db: Session = Depends(get_db)):
    usuarios = listar_usuarios(db)
    return [
        {
            "id": u.id_usuario,
            "usuario": u.usuario,
            "nombre": u.nombre,
            "correo": u.correo,
            "telefono": u.telefono,
            "es_admin": u.es_admin,
        }
        for u in usuarios
    ]

# Endpoint para ver perfil propio
@router.get("/perfil")
def perfil(current_user: Usuario = Depends(usuario_actual)):
    return {
        "id": current_user.id_usuario,
        "usuario": current_user.usuario,
        "nombre": current_user.nombre,
        "correo": current_user.correo,
        "telefono": current_user.telefono,
        "es_admin": current_user.es_admin,
    }
