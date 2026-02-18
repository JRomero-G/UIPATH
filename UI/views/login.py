import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QLabel, QLineEdit

from config import BASE_DIR, ASSETS_DIR, WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR
from config import set_session, _session, get_session
from components.base_window import BaseWindow
from components.animated_background import AnimatedCurvedLine
from components.animated_input import AnimatedInput
from components.neon_button import NeonButton

# Importaciones nuevas Jason modif
import requests  # se instalara esto
from PyQt5.QtWidgets import QMessageBox
from views.workspace_manager import WorkspaceManagerUI
from views.workspace_user import WorkspaceUserUI
from views.loading import LoadingUI


class LoginUI(BaseWindow):
    def __init__(self, rol=None, duration_ms=3000):
        super().__init__()

        self.rol = rol
        self.duration_ms = duration_ms
        # CLAVE: destruir esta ventana al cerrarse
        self.setAttribute(Qt.WA_DeleteOnClose)

        # ================= CONFIGURACIÓN =================
        self.setWindowTitle("Neon Login")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        # ================= LÍNEAS ANIMADAS  =================
        AnimatedCurvedLine(
            [(0, 70), (320, 20), (650, 140), (1000, 90)], self, delay=0.0
        )

        AnimatedCurvedLine(
            [(0, 520), (300, 560), (650, 520), (1000, 560)], self, delay=0.6
        )

        AnimatedCurvedLine(
            [(0, 560), (350, 600), (700, 560), (1000, 600)], self, delay=0.0
        )

        # ================= TEXTO SUPERIOR =================
        powered = QLabel("Powered by Nexus Ingeniería", self)
        powered.setFont(QFont("Arial", 10))
        powered.setStyleSheet("color: rgba(255,255,255,180);")
        powered.adjustSize()
        powered.move(self.width() - powered.width() - 20, 20)

        # ================= TÍTULO =================
        title = QLabel("Login", self)
        title.setGeometry(100, 160, 360, 70)
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 32, QFont.Bold))
        title.setStyleSheet("color: white;")

        # ================= INPUTS =================
        self.user = AnimatedInput("USUARIO", 100, 250, self)
        self.pwd = AnimatedInput("CONTRASEÑA", 100, 320, self)
        self.pwd.setEchoMode(QLineEdit.Password)

        # ================= BOTÓN =================
        self.btn_login = NeonButton("INGRESAR", 100, 395, self)
        self.btn_login.clicked.connect(self.open_loading)
        #funcion con teclas enter
        self.user.returnPressed.connect(self.open_loading)
        self.pwd.returnPressed.connect(self.open_loading)

        # ================= LOGO =================
        self.logo = QLabel(self)
        pm = QPixmap(os.path.join(ASSETS_DIR, "logo.png"))
        if not pm.isNull():
            pm = pm.scaled(340, 340, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo.setPixmap(pm)
            self.logo.setGeometry(
                self.width() - pm.width() - 80,
                (self.height() - pm.height()) // 2,
                pm.width(),
                pm.height(),
            )

    # ================= ABRIR LOADING - Jason  =================
    def open_loading(self):
        # ===== VALIDACIÓN =====
        USUARIO = self.user.text().strip()
        PASSWORD = self.pwd.text().strip()

        if not USUARIO or not PASSWORD:
            QMessageBox.warning(self, "Error", "Debe ingresar usuario y contraseña.")
            return
        else:
            try:
                response = requests.post(
                    "http://127.0.0.1:8000/auth/login",
                    json={"username": USUARIO, "password": PASSWORD},
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    # Guardar token y usuario
                    token = data["access_token"]
                    user_info = data["usuario"]
                    rol = user_info.get("es_admin")
                    user = user_info.get("nombre")
                    print("-Usuario: ", user, " -Es Administrador?:", rol)
                    set_session({"token": token, "usuario": user_info})
                    # Abrir workspace según rol
                    # ===== ABRIR LOADING =====
                    self.loading = LoadingUI(rol=rol, duration_ms=3000)
                    self.loading.show()
                    self.hide()

                else:
                    QMessageBox.warning(self, "Error", "Credenciales inválidas.")
                    return
            except requests.RequestException:
                QMessageBox.critical(self, "Error", "No se pudo conectar al servidor.")
                return


""" Comentado para pruebas de login real
def open_loading(self):
        self.loading = LoadingUI()   # referencia viva
        self.loading.show()
        self.close()
"""
