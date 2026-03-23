import sys
import os
import traceback

# ── Cargar .env PRIMERO, antes de cualquier import ──
if getattr(sys, 'frozen', False):
    env_path = os.path.join(os.path.dirname(sys.executable), ".env")
else:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

from dotenv import load_dotenv
load_dotenv(env_path)

print(f"[RUN] BACKEND_URL cargado: {os.getenv('BACKEND_URL')}")  # verificar

log_path = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else ".", "error_log.txt")

try:
    print("[RUN] Iniciando...")
    from UI.main import Iniciar
    print("[RUN] Import exitoso")

    if __name__ == "__main__":
        Iniciar()

except Exception as e:
    error_msg = traceback.format_exc()
    print(f"[RUN] ERROR: {error_msg}")
    with open(log_path, "w") as f:
        f.write(error_msg)
    input("Presiona Enter para cerrar...")