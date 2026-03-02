from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..Models.infima_model import Infima
# Nuevas importaciones
from ..Models.recomendaciones_usuario_model import RecomendacionesUsuario
from sqlalchemy import not_

def registrar_infima(db: Session, data: dict):
    infima = Infima(
        tipo_necesidad=data.get("tipo_necesidad"),
        codigo_necesidad=data.get("codigo_necesidad"),
        fecha_publicacion=data.get("fecha_publicacion"),
        provincia_canton=data.get("provincia_canton"),
        descripcion_objeto_compra=data.get("descripcion_objeto_compra"),
        fecha_limite_proformas=data.get("fecha_limite_proformas"),
        entidad_contratante=data.get("entidad_contratante"),
        entidad_contratante_url=data.get("entidad_contratante_url"),
        direccion_entrega=data.get("direccion_entrega"),
        contacto=data.get("contacto"),
        PAC=data.get("PAC"),
    )
    db.add(infima)
    db.commit()
    db.refresh(infima)
    return infima

# FUNCIONES QUE PROBABLEMENTE NO SE UTILICEN 

# Ya que la IA enviara los datos por lotes, inicialmente de los 100 primeros
# registros es probable que solo se necesiten registrar 20-40 infimas que cumplan
# con los requisitos previos
def procesar_lote_infimas(db: Session, payload: dict):
    infimas_creadas = []
    errores = []

    for data in payload.get("infimas", []):
        try:
            infima = Infima(
                tipo_necesidad=data.get("tipo_necesidad"),
                codigo_necesidad=data.get("codigo_necesidad"),
                fecha_publicacion=data.get("fecha_publicacion"),
                provincia_canton=data.get("provincia_canton"),
                descripcion_objeto_compra=data.get("descripcion_objeto_compra"),
                fecha_limite_proformas=data.get("fecha_limite_proformas"),
                entidad_contratante=data.get("entidad_contratante"),
                entidad_contratante_url=data.get("entidad_contratante_url"),
                direccion_entrega=data.get("direccion_entrega"),
                contacto=data.get("contacto"),
                PAC=data.get("PAC"),
            )
            db.add(infima)
            infimas_creadas.append(infima)

        except Exception as e:
            errores.append(
                {"codigo_necesidad": data.get("codigo_necesidad"), "error": str(e)}
            )

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        return {"status": "error", "detalle": "Error de integridad", "error": str(e)}

    return {
        "status": "ok",
        "total_recibidas": len(payload.get("infimas", [])),
        "registradas": len(infimas_creadas),
        "errores": errores,
    }


def listar_infimas(db: Session):
    return db.query(Infima).all()


def listar_infimas_seleccionadas(db: Session):
    return db.query(Infima).filter(Infima.etapa == "seleccionada").all()


def listar_infimas_ingresadas(db: Session):
    return db.query(Infima).filter(Infima.etapa == "ingresada").all()


def obtener_infima_por_codigo(db: Session, codigo: str):
    return db.query(Infima).filter(Infima.codigo_necesidad == codigo).first()

# =================== Nuevo Controlador  ========================

# Obtener las ínfimas que no han sido asignadas a ningún usuario cargaran en la tabla de administración
def obtener_infimas_disponibles_admin(db: Session):

    # subconsulta para ínfimas ya asignadas, se busca explícitamente que columna de la subconsulta usar
    subquery = (
        db.query(RecomendacionesUsuario.id_infima)
        .subquery()
    )

    # Dame todas las ínfimas que NO estén en recomendaciones_usuario
    return (
        db.query(Infima)
        .filter(
            not_(Infima.id_infima.in_(subquery)),
            Infima.etapa == "seleccionada",
            Infima.PAC > 0,
            Infima.nivel_de_oportunidad >=1 and Infima.nivel_de_oportunidad <=3
            #nuevas condiciones
            # Infima.PAC > 0
            # Infima.etapa == "seleccionada"
            # Infima
        )
        .order_by(Infima.fecha_publicacion.desc())
        .all()
    )

# Obtener las ínfimas que están en generación o finalizadas para mostrar en el dashboard del administrador
def obtener_infimas_en_generacion_y_finalizadas(db: Session):

    return(
        db.query(Infima)
        .filter(
            Infima.etapa.in_(["en generacion","finalizada"])
        )
        # Mostrar las infimas en generacion primero y luego las finalizadas
        .order_by(
            Infima.etapa.desc(),  # "en generacion" > "finalizada"
        )
    )

# Cargar infimas en etapa de engeneracion para mostrar en un contador o una tabla mientras la IA las procesa
# estas infimas seran las que ya un usuario tiene asignadas y el mismo paso a alisar por la IA
# mientras la IA las procesa, el usuario puede ver cuantas infimas están en proceso de generación 
# y cuales son para tener una idea del progreso general del sistema
def obtener_infimas_en_generacion(db: Session):
    return(
        db.query(Infima)
        .filter(Infima.etapa == "en generacion")
    )

# obtenemos las infimas totales como numero 
def contador_de_infimas_en_generacion(db: Session):
    return(
        db.query(Infima)
        .filter(Infima.etapa == "en generacion")
        .count()
    )
