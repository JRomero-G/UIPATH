from sqlalchemy import Column, Integer, String, DECIMAL, Text, TIMESTAMP, ForeignKey
from  src.Database.Models.base import Base

class Evaluacion(Base):
    __tablename__ = "evaluaciones"

    id_evaluacion = Column(Integer,autoincrement=True, primary_key=True)
    codigo_necesidad = Column(String(50), ForeignKey("infimas.codigo_necesidad"), unique=True)
    peso_total = Column(DECIMAL(6, 2), nullable=False)
    justificacion = Column(Text, nullable=False)
    fecha = Column(TIMESTAMP)
