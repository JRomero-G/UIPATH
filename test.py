import sys
import os
import requests

from dotenv import load_dotenv
from PyQt5.QtWidgets import QApplication

# ==========================
# Cargar .env
# ==========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH, override=True)

# ==========================
# Datos ficticios
# ==========================

datos_prueba = [
    {
        "id_infima": 1,
        "codigo_necesidad": "NIC-2026-001",
        "descripcion_objeto_compra": "Adquisición de equipo de oficina y suministros administrativos",
        "nivel_de_oportunidad": "nivel 1",
        "entidad_contratante_url": "https://ejemplo.com/proceso/001"
    },
    {
        "id_infima": 2,
        "codigo_necesidad": "NIC-2026-002",
        "descripcion_objeto_compra": "Contratación de servicios de mantenimiento preventivo para instalaciones",
        "nivel_de_oportunidad": "nivel 2",
        "entidad_contratante_url": "https://ejemplo.com/proceso/002"
    },
    {
        "id_infima": 3,
        "codigo_necesidad": "NIC-2026-003",
        "descripcion_objeto_compra": "Compra de materiales eléctricos para mantenimiento general",
        "nivel_de_oportunidad": "nivel 3",
        "entidad_contratante_url": "https://ejemplo.com/proceso/003"
    },
    {
        "id_infima": 4,
        "codigo_necesidad": "NIC-2026-004",
        "descripcion_objeto_compra": "Adquisición de computadoras portátiles y accesorios tecnológicos",
        "nivel_de_oportunidad": "nivel 1",
        "entidad_contratante_url": "https://ejemplo.com/proceso/004"
    },
    {
        "id_infima": 5,
        "codigo_necesidad": "NIC-2026-005",
        "descripcion_objeto_compra": "Servicio de limpieza y mantenimiento de áreas comunes",
        "nivel_de_oportunidad": "nivel 2",
        "entidad_contratante_url": "https://ejemplo.com/proceso/005"
    }
]


# ==========================
# Respuesta falsa del backend
# ==========================

class RespuestaPrueba:

    status_code = 200

    def json(self):
        return datos_prueba


# ==========================
# Interceptar requests.get
# ==========================

requests.get = lambda *args, **kwargs: RespuestaPrueba()


# ==========================
# Importar ventana
# ==========================

from UI.views.workspace_user import WorkspaceUserUI


# ==========================
# Ejecutar
# ==========================

app = QApplication(sys.argv)

ventana = WorkspaceUserUI()
ventana.show()

sys.exit(app.exec_())