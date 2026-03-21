# src/utils/updater.py
import os
import webbrowser
import requests
from packaging import version as pkg_version

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt

from src.Config.version import CURRENT_VERSION


# ============================================================
# DIÁLOGO DE ACTUALIZACIÓN
# ============================================================
class DialogoActualizacion(QDialog):
    def __init__(self, version_nueva, url_descarga, parent=None):
        super().__init__(parent)
        self.url_descarga = url_descarga
        self.setWindowTitle("Actualización disponible")
        self.setFixedWidth(420)
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 20)

        # Mensaje
        label = QLabel(
            f"🎉 Nueva versión disponible: <b>v{version_nueva}</b><br><br>"
            f"Versión instalada: v{CURRENT_VERSION}<br><br>"
            f"Se recomienda actualizar para obtener las últimas mejoras y correcciones."
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignLeft)
        layout.addWidget(label)

        # Botones
        botones = QHBoxLayout()

        btn_descargar = QPushButton("⬇ Descargar ahora")
        btn_descargar.setFixedHeight(38)
        btn_descargar.clicked.connect(self.descargar)

        btn_despues = QPushButton("Recordarme después")
        btn_despues.setFixedHeight(38)
        btn_despues.clicked.connect(self.reject)

        botones.addWidget(btn_descargar)
        botones.addWidget(btn_despues)
        layout.addLayout(botones)

        self.setLayout(layout)

    def descargar(self):
        webbrowser.open(self.url_descarga)
        self.accept()


# ============================================================
# HILO DE VERIFICACIÓN (no congela la UI)
# ============================================================
class VerificadorThread(QThread):
    hay_actualizacion = pyqtSignal(str, str)  # version_nueva, url_descarga

    def run(self):
        try:
            api_url = os.getenv("API_URL", "").rstrip("/")
            if not api_url:
                return

            response = requests.get(
                f"{api_url}/config/version",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            version_servidor = data.get("version", "0.0.0")
            url_descarga = data.get("url", "")

            if pkg_version.parse(version_servidor) > pkg_version.parse(CURRENT_VERSION):
                self.hay_actualizacion.emit(version_servidor, url_descarga)

        except Exception:
            pass  # Silencioso — no interrumpir al usuario


# ============================================================
# FUNCIÓN PRINCIPAL — llamar desde login.py
# ============================================================
def verificar_actualizacion_async(parent_widget):
    """
    Lanza la verificación en segundo plano.
    Si hay actualización, muestra el diálogo automáticamente.
    Retorna el hilo para mantener la referencia viva.
    """
    hilo = VerificadorThread()

    def mostrar_dialogo(version_nueva, url_descarga):
        dialogo = DialogoActualizacion(
            version_nueva=version_nueva,
            url_descarga=url_descarga,
            parent=parent_widget
        )
        dialogo.exec_()

    hilo.hay_actualizacion.connect(mostrar_dialogo)
    hilo.start()
    return hilo  # importante: guardar referencia con self._hilo_update
