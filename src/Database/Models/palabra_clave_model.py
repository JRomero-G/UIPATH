from sqlalchemy import Column, Integer, String
from  src.Database.Models.base import Base

class PalabraClave(Base):
    __tablename__ = "palabras_clave"

    id_clave = Column(Integer,autoincrement=True, primary_key=True)
    palabra_clave = Column(String(150), unique=True, nullable=False)
