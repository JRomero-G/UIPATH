from ..Models.recomendaciones_usuario_model import RecomendacionesUsuario
from ..ejemplo_flujo_ia_registro_infima import Infima
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..Controllers.usuarios_controller import (
    registrar_usuario,
    listar_usuarios,
    UsuarioCreate,
    listar_usuarios_no_admin,
)
from ..Auth.Usuario_auth import usuario_actual
from ..Models.usuarios_model import Usuario
from ..database import get_db
from PyQt5.QtWidgets import QComboBox

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


# Endpoint para listar usuarios no administradores
@router.get("/no-admin")
def listar_no_admin(db: Session = Depends(get_db)):
    usuarios = listar_usuarios_no_admin(db)
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


@router.post("/asignar")
def asignar_infimas_manual(
    asignaciones: list[dict],
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(usuario_actual),
):
    """
    asignaciones = [
        {"usuario_id": 1, "id_infima": 23},
        {"usuario_id": 2, "id_infima": 24},
    ]
    """
    objects = []
    for a in asignaciones:
        usuario_id = a.get("usuario_id")
        id_infima = a.get("id_infima")
        # Verificar que existan
        usuario = (
            db.query(Usuario)
            .filter(Usuario.id_usuario == usuario_id, Usuario.estado == "activo")
            .first()
        )
        infima = db.query(Infima).filter(Infima.id_infima == id_infima).first()
        if not usuario or not infima:
            continue
        # Evitar duplicados
        exists = (
            db.query(RecomendacionesUsuario)
            .filter(
                RecomendacionesUsuario.usuario_id == usuario_id,
                RecomendacionesUsuario.id_infima == id_infima,
            )
            .first()
        )
        if exists:
            continue
        objects.append(
            RecomendacionesUsuario(usuario_id=usuario_id, id_infima=id_infima)
        )

    if not objects:
        raise HTTPException(status_code=400, detail="No se asignaron ínfimas")

    db.bulk_save_objects(objects)
    db.commit()
    return {"mensaje": f"Asignadas {len(objects)} ínfimas"}
