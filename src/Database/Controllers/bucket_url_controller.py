from sqlalchemy.orm import Session
from Models.bucket_url_model import BucketURL


"Registra una URL asociada a una infima (archivos generados por IA)"
def registrar_bucket_url(db: Session, data: dict):

    bucket = BucketURL(
        codigo_necesidad=data["codigo_necesidad"],
        nombre_url=data["nombre_url"],
        url=data["url"]
    )
    db.add(bucket)
    db.commit()
    db.refresh(bucket)
    return bucket

"Lista todas las URLs registradas"
def listar_bucket_urls(db: Session):
    
    return db.query(BucketURL).all()


"Lista las URLs asociadas a una infima específica"
def listar_bucket_urls_por_codigo(db: Session, codigo_necesidad: str):

    return db.query(BucketURL).filter(
        BucketURL.codigo_necesidad == codigo_necesidad
    ).all()
