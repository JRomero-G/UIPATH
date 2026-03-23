from dotenv import load_dotenv
import os 
from pathlib import Path


# Siempre encuentra el .env desde la raíz, sin importar desde dónde se ejecute
load_dotenv(Path(__file__).resolve().parent / ".env")

class Global:
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DATABASE = os.getenv("DATABASE")
    DATABASE_URL = os.getenv("DATABASE_URL")
    BACKEND_URL = os.getenv("BACKEND_URL")
    BUCKET_NAME = os.getenv("BUCKET_NAME")
    CREDENTIALS_GEMINI = os.getenv("CREDENCIALES_GEMINI")
    RENDER_CRENDENTIALS_JSON = os.getenv("RENDER_CRENDENTIALS_JSON")
    SECRET_KEY_JWT= os.getenv("SECRET_KEY_JWT")
    ALGORITHM = os.getenv("ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
    MAX_PASSWORD_BYTES = os.getenv("MAX_PASSWORD_BYTES")
    GITHUB_KEY = os.getenv("GITHUB_KEY")
    
# NECESARIO INSTALAR: pip install pyinstaller

# Comando para empaquetar sin incluir el .env
#  pyinstaller --onefile --windowed --icon=UI/assets/Logo_app.ico --add-data "UI/assets;UI/assets" run.py

# pip install packaging requests