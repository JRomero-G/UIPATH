from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from .base import Base

class BucketURL(Base):
    __tablename__ = "bucket_url"

    id_url = Column(Integer,autoincrement=True, primary_key=True)
    codigo_necesidad = Column(String(50), ForeignKey("infimas.codigo_necesidad"))
    nombre_url = Column(String(100))
    url = Column(Text, nullable=False)
    created_at = Column(DateTime)
