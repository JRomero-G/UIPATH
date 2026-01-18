
"""
ejemplo_flujo_ia_registro_infima.py

EJEMPLO COMPLETO DEL FLUJO:

1. Datos obtenidos desde una página web (frontend / scraping / IA).
2. Análisis y filtrado mediante IA (simulado por reglas).
3. Normalización y validación de datos.
4. Registro final en la base de datos usando el controller registrar_infima.

Este archivo es DIDÁCTICO y está alineado con tu arquitectura Backend.
"""

from sqlalchemy.orm import Session
from datetime import date, datetime

# =========================
# MODELO SIMPLIFICADO (ejemplo)
# =========================
class Infima:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

# =========================
# PASO 1: DATOS CRUDOS (SALIDA DE IA / WEB)
# =========================
datos_extraidos_web = {
    "tipo_necesidad": "Equipos informáticos",
    "codigo_necesidad": "INF-EC-2025-001",
    "fecha_publicacion": "2025-01-10",
    "provincia_canton": "Pichincha - Quito",
    "descripcion_objeto_compra": "Adquisición de computadoras portátiles para personal administrativo",
    "fecha_limite_proformas": "2025-01-20 17:00",
    "entidad_contratante": "Ministerio de Educación",
    "entidad_contratante_url": "https://educacion.gob.ec",
    "direccion_entrega": "Av. Amazonas y Naciones Unidas",
    "contacto": "compras@educacion.gob.ec",
    "PAC": 18500.00
}

# =========================
# PASO 2: ANÁLISIS IA (SIMULADO)
# =========================
PALABRAS_CLAVE_VALIDAS = ["computadoras", "informáticos", "tecnología"]

def analisis_ia_aprueba(data: dict) -> bool:
    descripcion = data.get("descripcion_objeto_compra", "").lower()
    return any(palabra in descripcion for palabra in PALABRAS_CLAVE_VALIDAS)

# =========================
# PASO 3: NORMALIZACIÓN DE DATOS
# =========================
def preparar_datos_para_bd(data: dict) -> dict:
    return {
        "tipo_necesidad": data["tipo_necesidad"],
        "codigo_necesidad": data["codigo_necesidad"],
        "fecha_publicacion": date.fromisoformat(data["fecha_publicacion"]),
        "provincia_canton": data["provincia_canton"],
        "descripcion_objeto_compra": data["descripcion_objeto_compra"],
        "fecha_limite_proformas": datetime.fromisoformat(data["fecha_limite_proformas"]),
        "entidad_contratante": data["entidad_contratante"],
        "entidad_contratante_url": data["entidad_contratante_url"],
        "direccion_entrega": data["direccion_entrega"],
        "contacto": data["contacto"],
        "PAC": data["PAC"]
    }

# =========================
# PASO 4: CONTROLLER (IGUAL AL TUYO)
# =========================
def registrar_infima(db: Session, data: dict):
    infima = Infima(**data)
    print(f"✔ Infima registrada correctamente: {infima.codigo_necesidad}")
    return infima

# =========================
# FLUJO PRINCIPAL
# =========================
def flujo_principal(db: Session = None):
    if analisis_ia_aprueba(datos_extraidos_web):
        datos_finales = preparar_datos_para_bd(datos_extraidos_web)
        registrar_infima(db, datos_finales)
    else:
        print("✖ La IA descartó la infima por no cumplir criterios")

if __name__ == "__main__":
    flujo_principal()
