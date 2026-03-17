from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..Controllers.infima_controller import (
    listar_infimas_seleccionadas,
    registrar_infima,
    obtener_infima_por_codigo,
    listar_infimas,
    procesar_lote_infimas,
    listar_infimas_ingresadas,
    obtener_infimas_disponibles_admin,
    obtener_infimas_en_generacion_y_finalizadas,
    contador_de_infimas_en_generacion,
    actualizar_infimas_para_analisis,
    eliminar_infima_permanentemente,
    obtener_infimas_rechazadas
)

from ..Models.usuarios_model import Usuario
from ..Auth.Usuario_auth import usuario_actual
from ..database import get_db

router = APIRouter(prefix="/infimas", tags=["Infimas"])


@router.get("/Todas")
def listar_Todas(db: Session = Depends(get_db)):
    return listar_infimas(db)


@router.get("/seleccionadas")
def listar_Seleccionada(db: Session = Depends(get_db)):
    return listar_infimas_seleccionadas(db)


@router.get("/ingresadas")
def listar_Ingresadas(db: Session = Depends(get_db)):
    return listar_infimas_ingresadas(db)


@router.get("/codigo/{codigo}")
def obtener_por_codigo(codigo: str, db: Session = Depends(get_db)):
    return obtener_infima_por_codigo(db, codigo)

# =================== Nuevo Endpoint: Visualizacion de infimas disponibles para admin  ========================
@router.get("/infimas-disponibles")
def obtener_infimas_disponibles_admin_endpoint(db: Session = Depends(get_db)):
    return obtener_infimas_disponibles_admin(db)

# =================== Nuevo Endpoint: Visualizacion de infimas en generacion  ========================

@router.get("/contador-infimas-en-generacion") # contador
def contar_infimas_en_generacion(db: Session = Depends(get_db)):
    return contador_de_infimas_en_generacion(db) # ya en el contador se cuenta solo las que están en generación

# =================== Nuevo Endpoint: Visualizacion de infimas en generacion y finalizadas  ========================

@router.get("/infimas-en-generacion-y-finalizadas") #tabla 2 administracion
def mostrar_infimas_en_generacion_y_finalizadas(db: Session = Depends(get_db)):
    return obtener_infimas_en_generacion_y_finalizadas(db)

# ==================== Actualzar infimas a en generacion ===============================
@router.patch("/analizar-infimas/{id_infima}")
def analizar_infimas(db: Session = Depends(get_db),id_infima = int):
    resultado = actualizar_infimas_para_analisis(db,id_infima)
    return resultado

@router.delete("/eliminar-infimas/{id_infima}")
def eliminar_infimas(id_infima: int,db: Session = Depends(get_db)):

    resultado = eliminar_infima_permanentemente(db,id_infima)
    return resultado
    

#INFIMAS RECHAZADAS
@router.get("/obtener-infimas-rechazadas")
def obtener_infimas_asignadas(db: Session = Depends(get_db),current_user: Usuario = Depends(usuario_actual)):
    if current_user.es_admin:
        return {
            "data": obtener_infimas_rechazadas(db)
        }
    else:
        return {"error": "Acceso no Autorizado"}
