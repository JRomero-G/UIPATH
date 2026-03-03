import os
import requests
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QLabel, QLineEdit, QMessageBox

from config import BASE_DIR, ASSETS_DIR, WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR
from config import set_session, _session, get_session
from components.base_window import BaseWindow
from components.animated_background import AnimatedCurvedLine
from components.animated_input import AnimatedInput
from components.neon_button import NeonButton
from components.btns_windows import WindowButtons  # ← IMPORTADO


from ..views.workspace_manager import WorkspaceManagerUI
from ..views.workspace_user import WorkspaceUserUI
from ..views.loading import LoadingUI


class LoginUI(BaseWindow):
    def __init__(self, rol=None, duration_ms=3000):
        super().__init__()
         
        self.rol = rol
        self.duration_ms = duration_ms
        self.setAttribute(Qt.WA_DeleteOnClose)

        # ================= CONFIGURACIÓN =================
        self.setWindowTitle("Neon Login")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        # ================= BOTONES VENTANA =================
        # ← AÑADIDO: Botones minimizar/maximizar/cerrar en parte superior
        self.window_buttons = WindowButtons(self)
        self.window_buttons.setGeometry(0, 0, WINDOW_WIDTH, 35)

        # ================= LÍNEAS ANIMADAS (RESPONSIVE) =================
        self.top_line = AnimatedCurvedLine([], self, delay=0.0)
        self.middle_line = AnimatedCurvedLine([], self, delay=0.6)
        self.bottom_line = AnimatedCurvedLine([], self, delay=0.0)

        # ================= TEXTO SUPERIOR =================
        self.powered = QLabel("Powered by Nexus Ingeniería", self)
        self.powered.setFont(QFont("Arial", 10))
        self.powered.setStyleSheet("color: rgba(255,255,255,180);")
        self.powered.adjustSize()

        # ================= TÍTULO =================
        self.title = QLabel("Login", self)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Arial", 32, QFont.Bold))
        self.title.setStyleSheet("color: white;")

        # ================= INPUTS =================
        self.user = AnimatedInput("USUARIO", 0, 0, self)
        self.pwd = AnimatedInput("CONTRASEÑA", 0, 0, self)
        self.pwd.setEchoMode(QLineEdit.Password)

        # ================= BOTÓN =================
        self.btn_login = NeonButton("INGRESAR", 0, 0, self)
        self.btn_login.clicked.connect(self.open_loading)

        # ✅ AGREGADO: permitir Enter para ingresar
        self.user.returnPressed.connect(self.open_loading)
        self.pwd.returnPressed.connect(self.open_loading)

        # ================= LOGO =================
        self.logo = QLabel(self)
        pm = QPixmap(os.path.join(ASSETS_DIR, "logo.png"))
        if not pm.isNull():
            self.original_pixmap = pm
            pm = pm.scaled(340, 340, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo.setPixmap(pm)

    # ================= EVENTOS =================
    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()
        QTimer.singleShot(50, self.update_positions)
        QTimer.singleShot(60, self.update_lines)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_positions()
        self.update_lines()

    # ================= POSICIONES CENTRADAS =================
    def update_positions(self):
        w = self.width()
        h = self.height()

        # ← AÑADIDO: Actualizar ancho de botones al redimensionar
        self.window_buttons.setGeometry(0, 0, w, 35)

        # Powered by (esquina superior derecha)
        self.powered.adjustSize()
        self.powered.move(w - self.powered.width() - 20, 50)

        # ===== DIMENSIONES DEL FORMULARIO =====
        form_width = 360
        input_height = 48
        button_height = 52
        title_height = 70
        gap = 15  # Espacio entre elementos del formulario

        # ===== DIMENSIONES DEL LOGO (MÁS GRANDE) =====
        # Logo más grande: 45% del alto de pantalla, máximo 450px
        logo_size = min(450, int(h * 0.45))
        
        if hasattr(self, 'original_pixmap'):
            scaled_logo = self.original_pixmap.scaled(
                logo_size, logo_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.logo.setPixmap(scaled_logo)
        
        pm = self.logo.pixmap()
        logo_width = pm.width() if pm else logo_size
        logo_height = pm.height() if pm else logo_size

        # ===== CALCULAR ANCHOS TOTALES =====
        # Espacio entre formulario y logo
        center_gap = 100
        
        # Ancho total del grupo completo
        total_group_width = form_width + center_gap + logo_width
        
        # Posición X inicial para centrar todo el grupo
        start_x = (w - total_group_width) // 2
        
        # ===== CALCULAR ALTURA TOTAL DEL GRUPO =====
        # Altura del formulario
        form_total_height = title_height + gap + input_height + gap + input_height + gap + button_height
        
        # La altura del grupo es el máximo entre formulario y logo
        group_height = max(form_total_height, logo_height)
        
        # Posición Y inicial para centrar verticalmente
        start_y = (h - group_height) // 2

        # ===== POSICIONAR FORMULARIO (IZQUIERDA) =====
        form_x = start_x
        # Centrar formulario verticalmente respecto al logo
        form_y = start_y + (group_height - form_total_height) // 2
        
        # Título
        self.title.setGeometry(form_x, form_y, form_width, title_height)
        
        # Input usuario
        input_y1 = form_y + title_height + gap
        self.user.setGeometry(form_x, input_y1, form_width, input_height)
        
        # Input contraseña
        input_y2 = input_y1 + input_height + gap
        self.pwd.setGeometry(form_x, input_y2, form_width, input_height)
        
        # Botón
        button_y = input_y2 + input_height + gap
        self.btn_login.setGeometry(form_x, button_y, form_width, button_height)

        # ===== POSICIONAR LOGO (DERECHA) =====
        logo_x = form_x + form_width + center_gap
        logo_y = start_y + (group_height - logo_height) // 2
        
        self.logo.setGeometry(logo_x, logo_y, logo_width, logo_height)

    # ================= LÍNEAS RESPONSIVE (NO TOCAR) =================
    def update_lines(self):
        w = self.width()
        h = self.height()

        self.top_line.points = [
            (0, 70),
            (w * 0.3, 20),
            (w * 0.6, 140),
            (w, 90)
        ]

        self.middle_line.points = [
            (0, h - 120),
            (w * 0.3, h - 80),
            (w * 0.6, h - 120),
            (w, h - 80)
        ]

        self.bottom_line.points = [
            (0, h - 80),
            (w * 0.35, h - 40),
            (w * 0.7, h - 80),
            (w, h - 40)
        ]

        self.top_line.update()
        self.middle_line.update()
        self.bottom_line.update()

    # ================= LOGIN =================
    def open_loading(self):
        USUARIO = self.user.text().strip()
        PASSWORD = self.pwd.text().strip()

        if not USUARIO or not PASSWORD:
            QMessageBox.warning(self, "Error", "Debe ingresar usuario y contraseña.")
            return

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
                #guardar token y usuario
                data = response.json()
                token = data["access_token"]
                user_info = data["usuario"]
                rol = user_info.get("es_admin")
                user = user_info.get("nombre")

                print("-Usuario: ", user, " -Es Administrador?:", rol)

                set_session({"token": token, "usuario": user_info})
                #abrir loading y worksapaces segun rol
                self.loading = LoadingUI(rol=rol, duration_ms=3000)
                self.loading.show()
                QTimer.singleShot(2000, self.hide)

            else:
                QMessageBox.warning(self, "Error", "Credenciales inválidas.")

        except requests.RequestException:
            QMessageBox.critical(self, "Error", "No se pudo conectar al servidor.")