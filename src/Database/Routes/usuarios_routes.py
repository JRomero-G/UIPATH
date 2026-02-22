from ..Models.recomendaciones_usuario_model import RecomendacionesUsuario
from ..ejemplo_flujo_ia_registro_infima import Infima
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..Controllers.usuarios_controller import (
    registrar_usuario,
    listar_usuarios,
    UsuarioCreate,
    obtener_usuario_por_id,
    listar_usuarios_no_admin,
)
from ..Auth.Usuario_auth import usuario_actual
from ..Models.usuarios_model import Usuario
from ..database import get_db
from PyQt5.QtWidgets import QComboBox

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


# Endpoint para registrar usuario
@router.post("/registro")
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


# Endpoint para listar a todos usuarios
@router.get("/todos")
def listar(db: Session = Depends(get_db)):
    return  listar_usuarios(db)

# Endpoint para listar usuarios no administradores
@router.get("/empleados")
def listar_no_admin(db: Session = Depends(get_db), 
                    current_user: Usuario = Depends(usuario_actual)):
    if not current_user.es_admin:
        return {"error": "No autorizado debe ser administrador"}
    return listar_usuarios_no_admin(db)

# Endpoint para buscar un usuario
@router.get("/{id_usuario}")
def obtener_usuario_por_id(id_usuario: int, db: Session = Depends(get_db)):
    #Obtener usuario por id
    usuario = obtener_usuario_por_id(db,id_usuario)
    if not usuario:
        return ("Error:","Error al obtener usuarios o No hay usuarios registrados")
    
    return usuario