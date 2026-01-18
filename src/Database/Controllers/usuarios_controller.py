from sqlalchemy.orm import Session
from Models.usuarios_model import Usuario
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
from sqlalchemy.orm import Session
from Models.usuarios_model import Usuario
from Auth.Hashing import hash_password, verify_password


def registrar_usuario(db: Session, data: dict):
    usuario = Usuario(
        usuario=data["usuario"],
        nombre=data["nombre"],
        pass_hash=hash_password(data["password"]),
        correo=data.get("correo"),
        telefono=data.get("telefono"),
        es_admin=data.get("es_admin", False)
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def autenticar_usuario(db: Session, usuario: str, password: str):
    user = db.query(Usuario).filter(
        Usuario.usuario == usuario,
        Usuario.estado == "activo"
    ).first()

    if not user:
        return None

    if not verify_password(password, user.pass_hash):
        return None

    return user


def listar_usuarios(db: Session):
    return db.query(Usuario).all()


def obtener_usuario_por_id(db: Session, id_usuario: int):
    return db.query(Usuario).filter(
        Usuario.id_usuario == id_usuario
    ).first()

