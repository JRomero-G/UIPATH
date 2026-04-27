from sqlalchemy.orm import Session
from src.Database.Models.evaluacion_model import Evaluacion


def registrar_evaluacion(db: Session, data: dict):
    evaluacion = Evaluacion(
        codigo_necesidad=data["codigo_necesidad"],
        peso_total=data["peso_total"],
        justificacion=data["justificacion"],
    )
    db.add(evaluacion)
    db.commit()
    db.refresh(evaluacion)
    return evaluacion


def listar_evaluaciones(db: Session):
    return db.query(Evaluacion).all()
