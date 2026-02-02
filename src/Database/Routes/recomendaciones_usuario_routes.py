from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..Models.usuarios_model import Usuario
from ..Controllers.recomendaciones_usuario_controller import (
    asignar_infimas_a_usuarios,
    obtener_infimas_del_usuario,
)
from ..Auth.Usuario_auth import usuario_actual
from ..database import get_db

router = APIRouter(
    prefix="/recomendaciones-usuario", tags=["Recomendaciones por Usuario"]
)


# =========================
# ASIGNAR ÍNFIMAS DESDE LA UI
# =========================
@router.post("/asignar")
def asignar_infimas(
    asignaciones: list[dict],
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(usuario_actual),
):
    # Solo admins pueden asignar
    if not current_user.es_admin:
        raise HTTPException(status_code=403, detail="No autorizado")

    return asignar_infimas_a_usuarios(db, asignaciones_ui=asignaciones)


# =========================
# OBTENER MIS ÍNFIMAS
# =========================
@router.get("/mis-infimas")
def mis_infimas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(usuario_actual),
):
    infimas = obtener_infimas_del_usuario(db, current_user.id_usuario)

    return [
        {
            "id_infima": i.id_infima,
            "titulo": i.titulo,
            "fecha_publicacion": i.fecha_publicacion,
        }
        for i in infimas
    ]
