from sqlalchemy.orm import Session
from ..Models.recomendaciones_usuario_model import RecomendacionesUsuario
from ..Models.infima_model import Infima
from ..Models.usuarios_model import Usuario
# Nueva importacion
from sqlalchemy.exc import IntegrityError


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


# Devuelve las ínfimas asignadas a un usuario específico y paginadas para evitar sobre carga
def obtener_infimas_recomendadas_asignadas_del_usuario(db: Session,usuario_id: int):
    return (
        db.query(Infima)
        .join(RecomendacionesUsuario)
        .filter(RecomendacionesUsuario.usuario_id == usuario_id)
        .order_by(Infima.fecha_publicacion.desc())
        .all()
    )
