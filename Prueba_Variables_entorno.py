from Config import Global

import os
from dotenv import load_dotenv 


load_dotenv()
print("Segunda configuracion: "+os.getenv("DB_USER"))
print("Credenciales local: "+ Global.CREDENTIALS_GEMINI)