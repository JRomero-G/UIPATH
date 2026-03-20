import os
import math
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QLabel, QWidget

from UI.config import BASE_DIR, ASSETS_DIR, WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR
from UI.components.base_window import BaseWindow

from UI.views.workspace_user import WorkspaceUserUI
from UI.views.workspace_manager import WorkspaceManagerUI


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
        self.speed = 0.22

        self.spacing = 30

        for i in range(self.dot_count):
            dot = QLabel(self)
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

            x = (self.width() - ((self.dot_count - 1) * self.spacing)) // 2 + i * self.spacing
            y = (self.height() - size) // 2

            dot.setGeometry(x, y, size, size)
            dot.setStyleSheet(self.style(intensity))

        self.phase += self.speed


# ================== LOADING UI ==================
class LoadingUI(BaseWindow):
    def __init__(self, duration_ms=5000, rol=False):
        super().__init__()
        self.rol = rol
        self.duration_ms = duration_ms

        # Sin bordes ni título nativo
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Gestorex - Iniciando")
        self.setStyleSheet(f"background-color:{BG_COLOR};")
        
        # Tamaño inicial (se maximizará después)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # ===== LOGO =====
        self.logo = QLabel(self)
        pm = QPixmap(os.path.join(ASSETS_DIR, "logo.png"))
        if not pm.isNull():
            self.original_pixmap = pm
            self.logo.setPixmap(pm.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.logo.setAlignment(Qt.AlignCenter)

        # ===== PUNTOS =====
        self.dots = LoadingDots(self)

        # ===== TEXTO =====
        self.text = QLabel("Iniciando...", self)
        self.text.setFont(QFont("Arial", 16))
        self.text.setStyleSheet("color: rgba(255,255,255,180);")
        self.text.setAlignment(Qt.AlignCenter)

        # ===== DURACIÓN CONFIGURABLE =====
        QTimer.singleShot(self.duration_ms, self.finish_loading)

    # Mostrar maximizado y actualizar posiciones
    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()
        QTimer.singleShot(100, self.update_positions)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_positions()

    # ================= POSICIONES CENTRADAS EN PANTALLA =================
    def update_positions(self):
        w = self.width()
        h = self.height()

        # Tamaño del logo (proporcional al ancho)
        logo_size = min(300, int(w * 0.20))
        
        if hasattr(self, "original_pixmap"):
            scaled = self.original_pixmap.scaled(
                logo_size, 
                logo_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.logo.setPixmap(scaled)

        # Alturas de cada elemento
        dots_height = 40
        text_height = 30
        
        # Espacios reducidos entre elementos
        gap_logo_dots = 15
        gap_dots_text = 10
        
        # Calcular altura total del grupo
        total_height = logo_size + gap_logo_dots + dots_height + gap_dots_text + text_height
        
        # Calcular posición Y inicial para centrar todo el grupo
        start_y = (h - total_height) // 2
        
        # Posicionar logo
        logo_y = start_y
        self.logo.setGeometry(
            (w - logo_size) // 2,
            logo_y,
            logo_size,
            logo_size
        )
        
        # Posicionar puntos (debajo del logo)
        dots_y = logo_y + logo_size + gap_logo_dots
        self.dots.setGeometry(0, dots_y, w, dots_height)
        
        # Posicionar texto (debajo de los puntos)
        text_y = dots_y + dots_height + gap_dots_text
        self.text.setGeometry(0, text_y, w, text_height)

    # ================== FINALIZAR LOADING ==================
    def finish_loading(self):
        if self.rol is True:
            self.workspace = WorkspaceManagerUI()
        else:
            self.workspace = WorkspaceUserUI()

        self.workspace.show()
        QTimer.singleShot(2000, self.hide)