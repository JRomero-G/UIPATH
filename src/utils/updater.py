# src/utils/updater.py
import os
import sys
import subprocess
import requests
from packaging import version as pkg_version

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar,
)

from src.Config.version import CURRENT_VERSION
from Config import Global


# ============================================================
# HILO DE DESCARGA
# ============================================================
class DescargaThread(QThread):
    progreso = pyqtSignal(int)
    completado = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, repo, tag, filename):
        super().__init__()
        self.repo = repo
        self.tag = tag
        self.filename = filename

    def run(self):
        try:
            temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
            installer_path = os.path.join(temp_dir, "Installer_Gestorex.exe")

            github_token = Global.GITHUB_KEY
            if not github_token:
                self.error.emit("No se encontró el token de GitHub en la configuración.")
                return

            headers_api = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            # ── Paso 1: Obtener el ID del asset desde la API ──
            api_url = f"https://api.github.com/repos/{self.repo}/releases/tags/{self.tag}"
            print(f"[DESCARGA] Consultando release: {api_url}")

            resp_release = requests.get(api_url, headers=headers_api, timeout=15)
            resp_release.raise_for_status()
            release_data = resp_release.json()

            # Buscar el asset por nombre
            asset_id = None
            for asset in release_data.get("assets", []):
                if asset["name"] == self.filename:
                    asset_id = asset["id"]
                    break

            if not asset_id:
                self.error.emit(
                    f"No se encontró el archivo {self.filename} en el release {self.tag}."
                )
                return

            print(f"[DESCARGA] Asset ID: {asset_id}")

            # ── Paso 2: Descargar el asset usando su ID ──
            headers_download = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/octet-stream",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            asset_url = f"https://api.github.com/repos/{self.repo}/releases/assets/{asset_id}"
            response = requests.get(
                asset_url,
                headers=headers_download,
                stream=True,
                timeout=60,
                allow_redirects=True
            )
            response.raise_for_status()

            total = int(response.headers.get("content-length", 0))
            descargado = 0

            with open(installer_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        descargado += len(chunk)
                        if total > 0:
                            porcentaje = int((descargado / total) * 100)
                            self.progreso.emit(porcentaje)

            # ── Paso 3: Verificar que es un .exe válido ──
            with open(installer_path, "rb") as f:
                if f.read(2) != b"MZ":
                    self.error.emit("El archivo descargado no es válido.")
                    return

            self.completado.emit(installer_path)

        except requests.exceptions.Timeout:
            self.error.emit("La descarga tardó demasiado. Intenta de nuevo.")
        except requests.exceptions.ConnectionError:
            self.error.emit("Sin conexión a internet.")
        except Exception as e:
            self.error.emit(f"Error al descargar: {str(e)}")


# ============================================================
# DIÁLOGO DE ACTUALIZACIÓN
# ============================================================
class DialogoActualizacion(QDialog):
    def __init__(self, version_nueva, repo, tag, filename, parent=None):
        super().__init__(parent)
        self.version_nueva = version_nueva
        self.repo = repo
        self.tag = tag
        self.filename = filename
        self.setWindowTitle("Actualización disponible")
        self.setFixedWidth(440)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
            }
            QLabel {
                color: #2c2c2c;
                font-size: 13px;
                background-color: transparent;
            }
            QPushButton {
                background-color: #ffffff;
                color: #2c2c2c;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #aaa;
            }
            QPushButton#btn_descargar {
                background-color: #2196F3;
                color: white;
                border: none;
            }
            QPushButton#btn_descargar:hover {
                background-color: #1976D2;
            }
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #e0e0e0;
                text-align: center;
                color: #2c2c2c;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 4px;
            }
        """)

        self.layout_principal = QVBoxLayout()
        self.layout_principal.setSpacing(15)
        self.layout_principal.setContentsMargins(25, 25, 25, 20)

        self.label = QLabel(
            f"🎉 Nueva versión disponible: <b>v{version_nueva}</b><br><br>"
            f"Versión instalada: v{CURRENT_VERSION}<br><br>"
            f"¿Deseas descargar e instalar la actualización ahora?"
        )
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft)
        self.layout_principal.addWidget(self.label)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setFixedHeight(22)
        self.barra.hide()
        self.layout_principal.addWidget(self.barra)

        self.label_estado = QLabel("")
        self.label_estado.setAlignment(Qt.AlignCenter)
        self.label_estado.hide()
        self.layout_principal.addWidget(self.label_estado)

        self.botones_layout = QHBoxLayout()

        self.btn_descargar = QPushButton("⬇ Descargar e instalar")
        self.btn_descargar.setObjectName("btn_descargar")
        self.btn_descargar.setFixedHeight(38)
        self.btn_descargar.clicked.connect(self.iniciar_descarga)

        self.btn_despues = QPushButton("Recordarme después")
        self.btn_despues.setFixedHeight(38)
        self.btn_despues.clicked.connect(self.reject)

        self.botones_layout.addWidget(self.btn_descargar)
        self.botones_layout.addWidget(self.btn_despues)
        self.layout_principal.addLayout(self.botones_layout)

        self.setLayout(self.layout_principal)

    def iniciar_descarga(self):
        self.btn_descargar.setEnabled(False)
        self.btn_despues.setEnabled(False)
        self.btn_descargar.setText("Descargando...")
        self.barra.show()
        self.label_estado.show()
        self.label_estado.setText("Iniciando descarga...")
        self.label.setText(
            f"⬇ Descargando actualización v{self.version_nueva}...<br>"
            f"Por favor no cierres la aplicación."
        )

        # ← Ahora pasa repo, tag y filename en lugar de url
        self.hilo_descarga = DescargaThread(
            repo=self.repo,
            tag=self.tag,
            filename=self.filename
        )
        self.hilo_descarga.progreso.connect(self.actualizar_progreso)
        self.hilo_descarga.completado.connect(self.descarga_completa)
        self.hilo_descarga.error.connect(self.descarga_error)
        self.hilo_descarga.start()

    def actualizar_progreso(self, valor):
        self.barra.setValue(valor)
        self.label_estado.setText(f"Descargando... {valor}%")

    def descarga_completa(self, ruta_installer):
        self.label.setText(
            "✅ Descarga completa.<br><br>"
            "El instalador se abrirá ahora.<br>"
            "<b>La aplicación se cerrará para completar la actualización.</b>"
        )
        self.barra.setValue(100)
        self.label_estado.setText("¡Listo!")
        self.btn_despues.setText("Cerrar")
        self.btn_despues.setEnabled(True)
        self._ejecutar_instalador(ruta_installer)

    def descarga_error(self, mensaje):
        self.label.setText(f"❌ {mensaje}")
        self.barra.hide()
        self.label_estado.hide()
        self.btn_descargar.setText("Reintentar")
        self.btn_descargar.setEnabled(True)
        self.btn_despues.setEnabled(True)

    def _ejecutar_instalador(self, ruta):
        try:
            subprocess.run(
                ["powershell", "-Command", f"Unblock-File -Path '{ruta}'"],
                capture_output=True
            )
            subprocess.Popen(
                [ruta, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
                creationflags=subprocess.DETACHED_PROCESS
            )
        except Exception as e:
            self.label.setText(f"❌ No se pudo abrir el instalador: {str(e)}")
            return

        sys.exit(0)


# ============================================================
# HILO DE VERIFICACIÓN
# ============================================================
class VerificadorThread(QThread):
    hay_actualizacion = pyqtSignal(str, str, str, str)  # version, repo, tag, filename

    def run(self):
        try:
            api_url = Global.BACKEND_URL
            if not api_url:
                return

            response = requests.get(
                f"{api_url}/config/version",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            version_servidor = data.get("version", "0.0.0")
            repo = data.get("repo", "")
            tag = data.get("tag", "")
            filename = data.get("filename", "")

            if pkg_version.parse(version_servidor) > pkg_version.parse(CURRENT_VERSION):
                self.hay_actualizacion.emit(version_servidor, repo, tag, filename)

        except Exception:
            pass


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def verificar_actualizacion_async(parent_widget):
    hilo = VerificadorThread()

    def mostrar_dialogo(version_nueva, repo, tag, filename):
        dialogo = DialogoActualizacion(
            version_nueva=version_nueva,
            repo=repo,
            tag=tag,
            filename=filename,
            parent=parent_widget
        )
        dialogo.exec_()

    hilo.hay_actualizacion.connect(mostrar_dialogo)
    hilo.start()
    return hilo
