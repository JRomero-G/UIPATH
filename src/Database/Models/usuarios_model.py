from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Enum, DateTime
from .base import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer,autoincrement=True, primary_key=True)
    usuario = Column(String(100), unique=True, nullable=False)
    nombre = Column(String(250), nullable=False)
    pass_hash = Column(String(255), nullable=False)
    es_admin = Column(Boolean, default=False)
    correo = Column(String(250), unique=True)
    telefono = Column(String(50))
    estado = Column(Enum("activo", "inactivo"), default="activo")
    # Campos de auditoría
    # fecha_creacion se asignará al crear el usuario, fecha_modificacion se actualizará cada vez que se modifique el usuario
    fecha_creacion = Column(DateTime, default=datetime.now)
    fecha_modificacion = Column(DateTime, default=datetime.now, onupdate=datetime.now)
