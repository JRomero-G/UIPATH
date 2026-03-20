from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.Database.Controllers.usuarios_controller import (
    registrar_usuario,
    listar_usuarios,
    actualizar_usuario,
    inhabilitar_usuario,
    UsuarioCreate, # Esquema para crear usuarios
    UsuarioUpdate, # Esquema para actualizar usuarios
    obtener_usuario_por_id,
    listar_usuarios_no_admin,
    listar_empleados_activos,
)
from src.Database.Auth.Usuario_auth import usuario_actual
from src.Database.Models.usuarios_model import Usuario
from src.Database.database import get_db

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

#===================== RUTAS PARA CRUD==================================="

@router.post("/registro")
def registrar(data: UsuarioCreate, db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    if not current_user.es_admin:
        return {"error": "No autorizado debe ser administrador"}

    resultado = registrar_usuario(db, data)

    return resultado

@router.put("/actualizar/{id_usuario}")
def actualizar_datos_usuarios(id_usuario: int,data: UsuarioUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(usuario_actual)):
    if not current_user.es_admin:
        return {"error": "No autorizado debe ser administrador"}
    resultado =actualizar_usuario(db, id_usuario, data)

    if "error" in resultado:
        return resultado
    return resultado

@router.put("/desactivar-usuarios/{id_usuario}")
def desactivar_usuario(id_usuario: int, db: Session = Depends(get_db), current_user: Usuario = Depends(usuario_actual)):
    if not current_user.es_admin:
        return {"error": "No autorizado debe ser administrador"}

    resultado = inhabilitar_usuario(db,id_usuario)

    return resultado


# Endpoint para listar a todos usuarios
@router.get("/todos")
def listar(db: Session = Depends(get_db)):
    return  listar_usuarios(db)

# Endpoint para listar usuarios no administradores
@router.get("/empleados")
def listar_no_admin(db: Session = Depends(get_db), current_user: Usuario = Depends(usuario_actual)):
    if not current_user.es_admin:
        return {"error": "No autorizado debe ser administrador"}
    return listar_usuarios_no_admin(db)

@router.get("/empleados-activos")
def listar_empleados(db: Session = Depends(get_db), current_user: Usuario = Depends(usuario_actual)):
    if not current_user.es_admin:
        return {"error": "No autorizado dbe ser administrador"}
    return listar_empleados_activos(db)


# Endpoint para buscar un usuario
@router.get("/{id_usuario}")
def obtener_informacion_del_usuario_por_id(id_usuario: int, db: Session = Depends(get_db)):
    #Obtener usuario por id
    usuario = obtener_usuario_por_id(db,id_usuario)
    if not usuario:
        return ("Error:","Error al obtener usuarios o No hay usuarios registrados")
    
    return usuario