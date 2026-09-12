import os
import sys
import traceback

# Forzar bcrypt puro ANTES de cualquier import.
os.environ.setdefault("BCRYPT_PURE", "1")

# ── Carpeta de diagnostico ────────────────────────────────────────────────
# Antes era C:\Debug_gestorex: escribir en la raiz de C:\ requiere permisos de
# administrador, y si fallaba el makedirs la app moria antes de arrancar.
# %LOCALAPPDATA% siempre es escribible por el usuario que ejecuta la app.
_base_local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
DEBUG_DIR = os.path.join(_base_local, "Gestorex", "logs")

try:
    os.makedirs(DEBUG_DIR, exist_ok=True)
except OSError:
    import tempfile
    DEBUG_DIR = tempfile.gettempdir()


def _escribir_log(nombre, texto):
    """Escribe un log de diagnostico sin poder tumbar nunca la aplicacion."""
    try:
        with open(os.path.join(DEBUG_DIR, nombre), "w", encoding="utf-8") as f:
            f.write(texto)
    except OSError:
        pass


_escribir_log(
    "start.txt",
    "run.py iniciado\n"
    f"sys.frozen: {getattr(sys, 'frozen', False)}\n"
    f"sys.executable: {sys.executable}\n"
    f"cwd: {os.getcwd()}\n",
)

# ── Cargar .env PRIMERO, antes de cualquier import de la app ──────────────
if getattr(sys, "frozen", False):
    env_path = os.path.join(os.path.dirname(sys.executable), ".env")
else:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

from dotenv import load_dotenv

load_dotenv(env_path, override=True)  # override para forzar recarga

_escribir_log(
    "env_dump.txt",
    f"env_path: {env_path}\n"
    f"existe? {os.path.exists(env_path)}\n",
)


def _mostrar_error(mensaje):
    """Avisa al usuario en pantalla. La app se compila sin consola (console=False),
    asi que sin esto un fallo de arranque es completamente silencioso."""
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Gestorex - error al iniciar",
            f"{mensaje}\n\nDetalle tecnico en:\n{DEBUG_DIR}",
        )
    except Exception:
        pass


if __name__ == "__main__":
    if not os.path.exists(env_path):
        _escribir_log("gestorex_error.txt", f"No se encontro el archivo .env en: {env_path}\n")
        _mostrar_error(
            "No se encontro el archivo de configuracion (.env) junto al ejecutable."
        )
        sys.exit(1)

    try:
        from UI.main import Iniciar

        Iniciar()
    except Exception:
        error_msg = traceback.format_exc()
        _escribir_log("gestorex_error.txt", error_msg)
        _mostrar_error("La aplicacion no pudo iniciarse.")
        sys.exit(1)
