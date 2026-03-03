import os
from turtle import color

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
    QVBoxLayout, QHBoxLayout, QApplication, QStackedWidget,
    QGraphicsDropShadowEffect, QFrame, QSizePolicy
)

from config import *
from components.base_window import BaseWindow
from components.btns_windows import WindowButtons


class BaseButton(QPushButton):
    """ Botón unificado estilo sólido. Todos los botones se comportan como los de 'Eliminar'. """
    def __init__(self, text, color="#00ff88", parent=None):
        super().__init__(text, parent)
        self.color = color
        self.is_active = False
        self.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)
        self.setMaximumHeight(48)
        self.update_style()

    def update_style(self):
        if self.is_active:
            background = self.color
            text_color = "white"
        else:
            background = "transparent"
            text_color = self.color

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {background};
                border: 2px solid {self.color};
                border-radius: 10px;
                color: {text_color};
                padding: 0 25px;
            }}
            QPushButton:hover {{
                background-color: {self.color};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {self.color};
                color: white;
            }}
        """)

    def set_active(self, active):
        self.is_active = active
        self.update_style()


class StaticInput(QLineEdit):
    """Input con color personalizable"""
    def __init__(self, placeholder="", parent=None, color="#00ff88"):
        super().__init__(parent)
        self.color = color
        self.setPlaceholderText(placeholder)
        self.setFont(QFont("Segoe UI", 11))
        self.setMinimumHeight(40)
        self.setMaximumHeight(45)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: rgba(30, 40, 60, 200);
                border: 1px solid {self.color}60;
                border-radius: 8px;
                color: #ffffff;
                padding-left: 15px;
                padding-right: 15px;
            }}
            QLineEdit:hover {{
                border: 1px solid {self.color};
                background-color: rgba(35, 50, 75, 220);
            }}
            QLineEdit:focus {{
                border: 1px solid {self.color};
                background-color: rgba(40, 55, 85, 240);
            }}
        """)


class StaticComboBox(QComboBox):
    """ComboBox con color personalizable"""
    def __init__(self, parent=None, color="#00ff88"):
        super().__init__(parent)
        self.color = color
        self.setFont(QFont("Segoe UI", 11))
        self.setMinimumHeight(40)
        self.setMaximumHeight(45)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.addItems(["Seleccione rol...", "Gerente", "Empleado"])
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: rgba(30, 40, 60, 200);
                border: 1px solid {self.color}60;
                border-radius: 8px;
                color: white;
                padding-left: 15px;
            }}
            QComboBox:hover {{
                border: 1px solid {self.color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 40px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 7px solid {self.color};
                margin-right: 15px;
            }}
            QComboBox QAbstractItemView {{
                background-color: rgb(25, 35, 55);
                border: 1px solid {self.color};
                color: white;
                selection-background-color: {self.color}50;
                padding: 6px;
            }}
        """)


class PasswordInput(QWidget):
    """Input de contraseña - ojito SIN efecto hover"""
    def __init__(self, parent=None, color="#00ff88"):
        super().__init__(parent)
        self.color = color
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMaximumHeight(45)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.input = StaticInput("Contraseña", color=color)
        self.input.setEchoMode(QLineEdit.Password)
        self.input.setMaximumHeight(45)

        self.eye_btn = QPushButton("🔓")
        self.eye_btn.setFixedSize(42, 42)
        self.eye_btn.setCheckable(True)
        self.eye_btn.setCursor(Qt.PointingHandCursor)
        self.eye_btn.setFont(QFont("Segoe UI", 14))
        self.eye_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {self.color}80;
            }}
        """)
        self.eye_btn.toggled.connect(self.toggle_password)

        layout.addWidget(self.input, stretch=1)
        layout.addWidget(self.eye_btn)

    def toggle_password(self, checked):
        if checked:
            self.input.setEchoMode(QLineEdit.Normal)
            self.eye_btn.setText("🔒")
            self.eye_btn.setStyleSheet(f"color: {self.color}; background: transparent; border: none;")
        else:
            self.input.setEchoMode(QLineEdit.Password)
            self.eye_btn.setText("🔓")
            self.eye_btn.setStyleSheet(f"color: {self.color}80; background: transparent; border: none;")


class UserInfoDisplay(QWidget):
    """Widget para mostrar información de usuario"""
    def __init__(self, parent=None, color="#ff4444"):
        super().__init__(parent)
        self.color = color
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(160)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(30, 40, 60, 150);
                border: 1px solid {self.color}50;
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(25, 20, 25, 20)

        campos = [
            ("Nombre:", "Juan Pérez García"),
            ("Usuario:", "@juanperez"),
            ("Correo:", "juan@email.com"),
            ("Rol:", "Administrador")
        ]

        for label_text, valor_text in campos:
            row = QWidget()
            row.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(15)

            lbl = QLabel(label_text)
            lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
            lbl.setStyleSheet(f"color: {self.color}; background: transparent;")
            lbl.setFixedWidth(90)

            val = QLabel(valor_text)
            val.setFont(QFont("Segoe UI", 12))
            val.setStyleSheet("color: white; background: transparent;")
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            row_layout.addWidget(lbl)
            row_layout.addWidget(val, stretch=1)
            layout.addWidget(row)


