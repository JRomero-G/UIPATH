from sqlalchemy.orm import Session
from Models.logs_eventos_model import LogEvento


def registrar_log(db: Session, evento: str, creado_por: str = None):
    log = LogEvento(
        evento=evento,
        creado_por=creado_por
    )
    db.add(log)
    db.commit()
    return log


def listar_logs(db: Session):
    return db.query(LogEvento).order_by(
        LogEvento.fecha_creacion.desc()
    ).all()
