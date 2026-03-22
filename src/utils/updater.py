# src/utils/updater.py
import os
import sys
import subprocess
import requests
from packaging import version as pkg_version

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
)

from src.Config.version import CURRENT_VERSION
from Config import Global


# ============================================================
# HILO DE DESCARGA — descarga el instalador en segundo plano
# ============================================================
class DescargaThread(QThread):
    progreso = pyqtSignal(int)  # 0-100
    completado = pyqtSignal(str)  # ruta del archivo descargado
    error = pyqtSignal(str)  # mensaje de error

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            # Guardar el instalador en la carpeta temporal del sistema
            temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
            installer_path = os.path.join(temp_dir, "Installer_Gestorex.exe")

            response = requests.get(self.url, stream=True, timeout=60)
            response.raise_for_status()

            # Obtener tamaño total para la barra de progreso
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

            self.completado.emit(installer_path)
        except requests.exceptions.Timeout:
            self.error.emit("La descarga tardó demasiado. Intenta de nuevo.")
        except requests.exceptions.ConnectionError:
            self.error.emit("Sin conexión a internet.")
        except Exception as e:
            self.error.emit(f"Error al descargar: {str(e)}")


# ============================================================
# DIÁLOGO DE ACTUALIZACIÓN — con barra de progreso
# ============================================================


class DialogoActualizacion(QDialog):
    def __init__(self, version_nueva, url_descarga, parent=None):
        super().__init__(parent)
        self.url_descarga = url_descarga
        self.version_nueva = version_nueva
        self.setWindowTitle("Actualización disponible")
        self.setFixedWidth(440)
        self.setModal(True)

        # ── Estilo del diálogo ──
        self.setStyleSheet(
            """
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
        """
        )

        self.layout_principal = QVBoxLayout()
        self.layout_principal.setSpacing(15)
        self.layout_principal.setContentsMargins(25, 25, 25, 20)

        # ── Mensaje inicial ──
        self.label = QLabel(
            f"🎉 Nueva versión disponible: <b>v{version_nueva}</b><br><br>"
            f"Versión instalada: v{CURRENT_VERSION}<br><br>"
            f"¿Deseas descargar e instalar la actualización ahora?"
        )
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft)
        self.layout_principal.addWidget(self.label)

        # ── Barra de progreso (oculta al inicio) ──
        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setFixedHeight(22)
        self.barra.hide()
        self.layout_principal.addWidget(self.barra)

        # ── Label de estado (oculto al inicio) ──
        self.label_estado = QLabel("")
        self.label_estado.setAlignment(Qt.AlignCenter)
        self.label_estado.hide()
        self.layout_principal.addWidget(self.label_estado)

        # ── Botones ──
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
        # Deshabilitar botones durante la descarga
        self.btn_descargar.setEnabled(False)
        self.btn_despues.setEnabled(False)
        self.btn_descargar.setText("Descargando...")

        # Mostrar barra y estado
        self.barra.show()
        self.label_estado.show()
        self.label_estado.setText("Iniciando descarga...")
        self.label.setText(
            f"⬇ Descargando actualización v{self.version_nueva}...<br>"
            f"Por favor no cierres la aplicación."
        )

        # Iniciar hilo de descarga
        self.hilo_descarga = DescargaThread(self.url_descarga)
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

        # Ejecutar el instalador y cerrar la app
        self._ejecutar_instalador(ruta_installer)

    def descarga_error(self, mensaje):
        self.label.setText(f"❌ {mensaje}")
        self.barra.hide()
        self.label_estado.hide()
        self.btn_descargar.setText("Reintentar")
        self.btn_descargar.setEnabled(True)
        self.btn_despues.setEnabled(True)

    def _ejecutar_instalador(self, ruta):
        """Lanza el instalador y cierra la app actual"""
        try:
            # /SILENT hace la instalación sin mostrar el wizard completo
            # /CLOSEAPPLICATIONS cierra la app si está abierta
            subprocess.Popen(
                [ruta, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
                creationflags=subprocess.DETACHED_PROCESS,
            )
        except Exception as e:
            self.label.setText(f"❌ No se pudo abrir el instalador: {str(e)}")
            return

        # Cerrar la aplicación actual para que el instalador pueda reemplazar el .exe
        sys.exit(0)


# ============================================================
# HILO DE VERIFICACIÓN
# ============================================================
class VerificadorThread(QThread):
    hay_actualizacion = pyqtSignal(str, str)

def run(self):
    try:
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        installer_path = os.path.join(temp_dir, "Installer_Gestorex.exe")

        session = requests.Session()

        # Primera petición
        response = session.get(self.url, stream=True, timeout=60)
        response.raise_for_status()

        # ── Detectar si Drive devolvió página de confirmación ──
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            # Extraer el link de confirmación real de la página
            html = response.text
            import re
            match = re.search(r'href="(/uc\?export=download[^"]+confirm=[^"]+)"', html)
            if match:
                confirm_url = "https://drive.google.com" + match.group(1).replace("&amp;", "&")
                response = session.get(confirm_url, stream=True, timeout=60)
                response.raise_for_status()
            else:
                self.error.emit("No se pudo obtener el link de descarga de Google Drive.")
                return

        # Obtener tamaño total
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

        # ── Verificar que el archivo descargado es un .exe válido ──
        with open(installer_path, "rb") as f:
            header = f.read(2)
            if header != b"MZ":  # Todo .exe válido empieza con "MZ"
                self.error.emit(
                    "El archivo descargado no es válido.\n"
                    "Intenta descargar manualmente desde Google Drive."
                )
                return

        self.completado.emit(installer_path)

    except requests.exceptions.Timeout:
        self.error.emit("La descarga tardó demasiado. Intenta de nuevo.")
    except requests.exceptions.ConnectionError:
        self.error.emit("Sin conexión a internet.")
    except Exception as e:
        self.error.emit(f"Error al descargar: {str(e)}")


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def verificar_actualizacion_async(parent_widget):
    hilo = VerificadorThread()

    def mostrar_dialogo(version_nueva, url_descarga):
        dialogo = DialogoActualizacion(
            version_nueva=version_nueva, url_descarga=url_descarga, parent=parent_widget
        )
        dialogo.exec_()

    hilo.hay_actualizacion.connect(mostrar_dialogo)
    hilo.start()
    return hilo
