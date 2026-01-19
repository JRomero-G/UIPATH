from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from .base import Base

class RecomendacionesUsuario(Base):
    __tablename__ = "recomendaciones_usuario"

    id_rec_usuario = Column(Integer, primary_key=True, autoincrement=True)
    id_infima = Column(Integer, ForeignKey("infimas.id_infima"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)

    __table_args__ = (
        UniqueConstraint("id_infima", name="uq_infima_unica"),
    )
