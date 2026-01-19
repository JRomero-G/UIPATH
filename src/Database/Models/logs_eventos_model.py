from sqlalchemy import Column, Integer, String, DateTime
from .base import Base

class LogEvento(Base):
    __tablename__ = "logs_eventos"

    id_log = Column(Integer,autoincrement=True, primary_key=True)
    evento = Column(String(250), nullable=False)
    fecha_creacion = Column(DateTime)
    creado_por = Column(String(100))
