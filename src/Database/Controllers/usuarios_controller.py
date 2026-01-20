from sqlalchemy.orm import Session
from ..Models.usuarios_model import Usuario
from ..Auth.Hashing import hash_password, verify_password
from pydantic import BaseModel, EmailStr
from typing import Optional

# Esquema para crear usuarios
class UsuarioCreate(BaseModel):
    usuario: str
    nombre: str
    password: str
    correo: Optional[EmailStr] = None
    telefono: Optional[str] = None
    es_admin: bool = False


# Función para registrar un usuario
def registrar_usuario(db: Session, data: UsuarioCreate):
    usuario = Usuario(
        usuario=data.usuario,
        nombre=data.nombre,
        pass_hash=hash_password(data.password),
        correo=data.correo,
        telefono=data.telefono,
        es_admin=data.es_admin,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


# Función para autenticar un usuario
def autenticar_usuario(db: Session, usuario: str, password: str):
    user = (
        db.query(Usuario)
        .filter(Usuario.usuario == usuario, Usuario.estado == "activo")
        .first()
    )

    if not user:
        return None

    if not verify_password(password, user.pass_hash):
        return None

    return user


# Listar todos los usuarios
def listar_usuarios(db: Session):
    return db.query(Usuario).all()


# Obtener usuario por ID
def obtener_usuario_por_id(db: Session, id_usuario: int):
    return db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
