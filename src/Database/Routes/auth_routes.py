from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..Controllers.usuarios_controller import autenticar_usuario
from ..Auth.Hashing import create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Modelo de request para login
class LoginRequest(BaseModel):
    username: str
    password: str

# Endpoint de login
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    Recibe username y password, autentica al usuario,
    y devuelve un token JWT junto con la información básica del usuario.
    """
    # Validar credenciales
    usuario = autenticar_usuario(db, data.username, data.password)
    if not usuario:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # Generar token JWT
    token = create_access_token(data={"usuario_id": usuario.id_usuario})

    # Respuesta al cliente
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": usuario.id_usuario,
            "nombre": usuario.nombre,
            "es_admin": usuario.es_admin,
        },
    }
