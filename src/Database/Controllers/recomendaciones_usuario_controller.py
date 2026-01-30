from sqlalchemy.orm import Session
from ..Models.recomendaciones_usuario_model import RecomendacionesUsuario
from ..Models.infima_model import Infima
from ..Models.usuarios_model import Usuario


# =========================
# ASIGNAR ÍNFIMAS DESDE LA UI
# =========================
def asignar_infimas_a_usuarios(db: Session, asignaciones_ui: list[dict]):
    """
    asignaciones_ui = [
        {"usuario_id": 1, "id_infima": 23},
        {"usuario_id": 2, "id_infima": 24},
    ]
    """
    objects = []

    for a in asignaciones_ui:
        usuario_id = a.get("usuario_id")
        id_infima = a.get("id_infima")

        # Validar que existan usuario e infima
        usuario = (
            db.query(Usuario)
            .filter(Usuario.id_usuario == usuario_id, Usuario.estado == "activo")
            .first()
        )
        infima = db.query(Infima).filter(Infima.id_infima == id_infima).first()
        if not usuario or not infima:
            continue

        # Evitar duplicados
        exists = (
            db.query(RecomendacionesUsuario)
            .filter(
                RecomendacionesUsuario.usuario_id == usuario_id,
                RecomendacionesUsuario.id_infima == id_infima,
            )
            .first()
        )
        if exists:
            continue

        objects.append(
            RecomendacionesUsuario(usuario_id=usuario_id, id_infima=id_infima)
        )

    if not objects:
        return {"mensaje": "No se asignaron ínfimas"}

    db.add_all(objects)
    db.commit()

    return {
        "mensaje": f"Asignadas {len(objects)} ínfimas",
        "detalle": [
            {"usuario_id": o.usuario_id, "id_infima": o.id_infima} for o in objects
        ],
    }


# =========================
# OBTENER ÍNFIMAS DE UN USUARIO
# =========================
def obtener_infimas_del_usuario(
    db: Session, usuario_id: int, limit: int = 10, offset: int = 0
):
    resultados = (
        db.query(Infima)
        .join(
            RecomendacionesUsuario, RecomendacionesUsuario.id_infima == Infima.id_infima
        )
        .filter(RecomendacionesUsuario.usuario_id == usuario_id)
        .order_by(Infima.fecha_publicacion.desc())
        .all()
    )
    return resultados