class SearchComboWithButton(QWidget):
    """ComboBox de búsqueda con botón"""
    def __init__(self, placeholder="Buscar...", items=None, parent=None, color="#00ff88"):
        super().__init__(parent)
        self.color = color
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMaximumHeight(45)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.combo = QComboBox()
        self.combo.setFont(QFont("Segoe UI", 11))
        self.combo.setMinimumHeight(40)
        self.combo.setMaximumHeight(45)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.setEditable(False)
        #self.combo.lineEdit().setReadOnly(True)
        #self.combo.lineEdit().setPlaceholderText(placeholder)

        if items:
            self.combo.addItems(items)

        self.combo.setStyleSheet(f"""
            QComboBox {{
                background-color: rgba(30, 40, 60, 200);
                border: 1px solid {self.color}60;
                border-radius: 8px;
                color: white;
                padding-left: 15px;
            }}
            QComboBox:hover {{
                border: 1px solid {self.color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 40px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 7px solid {self.color};
                margin-right: 15px;
            }}
            QComboBox QAbstractItemView {{
                background-color: rgb(25, 35, 55);
                border: 1px solid {self.color};
                color: white;
                selection-background-color: {self.color}50;
                padding: 6px;
            }}
        """)

        self.btn_buscar = BaseButton("BUSCAR", color=color)
        self.btn_buscar.setMinimumWidth(120)
        self.btn_buscar.setMaximumWidth(160)
        self.btn_buscar.setFixedHeight(42)

        layout.addWidget(self.combo, stretch=1)
        layout.addWidget(self.btn_buscar)


