import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QLabel, QLineEdit

from config import *
from components.base_window import BaseWindow
from components.animated_background import AnimatedCurvedLine
from components.animated_input import AnimatedInput
from components.neon_button import NeonButton
from views.loading import LoadingUI


class LoginUI(BaseWindow):
    def __init__(self):
        super().__init__()

        # CLAVE: destruir esta ventana al cerrarse
        self.setAttribute(Qt.WA_DeleteOnClose)

        # ================= CONFIGURACIÓN =================
        self.setWindowTitle("Neon Login")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        # ================= LÍNEAS ANIMADAS  =================
        AnimatedCurvedLine(
            [(0, 70), (320, 20), (650, 140), (1000, 90)],
            self, delay=0.0
        )

        AnimatedCurvedLine(
            [(0, 520), (300, 560), (650, 520), (1000, 560)],
            self, delay=0.6
        )

        AnimatedCurvedLine(
            [(0, 560), (350, 600), (700, 560), (1000, 600)],
            self, delay=0.0
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
                pm.height()
            )

    def open_loading(self):
        # ===== VALIDACIÓN =====
        if not self.user.text().strip():
            return

        if not self.pwd.text().strip():
            return

        # ===== ABRIR LOADING =====
        self.loading = LoadingUI()
        self.loading.show()
        self.hide()
