from sqlalchemy import Column, Integer, Text, DECIMAL
from src.Database.Models.base import Base

class Contraindicacion(Base):
    __tablename__ = "contraindicaciones"

    id_contraindicacion = Column(Integer,autoincrement=True, primary_key=True)
    contraindicacion = Column(Text, nullable=False)
    peso = Column(DECIMAL(4, 2), default=1.00)
