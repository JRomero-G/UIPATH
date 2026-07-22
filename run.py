import sys
import os

# ── Forzar bcrypt puro ANTES de cualquier import ──
os.environ['BCRYPT_PURE'] = '1'

import traceback
# ── Crear carpeta de depuración en C:\ ──
DEBUG_DIR = r"C:\Debug_gestorex"
os.makedirs(DEBUG_DIR, exist_ok=True)

# ── Escribir archivo de inicio ──
with open(os.path.join(DEBUG_DIR, "start.txt"), "w") as f:
    f.write("run.py iniciado\n")
    f.write(f"sys.frozen: {getattr(sys, 'frozen', False)}\n")
    f.write(f"sys.executable: {sys.executable}\n")
    f.write(f"cwd: {os.getcwd()}\n")

# ── Cargar .env PRIMERO, antes de cualquier import ──
if getattr(sys, 'frozen', False):
    env_path = os.path.join(os.path.dirname(sys.executable), ".env")
else:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

from dotenv import load_dotenv
load_dotenv(env_path, override=True)  # override para forzar recarga

with open(os.path.join(DEBUG_DIR, "env_dump.txt"), "w") as f:
    f.write(f"env_path: {env_path}\n")
    f.write(f"existe? {os.path.exists(env_path)}\n")
#    f.write(f"DB_USER: {os.getenv('DB_USER', 'NO_LEIDO')}\n")
#    f.write(f"DB_PASSWORD: {os.getenv('DB_PASSWORD', 'NO_LEIDO')[:5]}\n")
#    f.write(f"DB_HOST: {os.getenv('DB_HOST', 'NO_LEIDO')}\n")

#import tempfile
log_path = os.path.join(DEBUG_DIR, "gestorex_error.txt")

try:
    from UI.main import Iniciar

    if __name__ == "__main__":
        Iniciar()

except Exception as e:
    error_msg = traceback.format_exc()
    with open(log_path, "w") as f:
        f.write(error_msg)