from mysql.connector import IntegrityError
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


# Esquema para actualizar usuarios
class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    usuario: Optional[str] = None
    password: Optional[str] = None
    correo: Optional[EmailStr] = None
    telefono: Optional[str] = None
    es_admin: Optional[bool] = None
    estado: Optional[str] = None


class UsuarioDelete(BaseModel):
    estado: str


# Función para registrar un usuario
def registrar_usuario(db: Session, data: UsuarioCreate):
    # Verificar si el nombre de usuario ya existe
    usuario_existe = (
        db.query(Usuario)
        .filter((Usuario.usuario == data.usuario) | (Usuario.correo == data.correo))
        .first()
    )

    if usuario_existe:
        return {"error": "El nombre de usuario o correo ya está en uso"}

    usuario = Usuario(
        usuario=data.usuario,
        nombre=data.nombre,
        pass_hash=hash_password(data.password),
        correo=data.correo,
        telefono=data.telefono,
        es_admin=data.es_admin,
    )

    try:
        # Agregar el nuevo usuario a la sesión y guardar en la base de datos
        db.add(usuario)  # Se utiliza db.add() para agregar el nuevo registro en la sesión de SQLAlchemy,
        # lo que marca el objeto como "pendiente" para ser insertado en la base de datos.
        db.commit()
        db.refresh(usuario)
        return usuario

    except IntegrityError as e:
        # Si ocurre un error de integridad (por ejemplo, nombre de usuario o correo duplicado),
        # hacemos rollback para evitar dejar la sesión en un estado inconsistente
        db.rollback()
        return {"error": str(e)}  # cambiar luego por un mensaje genernico
        # para no exponer detalles de la base de datos en la respuesta
    except Exception as e:
        db.rollback()
        return {"error": str(e)}


# Funcion Actualizar usuario
def actualizar_usuario(db: Session, id_usuario: int, data: UsuarioUpdate):

    # Buscamos el usuario por su ID
    User = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not User:
        return {"error": "Usuario no encontrado"}

    try:
        # Verificar si el correo ya existe para otro usuario viendo el id_usuario,
        # si el correo es el mismo del usuario que se esta actualizando, no se considera un error

        if data.correo:
            correo_existe = (
                db.query(Usuario)
                .filter(Usuario.correo == data.correo, Usuario.id_usuario != id_usuario)
                .first()
            )
            if correo_existe:
                return {"error": "El correo ya está en uso por otro usuario"}
            # Si el correo es el mismo del usuario que se esta actualizando,
            #  no se considera un error, por lo que no hacemos nada en ese caso
            User.correo = data.correo

        if data.usuario:
            usuario_existe = (
                db.query(Usuario)
                .filter(Usuario.usuario == data.usuario, Usuario.id_usuario != id_usuario)
                .first()
            )

            if usuario_existe:
                return {"error": "El nombre de usuario ya esta en uso."}

            User.usuario = data.usuario
        else:
            return {"error": "Usuario vacio"}

        if data.nombre is not None:
            User.nombre = data.nombre

        if data.password is not None:
            User.pass_hash = hash_password(data.password)

        if data.telefono is not None:
            User.telefono = data.telefono

        if data.es_admin is not None:
            User.es_admin = data.es_admin

        if data.estado is not None:
            User.estado = data.estado

            # No utilizamos db.add(usuario) porque el objeto usuario ya está siendo rastreado por la sesión de SQLAlchemy,
            # por lo que cualquier cambio que hagamos en el objeto se reflejará automáticamente en
            # la base de datos cuando llamemos a db.commit(). No es necesario agregarlo nuevamente a la sesión.

        # Guardamos los cambios en la base de datos
        db.commit()
        # Refrescamos el objeto para obtener los datos actualizados
        db.refresh(User)
        return {
            "success": True,
            "message": "Usuario actualizado correctamente",
            "usuario": {
                "id": User.id_usuario,
                "nombre": User.nombre,
                "usuario": User.usuario,
                "correo": User.correo,
                "telefono": User.telefono,
                "es_admin": User.es_admin,
                "estado": User.estado
            }
        }
    except IntegrityError as e:
        db.rollback()
        return {"error": str(e)}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}


# Función para eliminar un usuario (cambiar estado a inactivo)
def inhabilitar_usuario(db: Session, id_usuario: int):
    usuario = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario:
        return {"error": "Usuario no encontrado"}

    try:
        usuario.estado = "inactivo"
        db.commit()
        db.refresh(usuario)
        return {"message": "Usuario inhabilitado exitosamente"}
    except IntegrityError as e:
        db.rollback()
        return {"error": str(e)}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}


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


def listar_usuarios_no_admin(db: Session):
    return db.query(Usuario).filter(Usuario.es_admin == 1, Usuario.estado == "activo").all()

def listar_empleados_activos(db: Session):
    return db.query(Usuario).filter(Usuario.es_admin == 0, Usuario.estado == "activo").all()

# Obtener usuario por ID
def obtener_usuario_por_id(db: Session, id_usuario: int):
    return db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
