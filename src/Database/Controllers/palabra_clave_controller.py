from sqlalchemy.orm import Session
from src.Database.Models.palabra_clave_model import PalabraClave


def registrar_palabra_clave(db: Session, palabra: str):
    palabra_clave = PalabraClave(palabra_clave=palabra)
    db.add(palabra_clave)
    db.commit()
    db.refresh(palabra_clave)
    return palabra_clave


def listar_palabras_clave(db: Session):
    return db.query(PalabraClave).all()
