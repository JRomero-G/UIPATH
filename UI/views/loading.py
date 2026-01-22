import os
import math
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QLabel, QWidget


from UI.config import BASE_DIR, ASSETS_DIR, WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR
from UI.config import set_session, _session, get_session
from ..components.base_window import BaseWindow

# jason
from ..views.workspace_user import WorkspaceUserUI
from ..views.workspace_manager import WorkspaceManagerUI


# ================== PUNTOS TIPO VIDEO ONDA REAL ==================
class LoadingDots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.dot_count = 7
        self.dots = []

        self.setFixedHeight(40)

        # Tamaños
        self.min_size = 8
        self.max_size = 20

        # Onda
        self.phase = 0.0
        self.speed = 0.22  # velocidad equilibrada

        self.spacing = 30
        total_width = (self.dot_count - 1) * self.spacing
        self.start_x = (WINDOW_WIDTH - total_width) // 2
        self.center_y = 18

        for i in range(self.dot_count):
            dot = QLabel(self)
            dot.setGeometry(
                self.start_x + i * self.spacing,
                self.center_y,
                self.min_size,
                self.min_size,
            )
            dot.setStyleSheet(self.style(0.0))
            self.dots.append(dot)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(60)

    def style(self, intensity: float):
        alpha = int(80 + intensity * 170)
        radius = int(4 + intensity * 6)
        return f"""
            background-color: rgba(0,220,255,{alpha});
            border-radius: {radius}px;
        """

    def animate(self):
        for i, dot in enumerate(self.dots):
            wave = math.sin(self.phase - i * 0.7)
            intensity = (wave + 1) / 2
            size = int(self.min_size + intensity * (self.max_size - self.min_size))

            x = self.start_x + i * self.spacing
            y = self.center_y + (self.min_size - size) // 2

            dot.setGeometry(x, y, size, size)
            dot.setStyleSheet(self.style(intensity))

        self.phase += self.speed


# ================== LOADING UI ==================
class LoadingUI(BaseWindow):
    def __init__(self, duration_ms=5000, rol=bool):  # rol jason
        super().__init__()
        self.rol = rol

        self.duration_ms = duration_ms  # ⏱ duración configurable

        self.setWindowTitle("Gestorex - Iniciando")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        # ===== LOGO =====
        self.logo = QLabel(self)
        pm = QPixmap(os.path.join(ASSETS_DIR, "logo.png"))
        if not pm.isNull():
            pm = pm.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo.setPixmap(pm)
            self.logo.setAlignment(Qt.AlignCenter)
            self.logo.setGeometry(0, 140, self.width(), pm.height())

        # ===== PUNTOS =====
        self.dots = LoadingDots(
            self
        )  ## verrificar aqui despues vara ver si es correcto
        self.dots.setGeometry(0, 470, self.width(), 40)

        # ===== TEXTO =====
        self.text = QLabel("Iniciando...", self)
        self.text.setFont(QFont("Arial", 16))
        self.text.setStyleSheet("color: rgba(255,255,255,180);")
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setGeometry(0, 525, self.width(), 30)

        # ===== DURACIÓN CONFIGURABLE =====
        QTimer.singleShot(self.duration_ms, self.finish_loading)

    # ===== FINALIZAR LOADING EMPLEADO O ADMIN=====
    def finish_loading(self):
        if self.rol is True:
            # ABRIR WORKSPACE ADMIN
            self.workspace = WorkspaceManagerUI()
        else:
            # ABRIR WORKSPACE USER
            self.workspace = WorkspaceUserUI()

        self.workspace.show()
        self.hide()
