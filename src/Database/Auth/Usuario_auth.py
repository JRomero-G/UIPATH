from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from src.Database.database import get_db
from src.Database.Models.usuarios_model import Usuario
from src.Database.Auth.Hashing import oauth2_scheme
from Config import Global


def usuario_actual(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> Usuario:
    try:
        payload = jwt.decode(token, Global.SECRET_KEY_JWT, algorithms=[Global.ALGORITHM])
        usuario_id: int = payload.get("usuario_id")
        if usuario_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        )

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id_usuario == usuario_id, Usuario.estado == "activo")
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido"
        )

    return usuario
