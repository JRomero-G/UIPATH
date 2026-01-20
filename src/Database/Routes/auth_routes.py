from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..Controllers.usuarios_controller import autenticar_usuario
from ..Auth.Hashing import create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    usuario = autenticar_usuario(db, form_data.username, form_data.password)

    if not usuario:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_access_token(data={"usuario_id": usuario.id_usuario})

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": usuario.id_usuario,
            "nombre": usuario.nombre,
            "es_admin": usuario.es_admin,
        },
    }
