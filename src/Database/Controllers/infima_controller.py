from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.Database.Models.infima_model import Infima
from src.Database.Models.evaluacion_model import Evaluacion
# Nuevas importaciones
from src.Database.Models.recomendaciones_usuario_model import RecomendacionesUsuario
from sqlalchemy import not_, or_

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
            #Infima.nivel_de_oportunidad >=1 and Infima.nivel_de_oportunidad <=3
            #nuevas condiciones
            # Infima.PAC > 0
            # Infima.etapa == "seleccionada"
            # Infima
        )
        .order_by(Infima.fecha_publicacion.desc())
        .limit(15)
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

def actualizar_infimas_para_analisis(db: Session, id_infima = int):
    infima = (db.query(Infima).filter(Infima.id_infima == id_infima).first())

    if not infima:
        return {"error": "Infima no encontrada"}
    
    try:
        
        infima.etapa = "en generacion"
        db.commit()
        db.refresh(infima)
        return {
        "id_infima": id_infima,
        "etapa": "en generacion",
        "mensaje": "Ínfima actualizada a 'en generacion'"
        }

    except IntegrityError as e:
        db.rollback()
        return {"error": str(e)}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    

def actualizar_infimas_a_enviadas(db: Session, id_infima = int):
    infima = (db.query(Infima).filter(Infima.id_infima == id_infima).first())

    if not infima:
        return {"error": "Infima no encontrada"}
    
    try:
        
        infima.etapa = "enviada"
        db.commit()
        db.refresh(infima)
        return {
        "id_infima": id_infima,
        "etapa": "enviada",
        "mensaje": "Ínfima actualizada a 'enviada'"
        }

    except IntegrityError as e:
        db.rollback()
        return {"error": str(e)}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}

#elimnamos infimas de manera permanente e irreversible
def eliminar_infima_permanentemente(db: Session, id_infima: int):

    print("Intentando eliminar:", id_infima)

    infima = db.query(Infima).filter(Infima.id_infima == id_infima).first()

    if not infima:
        return {"error": "Ínfima no encontrada"}

    codigo_necesidad = infima.codigo_necesidad

    try:

        # eliminar recomendaciones
        recomendaciones_eliminadas = (
            db.query(RecomendacionesUsuario)
            .filter(RecomendacionesUsuario.id_infima == id_infima)
            .delete(synchronize_session=False)
        )

        #  eliminar evaluaciones
        evaluaciones_eliminadas = (
            db.query(Evaluacion)
            .filter(Evaluacion.codigo_necesidad == codigo_necesidad)
            .delete(synchronize_session=False)
        )

        # eliminar
        db.delete(infima)

        db.commit()

        return {
            "success": True,
            "mensaje": f"Ínfima '{codigo_necesidad}' eliminada",
            "recomendaciones_eliminadas": recomendaciones_eliminadas,
            "Eliminadas de evaluaciones": evaluaciones_eliminadas
        }

    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    
# Asigna individualmente cada ínfima a un usuario específico (manual por admin)
def asignar_infimas_recomendadas_a_usuario_individual(db: Session,usuario_id: int,id_infima: int):

    # Crear registros de asignación
    asignacion = RecomendacionesUsuario(id_infima=id_infima,usuario_id=usuario_id)
    

    # Guardar en la base de datos
    try:
        db.add(asignacion)
        db.commit()
        db.refresh(asignacion)# Vuelve a consultar el registro recién insertado

    except IntegrityError:
        db.rollback()

        return {
            "error": "Conflicto: Infima ya fue asignada (error de integridad)"
        }

    return {
        "ID de la asignacion": asignacion.id,
        "ID del usuario": usuario_id,
        "ID de la infima asignada": id_infima,
        "mensaje": "Infima asignada Correctamente"
    }

# OBTENER INFIMAS RECHAZADAS
def obtener_infimas_rechazadas(db: Session):
    
    resultado = (    db.query(
            Infima.codigo_necesidad,
            Infima.etapa,
            Infima.descripcion_objeto_compra,
            Infima.fecha_limite_proformas,
            Infima.entidad_contratante_url
        )
        # Filtramos por etapa
        .filter(Infima.etapa == "no seleccionada")
        # Ordenamos por fecha limite de proformas (las mas proximas a vencer)
        .order_by(Infima.fecha_limite_proformas.asc())
        .limit(50)
        .all()
    )
    
    #if resultado:
        #print("Campos consultados Rechazadas: ",resultado[0]._fields)
    
    return [
        {
            "codigo_necesidad": r.codigo_necesidad,
            "etapa": r.etapa,
            "descripcion_objeto_compra": r.descripcion_objeto_compra,
            "fecha_limite_proformas": r.fecha_limite_proformas,
            "entidad_contratante_url": r.entidad_contratante_url
        }

        for r in resultado
    ]

# OBTENER LAS EVALUACIONES DE LAS INFIMAS POR CODIGO DE NECESIDAD
def obtener_evaluacion_de_infimas_por_codigo(db: Session, codigo_necesidad: str):
    resultado = (
        db.query(
            Evaluacion.codigo_necesidad,
            Evaluacion.justificacion
            )
        .filter(Evaluacion.codigo_necesidad == codigo_necesidad)
        .first()
    )

    if not resultado:
        return {"error": "No se encontró evaluación para el código de necesidad proporcionado"}

    return {
        "codigo_necesidad": resultado.codigo_necesidad,
        "justificacion": resultado.justificacion
    }
