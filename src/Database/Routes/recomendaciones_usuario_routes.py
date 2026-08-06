from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.Database.Models.usuarios_model import Usuario
from src.Database.Controllers.recomendaciones_usuario_controller import (
    asignar_infimas_recomendadas_a_usuario_lote,
    asignar_infimas_recomendadas_a_usuario_individual,
    obtener_infimas_recomendadas_asignadas_del_usuario,
    obtener_infimas_asignadas_en_generacion_y_a_que_usuarios,
    obtener_infimas_asignadas_finalizadas_y_a_que_usuarios,
    obtener_infimas_asignadas_enviadas_y_a_que_usuarios,
    obtener_infimas_asignadas_y_a_que_usuarios,
    obtener_infimas_asignadas_y_a_que_usuarios_filtro,
    obtener_infimas_recomendadas_asignadas_finalizadas_del_usuario,
    obtener_infimas_recomendadas_asignadas_del_usuario2
)
from src.Database.Auth.Usuario_auth import usuario_actual
from src.Database.database import get_db

# Nuevas importaciones
from pydantic import BaseModel
from typing import List
from src.Database.Controllers.infima_controller import obtener_infimas_disponibles_admin

router = APIRouter(
    prefix="/recomendaciones-usuario", 
    tags=["Recomendaciones por Usuario"]
)

# asignacion multiple
class AsignacionRequest(BaseModel):
    usuario_id: int
    infimas: List[int]

# asignacion individual
class AsignacionIndividualRequest(BaseModel):
    usuario_id: int
    id_infima: int

#==================== RUTAS PARA ADMIN===================================

"""
Endpoint para que el ADMIN vea las ínfimas NO asignadas
Estas se mostrarán en la tabla con checkboxes
"""
@router.get("/admin/infimas-disponibles")
def infimas_para_admin(db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    # si el usuario actual no es dmin entonces no esta autorizado
    if not current_user.es_admin:
        return {"error": "No autorizado debe ser administrador"}
    return obtener_infimas_disponibles_admin(db)

#Nueva ruta para asignar infimas individualmente
@router.post("/admin/asignar-infima-individual")
def asignar_infima_unica(data: AsignacionIndividualRequest, db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    
    if not current_user.es_admin:
        return {"error":"No autorizado debe ser administrador"}
    
    resultado = asignar_infimas_recomendadas_a_usuario_individual(
        db,
        data.usuario_id,
        data.id_infima
    )

    if "error" in resultado:
        return resultado
    
    return resultado

# Nueva ruta para que el admin asigne ínfimas a un usuario
@router.post("/admin/asignar-infimas-multiples")
def asignar_infimas_multiples(data: AsignacionRequest,db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    
    if not current_user.es_admin:
        return {"error": "No autorizado debe ser administrador"}

    resultado = asignar_infimas_recomendadas_a_usuario_lote(
        db,
        data.usuario_id,
        data.infimas
    )

    if "error" in resultado:
        return resultado

    return resultado 

# ruta para infimas asignadas en etapa en generacion
@router.get("/admin/obtener-infimas-en-generacion-de-empleados")
def Obtener_infimas_en_generacion_empleados(db: Session = Depends(get_db), current_user: Usuario = Depends(usuario_actual)):
    return {
        "data": obtener_infimas_asignadas_en_generacion_y_a_que_usuarios(db)
    }
# ruta para infimas asignadas en etapa finalizada
@router.get("/admin/obtener-infimas-finalizada-de-empleados")
def Obtener_infimas_finalizadas_empleados(db: Session = Depends(get_db), current_user: Usuario = Depends(usuario_actual)):
    return {
        "data": obtener_infimas_asignadas_finalizadas_y_a_que_usuarios(db)
    }

# ruta para infimas asignadas en etapa enviada
@router.get("/admin/obtener-infimas-enviadas-de-empleados")
def obtener_infimas_asignadas_enviadas_y_a_que_usuarios(db: Session = Depends(get_db), current_user: Usuario = Depends(usuario_actual)):
        return {
        "data": obtener_infimas_asignadas_enviadas_y_a_que_usuarios(db)
    }

@router.get("/admin/obtener-infimas-asignadas")
def obtener_infimas_asignadas(db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    return {
        "data": obtener_infimas_asignadas_y_a_que_usuarios(db)
    }

@router.get("/admin/obtener-infimas-asignadas-por-usuario/{id_usuario}")
def obtener_infimas_asignadas_por_usuario(id_usuario: int,db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    return {
        "data": obtener_infimas_asignadas_y_a_que_usuarios_filtro(db, id_usuario)
    }

# ================= RUTAS DEL EMPLEADO ==================

# Nueva ruta para que un usuario vea sus ínfimas asignadas
@router.get("/mis-infimas")
def mis_infimas(db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    resultado = obtener_infimas_recomendadas_asignadas_del_usuario(db, current_user.id_usuario)

    if "error" in resultado:
        return resultado
    
    return resultado


# Nueva ruta para que un usuario vea sus ínfimas asignadas
@router.get("/mis-infimas2")
def mis_infimas2(db: Session = Depends(get_db)):
    resultado = obtener_infimas_recomendadas_asignadas_del_usuario2(db, 14)

    if "error" in resultado:
        return resultado
    
    return resultado

@router.get("/mis-infimas-finalizadas")
def mis_infimas(db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    return obtener_infimas_recomendadas_asignadas_finalizadas_del_usuario(db, current_user.id_usuario)

