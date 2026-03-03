from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..Controllers.infima_controller import (
    listar_infimas_seleccionadas,
    registrar_infima,
    obtener_infima_por_codigo,
    listar_infimas,
    procesar_lote_infimas,
    listar_infimas_ingresadas,
    obtener_infimas_en_generacion_y_finalizadas,
    contador_de_infimas_en_generacion
)
from ..database import get_db

router = APIRouter(prefix="/infimas", tags=["Infimas"])


@router.post("/registro-masivo")
def registro_masivo(payload: dict, db: Session = Depends(get_db)):
    return procesar_lote_infimas(db, payload)


@router.post("/registrar_Una")
def registrar(data: dict, db: Session = Depends(get_db)):
    return registrar_infima(db, data)


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

# =================== Nuevo Endpoint: Visualizacion de infimas en generacion  ========================

@router.get("/contador-infimas-en-generacion") # contador
def contar_infimas_en_generacion(db: Session = Depends(get_db)):
    return contador_de_infimas_en_generacion(db) # ya en el contador se cuenta solo las que están en generación

# =================== Nuevo Endpoint: Visualizacion de infimas en generacion y finalizadas  ========================

@router.get("/infimas-en-generacion-y-finalizadas") #tabla 2 administracion
def mostrar_infimas_en_generacion_y_finalizadas(db: Session = Depends(get_db)):
    return obtener_infimas_en_generacion_y_finalizadas(db)