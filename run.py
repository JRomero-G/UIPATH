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

log_path = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else ".", "error_log.txt")

try:
    from UI.main import Iniciar

    if __name__ == "__main__":
        Iniciar()

except Exception as e:
    error_msg = traceback.format_exc()
    with open(log_path, "w") as f:
        f.write(error_msg)