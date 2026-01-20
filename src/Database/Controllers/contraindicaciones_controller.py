from sqlalchemy.orm import Session
from ..Models.contraindicaciones_model import Contraindicacion


def registrar_contraindicacion(db: Session, data: dict):
    """
    Registra una contraindicacion evaluada por la IA
    """
    contra = Contraindicacion(
        contraindicacion=data["contraindicacion"],
        peso=data.get("peso", 1.00)
    )
    db.add(contra)
    db.commit()
    db.refresh(contra)
    return contra


def listar_contraindicaciones(db: Session):
    """
    Lista todas las contraindicaciones
    """
    return db.query(Contraindicacion).all()
