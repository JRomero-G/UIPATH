from sqlalchemy.orm import Session
from src.Database.Models.recomendaciones_usuario_model import RecomendacionesUsuario
from src.Database.Models.infima_model import Infima
from src.Database.Models.usuarios_model import Usuario
# Nueva importacion
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_


# ================= Nuevos Controladores ===============

# Asigna múltiples ínfimas a un usuario específico (manual por admin)
def asignar_infimas_recomendadas_a_usuario_lote(db: Session,usuario_id: int,lista_infimas: list[int]):

    # Validar usuario
    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.id_usuario == usuario_id,
            Usuario.estado == "activo"
        )
        .first()
    )

    if not usuario:
        return {
            "error": "Usuario no existe o está inactivo"
        }

    # Verificar que las ínfimas existen
    infimas_existentes = (
        db.query(Infima.id_infima)
        .filter(Infima.id_infima.in_(lista_infimas))
        .all()
    )

    ids_existentes = {i[0] for i in infimas_existentes}

    if not ids_existentes:
        return {
            "error": "Las ínfimas no existen"
        }

    # Ver qué ínfimas ya están asignadas
    ya_asignadas = (
        db.query(RecomendacionesUsuario.id_infima)
        .filter(RecomendacionesUsuario.id_infima.in_(ids_existentes))
        .all()
    )

    ids_asignadas = {i[0] for i in ya_asignadas}

    # Filtrar solo válidas 
    infimas_para_asignar = [
        i for i in ids_existentes if i not in ids_asignadas
    ]

    if not infimas_para_asignar:
        return {
            "mensaje": "Todas las ínfimas ya estaban asignadas"
        }

    # Crear registros de asignación
    asignaciones = [
        RecomendacionesUsuario(
            id_infima=id_infima,
            usuario_id=usuario_id
        )
        for id_infima in infimas_para_asignar
    ]

    # Guardar en la base de datos
    try:
        db.add_all(asignaciones)
        db.commit()

    except IntegrityError:
        db.rollback()

        return {
            "error": "Conflicto: alguna ínfima ya fue asignada"
        }

    return {
        "usuario_id": usuario_id,
        "total_asignadas": len(asignaciones),
        "infimas": infimas_para_asignar
    }


# =================== Asignasion Individual =============================

# Asigna individualmente cada ínfima a un usuario específico (manual por admin)
def asignar_infimas_recomendadas_a_usuario_individual(db: Session,usuario_id: int,id_infima: int):

    # Validar usuario
    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.id_usuario == usuario_id,
            Usuario.estado == "activo"
        )
        .first()
    )

    if not usuario:
        return {
            "error": "Usuario no existe o está inactivo"
        }

    # Verificar que las ínfimas existen
    infima_existente = (
        db.query(Infima.id_infima)
        .filter(Infima.id_infima == id_infima)
        .first()
    )

    if not infima_existente:
        return {
            "error": "La ínfima no existe"
        }

    # Ver qué ínfimas ya están asignadas
    ya_asignada = (
        db.query(RecomendacionesUsuario.id_infima)
        .filter(RecomendacionesUsuario.id_infima == id_infima)
        .first()
    )

    if ya_asignada:
        return {"error": "Infimas ya esta asignada a otro usuario"}

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


# Devuelve las ínfimas asignadas a un usuario específico 
def obtener_infimas_recomendadas_asignadas_del_usuario(db: Session,usuario_id: int):
    return (
        db.query(Infima)
        .join(RecomendacionesUsuario)
        .filter(RecomendacionesUsuario.usuario_id == usuario_id
        ,Infima.etapa != "en generacion")
        .order_by(Infima.fecha_publicacion.desc())
        .limit(20)
        .all()
    )

def obtener_infimas_recomendadas_asignadas_finalizadas_del_usuario(db: Session,usuario_id: int):
    return (
        db.query(Infima)
        .join(RecomendacionesUsuario)
        .filter(RecomendacionesUsuario.usuario_id == usuario_id
        ,Infima.etapa == "finalizada")
        .order_by(Infima.fecha_publicacion.desc())
        .all()
    )

# =============== INFIMAS ASIGNADAS Y A QUIEN SE ASIGNARON ============================

# INFIMAS EN ETAPA EN GENERACION
def obtener_infimas_asignadas_en_generacion_y_a_que_usuarios(db: Session):
    resultado = (
        db.query(
            Usuario.usuario,
            Usuario.nombre,
            Infima.codigo_necesidad,
            Infima.descripcion_objeto_compra,
            Infima.fecha_limite_proformas,
        )
        .join(RecomendacionesUsuario, Usuario.id_usuario == RecomendacionesUsuario.usuario_id)
        .join(Infima, Infima.id_infima == RecomendacionesUsuario.id_infima)
        # Filtramos por etapa
        .filter(Infima.etapa == "en generacion")
        # Ordenamos por fecha limite de proformas (las mas proximas a vencer)
        .order_by(Infima.fecha_limite_proformas.asc())
        .all()
    )

    return [
        {
            "usuario": r.usuario,
            "nombre": r.nombre,
            "codigo_necesidad": r.codigo_necesidad,
            "descripcion_objeto_compra": r.descripcion_objeto_compra,
            "fecha_limite_proformas": r.fecha_limite_proformas,
        }
        for r in resultado
    ]


