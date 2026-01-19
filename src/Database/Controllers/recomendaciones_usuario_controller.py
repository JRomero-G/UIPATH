from sqlalchemy.orm import Session
from Models.recomendaciones_usuario_model import RecomendacionesUsuario
from Models.infima_model import Infima
from Models.usuarios_model import Usuario
from sqlalchemy import not_

#Asignamos ínfimas no asignadas a usuarios activos
def asignar_infimas_a_usuarios(db: Session, max_por_usuario: int = 15):

    #comprobamos que los usuarios esten activos,
    #no se puede asignar infimas a un usuario que no trabaja o que ya no puede ingresar al sistema
    usuarios = db.query(Usuario).filter(
        Usuario.estado == "activo"
    ).all()

    #Poco probable pero si no hay usuarios activos no se procede
    if not usuarios:
        return {"error": "No hay usuarios activos"}

    #Se identifican qué ínfimas ya fueron asignadas para no reasignar infimas 
    subquery_infimas_asignadas = (
        db.query(RecomendacionesUsuario.id_infima)
        .distinct()
        .subquery()
    )

    #identifiamos infimas disponibles y que no han sido asignadas 
    infimas_disponibles = db.query(Infima).filter(
        not_(Infima.id_infima.in_(subquery_infimas_asignadas))
    ).all()

    #si el sistema hara una actualizacion periodica junto a las nuevas infimas que pueda
    #recolectar la IA es podible que cuando en la pagina web solo se hayan creado 15 nuevas
    #infimas por ejemplo, es probable que solo 5 o ninguna sea recomendable entonces no habran
    #nuevas infimas registradas
    if not infimas_disponibles:
        return {"mensaje": "No hay ínfimas disponibles para asignar"}

    #ista temporal de objetos a insertar
    asignaciones = []
    #índice que recorre la lista de infimas disponibles una sola vez
    idx_infima = 0

    #Iteras usuario por usuario y se lleva un control de cuantas infimas recibe cada uno
    for usuario in usuarios:
        asignadas_usuario = 0

        #condiciones: El usuario no ha alcanzado su límite (max_por_usuario) y Aun quedan infimas sin asignar
        while asignadas_usuario < max_por_usuario and idx_infima < len(infimas_disponibles):
            
            #crea objetos
            asignaciones.append(
                RecomendacionesUsuario(
                    id_infima=infimas_disponibles[idx_infima].id_infima,
                    usuario_id=usuario.id_usuario
                )
            )

            #El usuario recibe una infima más
            asignadas_usuario += 1
            #Se avanza a la siguiente ínfima
            idx_infima += 1

    if not asignaciones:
        return {"mensaje": "No se realizaron asignaciones"}
    
    #Se insertan todas las asignaciones en una sola operacion
    db.bulk_save_objects(asignaciones)
    #Se confirma la transacción
    db.commit()

    #resultados de la operacion
    return {
        #Cuántos usuarios participaron
        "usuarios": len(usuarios),
        #Cuantas infimas se asignaron
        "infimas_asignadas": len(asignaciones),
        #Detalle exacto de cada asignacion usuario y id de infima
        "detalle": [
            {"usuario_id": a.usuario_id, "id_infima": a.id_infima}
            for a in asignaciones
        ]
    }

#Devuelve las ínfimas asignadas a un usuario específico y paginadas para evitar sobre carga
def obtener_infimas_del_usuario(db: Session, usuario_id: int,limit: int = 10, offset: int = 0):

    resultados = (
        db.query(Infima)
        .join(
            RecomendacionesUsuario,
            RecomendacionesUsuario.id_infima == Infima.id_infima
        )
        .filter(RecomendacionesUsuario.usuario_id == usuario_id)
        .order_by(Infima.fecha_publicacion.desc())
        .all()
    )

    return resultados