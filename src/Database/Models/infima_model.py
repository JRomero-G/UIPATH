from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, Text, DECIMAL, TIMESTAMP
from  src.Database.Models.base import Base

class Infima(Base):
    __tablename__ = "infimas"

    id_infima = Column(Integer,autoincrement=True, primary_key=True)
    tipo_necesidad = Column(String(100), nullable=False)
    codigo_necesidad = Column(String(50), unique=True, nullable=False)
    fecha_publicacion = Column(Date)
    provincia_canton = Column(String(150))
    descripcion_objeto_compra = Column(Text)
    estado_necesidad = Column(Enum("en curso", "finalizada"), default="en curso")
    fecha_limite_proformas = Column(DateTime)
    entidad_contratante = Column(String(200))
    entidad_contratante_url = Column(String(500))
    direccion_entrega = Column(String(255))
    contacto = Column(String(150))
    etapa = Column(
        Enum(
            "ingresada",
            "preseleccionada",
            "no seleccionada",
            "seleccionada",
            "en generacion",
            "finalizada",
            "enviada"
        ),
        default="ingresada"
    )
    nivel_de_oportunidad = Column(Enum("nivel 1", "nivel 2", "nivel 3"))
    PACdoc = Column(DECIMAL(12, 2))
    PACweb = Column(DECIMAL(12, 2))
    fecha_creacion = Column(TIMESTAMP)
    actualizado_en = Column(TIMESTAMP)
