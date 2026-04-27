from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import jwt
import os
from typing import Optional
from Config import Global

# -------- CONFIGURACIÓN JWT --------
SECRET_KEY = Global.SECRET_KEY_JWT
ALGORITHM = Global.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = int(Global.ACCESS_TOKEN_EXPIRE_MINUTES)

# -------- HASHING Y BCRYPT --------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
MAX_PASSWORD_BYTES = int(Global.MAX_PASSWORD_BYTES)

def safe_truncate_password(password: str) -> str:
    """Trunca la contraseña de forma segura a 72 bytes para bcrypt"""
    # Convierte a bytes
    password_bytes = password.encode('utf-8')
    
    # Si ya está dentro del límite, retorna tal cual
    if len(password_bytes) <= MAX_PASSWORD_BYTES:
        return password
    
    # Trunca a 72 bytes
    truncated_bytes = password_bytes[:MAX_PASSWORD_BYTES]
    
    # Asegura que no cortamos un carácter UTF-8 a la mitad
    # Busca el último byte que no es continuación de un carácter multibyte
    i = MAX_PASSWORD_BYTES - 1
    while i >= 0 and (truncated_bytes[i] & 0xC0) == 0x80:
        i -= 1
    
    # Si encontramos un byte inicial, truncamos hasta ahí
    if i < MAX_PASSWORD_BYTES - 1:
        truncated_bytes = truncated_bytes[:i + 1]
    
    # Decodifica de vuelta
    try:
        return truncated_bytes.decode('utf-8')
    except UnicodeDecodeError:
        # Si hay error, usa 'ignore' para caracteres inválidos
        return truncated_bytes.decode('utf-8', 'ignore')

def hash_password(password: str) -> str:
    """Hashea una contraseña de forma segura para bcrypt"""
    # Aplica truncamiento seguro
    safe_password = safe_truncate_password(password)
    # Hashea la contraseña truncada
    return pwd_context.hash(safe_password)

def verify_password(password: str, hashed: str) -> bool:
    """Verifica una contraseña contra su hash"""
    # Aplica el mismo truncamiento que en hash_password
    safe_password = safe_truncate_password(password)
    return pwd_context.verify(safe_password, hashed)

# -------- JWT --------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# -------- OAuth2 --------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")