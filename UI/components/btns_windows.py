from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor
from config import BG_COLOR


class WindowButtons(QWidget):
    """
    Botones de ventana (minimizar, maximizar, cerrar) 
    para colocar dentro del contenido de la ventana.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # La ventana siempre inicia maximizada, así que el estado es True
        self.is_maximized = True
        
        self.setup_ui()
        self.apply_styles()
        
        # ← CORREGIDO: Iniciar con icono de restaurar (❐) porque ya está maximizada
        self.btn_maximize.setText("❐")
    
    def setup_ui(self):
        self.setFixedHeight(35)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(8)
        
        # Espaciador para empujar botones a la derecha
        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(left_spacer)
        
        # Botón minimizar
        self.btn_minimize = QPushButton("−")
        self.btn_minimize.setFixedSize(30, 22)
        self.btn_minimize.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_minimize.clicked.connect(self.minimize_window)
        layout.addWidget(self.btn_minimize)
        
        # Botón maximizar/restaurar
        self.btn_maximize = QPushButton("□")
        self.btn_maximize.setFixedSize(30, 22)
        self.btn_maximize.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_maximize.clicked.connect(self.toggle_maximize)
        layout.addWidget(self.btn_maximize)
        
        # Botón cerrar
        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(30, 22)
        self.btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_close.clicked.connect(self.close_window)
        layout.addWidget(self.btn_close)
    
    def apply_styles(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_COLOR};
            }}
            QPushButton {{
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 16px;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.15);
            }}
        """)
        
        # Estilo especial para cerrar
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e81123;
            }
        """)
    
    def minimize_window(self):
        self.parent.showMinimized()
    
    def toggle_maximize(self):
        if self.is_maximized:
            self.parent.showNormal()
            self.btn_maximize.setText("□")
            self.is_maximized = False
        else:
            self.parent.showMaximized()
            self.btn_maximize.setText("❐")
            self.is_maximized = True
    
    def close_window(self):
        self.parent.close()