# INFIMAS EN ETAPA FINALIZADA
def obtener_infimas_asignadas_finalizadas_y_a_que_usuarios(db: Session):
    resultado = (
        db.query(
            Usuario.usuario,
            Usuario.nombre,
            Infima.codigo_necesidad,
            Infima.descripcion_objeto_compra,
            Infima.fecha_limite_proformas,
        )
        .join(RecomendacionesUsuario, Usuario.id_usuario == RecomendacionesUsuario.usuario_id)
        .join(Infima, Infima.id_infima == RecomendacionesUsuario.id_infima)
        # Filtramos por etapa
        .filter(Infima.etapa == "finalizada")
        # Ordenamos por fecha limite de proformas (las mas proximas a vencer)
        .order_by(Infima.fecha_limite_proformas.asc())
        .all()
    )
    
    return [
        {
            "usuario": r.usuario,
            "nombre": r.nombre,
            "codigo_necesidad": r.codigo_necesidad,
            "descripcion_objeto_compra": r.descripcion_objeto_compra,
            "fecha_limite_proformas": r.fecha_limite_proformas,
        }
        for r in resultado
    ]


# INFIMAS EN ETAPA ENVIADA
def obtener_infimas_asignadas_enviadas_y_a_que_usuarios(db: Session, etapa: str = "enviada"):
    resultado = (
        db.query(
            Usuario.usuario,
            Usuario.nombre,
            Infima.codigo_necesidad,
            Infima.descripcion_objeto_compra,
            Infima.fecha_limite_proformas,
        )
        .join(RecomendacionesUsuario, Usuario.id_usuario == RecomendacionesUsuario.usuario_id)
        .join(Infima, Infima.id_infima == RecomendacionesUsuario.id_infima)
        # Filtramos por etapa
        .filter(Infima.etapa == etapa)
        # Ordenamos por fecha limite de proformas (las mas proximas a vencer)
        .order_by(Infima.fecha_limite_proformas.asc())
        .all()
    )

    return [
        {
            "usuario": r.usuario,
            "nombre": r.nombre,
            "codigo_necesidad": r.codigo_necesidad,
            "descripcion_objeto_compra": r.descripcion_objeto_compra,
            "fecha_limite_proformas": r.fecha_limite_proformas,
        }
        for r in resultado
    ]


# ETAPAS EN GENERACION Y FINALIZADAS
def obtener_infimas_asignadas_y_a_que_usuarios(db: Session):
    
    resultado = (    db.query(
            Usuario.usuario,
            Usuario.nombre,
            Infima.codigo_necesidad,
            Infima.etapa,
            Infima.entidad_contratante_url,
            Infima.descripcion_objeto_compra,
            Infima.fecha_limite_proformas,
        )
        .join(RecomendacionesUsuario, Usuario.id_usuario == RecomendacionesUsuario.usuario_id)
        .join(Infima, Infima.id_infima == RecomendacionesUsuario.id_infima)
        # Filtramos por etapa
        .filter(
            or_(
                Infima.etapa == "en generacion",
                Infima.etapa == "finalizada"
            )
        )
        # Ordenamos por fecha limite de proformas (las mas proximas a vencer)
        .order_by(Infima.fecha_limite_proformas.asc())
        .all()
    )
    
    if resultado:
        print("Campos consultados Rechazadas: ",resultado[0]._fields)
    
    return [
        {
            "usuario": r.usuario,
            "nombre": r.nombre,
            "codigo_necesidad": r.codigo_necesidad,
            "entidad_contratante_url": r.entidad_contratante_url,
            "descripcion_objeto_compra": r.descripcion_objeto_compra,
            "etapa": r.etapa,
            "fecha_limite_proformas": r.fecha_limite_proformas,
        }
        for r in resultado
    ]

# ETAPAS EN GENERACION Y FINALIZADAS Con filtros
def obtener_infimas_asignadas_y_a_que_usuarios_filtro(db: Session,id_usuario: int):
    
    resultado = (    db.query(
            Usuario.usuario,
            Usuario.nombre,
            Infima.codigo_necesidad,
            Infima.etapa,
            Infima.entidad_contratante_url,
            Infima.descripcion_objeto_compra,
            Infima.fecha_limite_proformas,
        )
        .join(RecomendacionesUsuario, Usuario.id_usuario == RecomendacionesUsuario.usuario_id)
        .join(Infima, Infima.id_infima == RecomendacionesUsuario.id_infima)
        # Filtramos por etapa
        .filter(
            Usuario.id_usuario == id_usuario,
            or_(
                Infima.etapa == "en generacion",
                Infima.etapa == "finalizada"
            )
        )
        # Ordenamos por fecha limite de proformas (las mas proximas a vencer)
        .order_by(Infima.fecha_limite_proformas.asc())
        .all()
    )
    
    if resultado:
        print("Campos consultados Rechazadas: ",resultado[0]._fields)
    
    return [
        {
            "usuario": r.usuario,
            "nombre": r.nombre,
            "codigo_necesidad": r.codigo_necesidad,
            "entidad_contratante_url": r.entidad_contratante_url,
            "descripcion_objeto_compra": r.descripcion_objeto_compra,
            "etapa": r.etapa,
            "fecha_limite_proformas": r.fecha_limite_proformas,
        }

        for r in resultado
    ]