class UserManagementUI(BaseWindow):
    COLORES = {
        0: "#00ff88",
        1: "#ff9500",
        2: "#ff3333"
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestorex 1.1 - Usuario")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        self.window_buttons = WindowButtons(self)
        self.window_buttons.setGeometry(0, 0, WINDOW_WIDTH, 35)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 50, 30, 20)
        main_layout.setSpacing(18)

        self.central = QWidget(self)
        self.central.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgb(8, 12, 25),
                    stop: 0.5 rgb(12, 18, 35),
                    stop: 1 rgb(8, 12, 25)
                );
            }
        """)
        central_layout = QVBoxLayout(self.central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self.title_bar = WindowButtons(parent=self)
        central_layout.addWidget(self.title_bar)

        header = self.create_header()
        central_layout.addWidget(header)

        center_container = QWidget()
        center_container.setStyleSheet("background: transparent;")
        center_layout = QHBoxLayout(center_container)
        center_layout.setContentsMargins(40, 20, 40, 30)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        center_layout.addWidget(self.stack, stretch=1)

        central_layout.addWidget(center_container, stretch=1)

        self.setup_crear()
        self.setup_modificar()
        self.setup_eliminar()

        self.show_tab(0)

    def create_header(self):
        header = QWidget()
        header.setMinimumHeight(70)
        header.setMaximumHeight(85)
        header.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 16, 30, 180);
                border-bottom: 1px solid rgba(100, 120, 150, 0.2);
            }
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(30, 0, 30, 0)

        title = QLabel("Gestión de Usuarios")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        layout.addWidget(title)
        layout.addStretch()

        self.tabs = []
        tab_data = [
            ("➕ Crear Usuario", self.COLORES[0]),
            ("✏️ Modificar Usuario", self.COLORES[1]),
            ("🗑️ Eliminar Usuario", self.COLORES[2])
        ]

        tabs_widget = QWidget()
        tabs_widget.setStyleSheet("background: transparent;")
        tabs_layout = QHBoxLayout(tabs_widget)
        tabs_layout.setSpacing(10)
        tabs_layout.setContentsMargins(0, 0, 0, 0)

        for i, (text, color) in enumerate(tab_data):
            btn = BaseButton(text, color=color)
            btn.setMinimumWidth(150)
            btn.setMaximumWidth(220)
            btn.setMinimumHeight(40)
            btn.setMaximumHeight(45)
            btn.setProperty("index", i)
            btn.clicked.connect(lambda checked, idx=i: self.show_tab(idx))
            self.tabs.append(btn)
            tabs_layout.addWidget(btn)

        layout.addWidget(tabs_widget)
        return header

    def show_tab(self, index):
        self.stack.setCurrentIndex(index)
        for btn in self.tabs:
            btn_index = btn.property("index")
            btn.set_active(btn_index == index)

    def create_tab_card(self, title_text, color):
        tab_widget = QWidget()
        tab_widget.setStyleSheet("background: transparent;")
        tab_layout = QHBoxLayout(tab_widget)
        tab_layout.setAlignment(Qt.AlignCenter)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setMinimumWidth(450)
        card.setMaximumWidth(700)
        card.setMinimumHeight(420)
        card.setMaximumHeight(580)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(20, 28, 48, 220);
                border: 1px solid {color}40;
                border-radius: 16px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 10)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(40, 30, 40, 25)

        title = QLabel(title_text)
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)
        card_layout.addSpacing(25)

        fields_area = QWidget()
        fields_area.setStyleSheet("background: transparent;")
        fields_layout = QVBoxLayout(fields_area)
        fields_layout.setSpacing(12)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setAlignment(Qt.AlignTop)
        card_layout.addWidget(fields_area, stretch=1)

        button_area = QWidget()
        button_area.setStyleSheet("background: transparent;")
        button_layout = QHBoxLayout(button_area)
        button_layout.setContentsMargins(0, 15, 0, 0)
        button_layout.addStretch()
        card_layout.addWidget(button_area)

        tab_layout.addWidget(card, stretch=1)
        return tab_widget, fields_layout, button_layout

    # === CREAR TAB ===
    def setup_crear(self):
        color = self.COLORES[0]
        container, layout, btn_layout = self.create_tab_card("Nuevo Usuario", color)

        self.input_nombre = StaticInput("Nombre completo", color=color)
        self.input_usuario = StaticInput("Nombre de usuario", color=color)
        self.input_email = StaticInput("Correo electrónico", color=color)
        self.input_password = PasswordInput(color=color)

    # ✅ NUEVO CAMPO: Confirmar contraseña
        self.input_confirm_password = PasswordInput(color=color)
        self.input_confirm_password.input.setPlaceholderText("Confirmar contraseña")

        self.combo_rol = StaticComboBox(color=color)

        layout.addWidget(self.input_nombre)
        layout.addWidget(self.input_usuario)
        layout.addWidget(self.input_email)
        layout.addWidget(self.input_password)
        layout.addWidget(self.input_confirm_password)  # ← agregado aquí
        layout.addWidget(self.combo_rol)
        layout.addStretch()

        btn_crear = BaseButton("CREAR USUARIO", color=color)
        btn_crear.setMinimumWidth(200)
        btn_crear.setMaximumWidth(280)
        btn_layout.addWidget(btn_crear)

        self.stack.addWidget(container)

    # === MODIFICAR TAB ===
    def setup_modificar(self):
        color = self.COLORES[1]
        container, layout, btn_layout = self.create_tab_card("Editar Usuario", color)

        self.search_bar = SearchComboWithButton(
            "🔍 Buscar usuario...",
            items=["Juan Pérez", "Ana López", "Carlos Méndez", "María Ruiz"],
            color=color
        )
        layout.addWidget(self.search_bar)
        layout.addSpacing(20)

        campos = [
            ("Nombre completo", "edit_nombre"),
            ("Nombre de usuario", "edit_usuario"),
            ("Correo electrónico", "edit_email")
        ]

        for placeholder, attr_name in campos:
            inp = StaticInput(placeholder, color=color)
            inp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            setattr(self, attr_name, inp)
            layout.addWidget(inp)

        self.edit_rol = StaticComboBox(color=color)
        layout.addWidget(self.edit_rol)

    # ✅ NUEVOS CAMPOS DE CONTRASEÑA
        self.edit_current_password = PasswordInput(color=color)
        self.edit_current_password.input.setPlaceholderText("Contraseña actual")

        self.edit_new_password = PasswordInput(color=color)
        self.edit_new_password.input.setPlaceholderText("Nueva contraseña")

        layout.addWidget(self.edit_current_password)
        layout.addWidget(self.edit_new_password)

        layout.addStretch()

        btn_guardar = BaseButton("GUARDAR CAMBIOS", color=color)
        btn_guardar.setMinimumWidth(220)
        btn_guardar.setMaximumWidth(300)
        btn_layout.addWidget(btn_guardar)

        self.stack.addWidget(container)

    # === ELIMINAR TAB ===
    def setup_eliminar(self):
        color = self.COLORES[2]
        container, layout, btn_layout = self.create_tab_card("Eliminar Usuario", color)

        self.search_bar_del = SearchComboWithButton(
            "🔍 Buscar usuario a eliminar...",
            items=["Juan Pérez", "Ana López", "Carlos Méndez", "María Ruiz"],
            color=color
        )
        layout.addWidget(self.search_bar_del)
        layout.addSpacing(20)

        self.user_info = UserInfoDisplay(color=color)
        layout.addWidget(self.user_info)
        layout.addStretch()

        btn_eliminar = BaseButton("ELIMINAR", color=color)
        btn_eliminar.setMinimumWidth(150)
        btn_eliminar.setMaximumWidth(200)
        btn_layout.addWidget(btn_eliminar)

        self.stack.addWidget(container)

    # === EVENTOS DE VENTANA ===
    def showEvent(self, event):
        super().showEvent(event)
        self.central.setGeometry(0, 0, self.width(), self.height())
        self.showMaximized()
        self.window_buttons.setGeometry(0, 0, self.width(), 35)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'central'):
            self.central.setGeometry(0, 0, self.width(), self.height())
            self.window_buttons.setGeometry(0, 0, self.width(), 35)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 11)
    app.setFont(font)
    window = UserManagementUI()
    window.show()
    sys.exit(app.exec_())
