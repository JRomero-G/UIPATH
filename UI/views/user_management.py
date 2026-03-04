import os
from turtle import color

from PyQt5.QtCore import Qt, QTimer, pyqtSignal,QRegularExpression
from PyQt5.QtGui import QFont, QColor,QRegularExpressionValidator
from PyQt5.QtWidgets import (
    QMessageBox, QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
    QVBoxLayout, QHBoxLayout, QApplication, QStackedWidget,
    QGraphicsDropShadowEffect, QFrame, QSizePolicy
)
import requests

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
        self.addItems(["Seleccione rol...", "Administrador", "Empleado"])
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


# Cambios para hacer los campos de eliminar dinamicos y poder
# llenar la informacion desde la consulta
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

        # ====== LABELS ======

        self.lbl_nombre = self._crear_fila("Nombre:")
        self.lbl_usuario = self._crear_fila("Usuario:")
        self.lbl_correo = self._crear_fila("Correo:")
        self.lbl_rol = self._crear_fila("Rol:")

        layout.addWidget(self.lbl_nombre["row"])
        layout.addWidget(self.lbl_usuario["row"])
        layout.addWidget(self.lbl_correo["row"])
        layout.addWidget(self.lbl_rol["row"])

        # Estado inicial
        self.clear()

    def _crear_fila(self, texto):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(15)

        lbl = QLabel(texto)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lbl.setStyleSheet(f"color: {self.color};")

        val = QLabel("--------------")
        val.setFont(QFont("Segoe UI", 12))
        val.setStyleSheet("color: white;")
        val.setWordWrap(True)

        row_layout.addWidget(lbl)
        row_layout.addWidget(val, stretch=1)

        return {
            "row": row,
            "value": val
        }

    # ==========================
    # LIMPIAR
    # ==========================
    def clear(self):

        self.lbl_nombre["value"].setText("--------------")
        self.lbl_usuario["value"].setText("--------------")
        self.lbl_correo["value"].setText("--------------")
        self.lbl_rol["value"].setText("--------------")

    # ==========================
    # CARGAR DATOS
    # ==========================
    def set_data(self, data):

        self.lbl_nombre["value"].setText(data.get("nombre", ""))
        self.lbl_usuario["value"].setText(data.get("usuario", ""))
        self.lbl_correo["value"].setText(data.get("correo", ""))

        if data.get("es_admin"):
            self.lbl_rol["value"].setText("Administrador")
        else:
            self.lbl_rol["value"].setText("Empleado")

class SearchComboWithButton(QWidget):
    """ComboBox de búsqueda con botón"""
    def __init__(self, placeholder="Buscar...", items=None, parent=None, color="#00ff88"):
        super().__init__(parent)

        if items is None:
            items = []

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

        for item in items:
            # Protección
            if not isinstance(item, dict):
                continue

            nombre = item.get("nombre")
            uid = item.get("id")

            if nombre and uid is not None:
                self.combo.addItem(nombre, uid)


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
        #validaciones
        self.aplicar_validaciones()
        self.aplicar_validaciones_modificar()
        

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
        self.input_telefono = StaticInput("Teléfono: +504-0000-0000", color=color)
        self.input_password = PasswordInput(color=color)

    # ✅ NUEVO CAMPO: Confirmar contraseña
        self.input_confirm_password = PasswordInput(color=color)
        self.input_confirm_password.input.setPlaceholderText("Confirmar contraseña")

        self.combo_rol = StaticComboBox(color=color)

        layout.addWidget(self.input_nombre)
        layout.addWidget(self.input_usuario)
        layout.addWidget(self.input_email)
        layout.addWidget(self.input_telefono)
        layout.addWidget(self.input_password)
        layout.addWidget(self.input_confirm_password)  # ← agregado aquí
        layout.addWidget(self.combo_rol)
        layout.addStretch()

        btn_crear = BaseButton("CREAR USUARIO", color=color)
        btn_crear.setMinimumWidth(200)
        btn_crear.setMaximumWidth(280)
        btn_layout.addWidget(btn_crear)

        self.stack.addWidget(container)

        btn_crear.clicked.connect(self.handle_crear_usuario)

    def handle_crear_usuario(self):  
        # Lee los valores de los campos
        nombre = self.input_nombre.text().strip()
        usuario = self.input_usuario.text().strip()
        correo = self.input_email.text().strip()
        telefono = self.input_telefono.text().strip()
        password = self.input_password.input.text()
        confirm_password = self.input_confirm_password.input.text()  # ← nuevo campo
        
        # Determina es_admin según el combobox
        rol = self.combo_rol.currentText()
        if rol == "Administrador":
            es_admin = True
        elif rol == "Empleado":
            es_admin = False
        else:
            QMessageBox.warning(self, "Error", "Debe seleccionar un rol.")
            return
        
        # Valida contraseñas
        if password != confirm_password:
            QMessageBox.warning(self, "Error", "Las contraseñas no coinciden.")
            return
        
        # Llama a la función externa
        resultado = registrar_usuario(nombre, usuario,correo, password, es_admin,telefono)

        if "error" in resultado:
            QMessageBox.critical(self, "Error", resultado["error"])
        else:
            QMessageBox.information(self, "Éxito", resultado["success"])
            # limpiamos los campos
            print("Se registro un nuevo usuario con exito")
            self.input_nombre.clear()
            self.input_usuario.clear() 
            self.input_email.clear()
            self.input_telefono.clear()
            self.input_telefono.setInputMask("+504-0000-0000")
            self.input_password.input.clear()
            self.input_confirm_password.input.clear()
            self.combo_rol.setCurrentIndex(0)
            self.recargar_usuarios()
        

    # === MODIFICAR TAB ===
    def setup_modificar(self):
        color = self.COLORES[1]
        container, layout, btn_layout = self.create_tab_card("Editar Usuario", color)

        self.usuario_actual_id = None
        # Cargar usuarios
        lista_usuarios = self.cargar_usuarios()
        print("DEBUG lista_usuarios:", lista_usuarios)
        
        self.search_bar = SearchComboWithButton(
            items=lista_usuarios,
            color=color
        )
        layout.addWidget(self.search_bar)
        layout.addSpacing(20)

        # 👉 Conectar botón buscar
        self.search_bar.btn_buscar.clicked.connect(self.buscar_usuario)

        campos = [
            ("Nombre completo", "edit_nombre"),
            ("Nombre de usuario", "edit_usuario"),
            ("Correo electrónico", "edit_email"),
            ("Telefono : +504-0000-0000","edit_telefono"),
        ]

        for placeholder, attr_name in campos:
            inp = StaticInput(placeholder, color=color)
            inp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            setattr(self, attr_name, inp)
            layout.addWidget(inp)

        # Rol
        self.edit_rol = StaticComboBox(color=color)
        layout.addWidget(self.edit_rol)

    # ✅ NUEVOS CAMPOS DE CONTRASEÑA
        self.edit_current_password = PasswordInput(color=color)
        self.edit_current_password.input.setPlaceholderText("Nueva contraseña (opcional)")

        self.edit_new_password = PasswordInput(color=color)
        self.edit_new_password.input.setPlaceholderText("Nueva contraseña")

        layout.addWidget(self.edit_current_password)
        layout.addWidget(self.edit_new_password)

        layout.addStretch()

        btn_guardar = BaseButton("GUARDAR CAMBIOS", color=color)
        btn_guardar.clicked.connect(self.guardar_cambios_usuario)
        btn_guardar.setMinimumWidth(220)
        btn_guardar.setMaximumWidth(300)
        btn_layout.addWidget(btn_guardar)

        self.stack.addWidget(container)

    #===================== Buscamos al emplado seleccionado =======================
    def buscar_usuario(self):

        user_id = self.search_bar.combo.currentData()

        if not user_id:
            QMessageBox.warning(self, "Aviso", "Seleccione un usuario")
            return

        data = obtener_informacion_del_usuario(user_id)

        if not data:
            QMessageBox.critical(self, "Error", "No se pudo cargar el usuario")
            return

        self.usuario_actual_id = user_id

        # Llenar campos
        self.edit_nombre.setText(data.get("nombre", ""))
        self.edit_usuario.setText(data.get("usuario", ""))
        self.edit_email.setText(data.get("correo", ""))
        self.edit_telefono.setText(data.get("telefono", ""))

        if data.get("es_admin"):
            self.edit_rol.setCurrentIndex[1]
        else:
            self.edit_rol.setCurrentIndex[2]
        
        # Limpiar password
        self.edit_new_password.input.clear()

    # ====================Guardar los cambios =====================================
    def guardar_cambios_usuario(self):

        if not self.usuario_actual_id:
            QMessageBox.warning(self, "Error", "Primero busque un usuario")
            return

        nombre = self.edit_nombre.text().strip()
        usuario = self.edit_usuario.text().strip()
        email = self.edit_email.text().strip()
        telefono = self.edit_telefono.text().strip()
        password = self.edit_new_password.input.text().strip()

        es_admin = self.edit_rol.currentText() == "Administrador"

        if not all[nombre,usuario,email,telefono]:
            QMessageBox.warning(self, "Error", "Campos obligatorios vacíos")
            return
        

        payload = {
            "nombre": nombre,
            "usuario": usuario,
            "correo": email,
            "telefono": telefono,
            "es_admin": es_admin,
        }

        # Solo enviar password si existe
        if password:
            payload["password"] = password

        try:
            response = requests.put(
                f"http://localhost:8000/usuarios/actualizar/{self.usuario_actual_id}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {get_token()}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )

            if response.status_code == 200:

                QMessageBox.information(self, "Éxito", "Usuario actualizado")
                print("Usuario Actualizado con exito")

                self.edit_new_password.input.clear()
                self.edit_current_password.clear()
                self.edit_nombre.clear()
                self.edit_usuario.clear()
                self.edit_email.clear()
                self.edit_telefono.clear()
                self.edit_rol.setCurrentIndex[0]
                # Recargar lista
                self.recargar_usuarios()

            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Error: {response.text}"
                )
                print(f"Error al guardar los cambios del usuario {response.text}")

        except requests.RequestException as e:
            QMessageBox.critical(self, "Error", str(e))
    
    # ================== cargar empleados ==================
    def cargar_usuarios(self):

            try:
                response = requests.get(
                    "http://localhost:8000/usuarios/empleados-activos",
                    headers={
                        "Authorization": f"Bearer {get_token()}"
                    },
                    timeout=10
                )

                if response.status_code != 200:
                    return []

                data = response.json()

                usuarios = []

                for u in data:
                    usuarios.append({
                        "id": u["id_usuario"],
                        "nombre": u["nombre"]
                    })

                return usuarios

            except Exception as e:
                print("Error al cargar usuarios:", e)
                return []
    

    # === ELIMINAR TAB ===
    def setup_eliminar(self):
        color = self.COLORES[2]
        container, layout, btn_layout = self.create_tab_card("Eliminar Usuario", color)

        self.usuario_actual_id = None

        # Cargar usuarios   
        lista_usuarios = self.cargar_usuarios()

        self.search_bar_del = SearchComboWithButton(
            items= lista_usuarios,
            color=color
        )

        # 👉 Conectar botón buscar
        self.search_bar_del.btn_buscar.clicked.connect(self.buscar_usuario_a_eliminar)

        layout.addWidget(self.search_bar_del)
        layout.addSpacing(20)

        self.user_info = UserInfoDisplay(color=color)
        layout.addWidget(self.user_info)
        layout.addStretch()

        btn_eliminar = BaseButton("ELIMINAR", color=color)
        btn_eliminar.setMinimumWidth(150)
        btn_eliminar.setMaximumWidth(200)
        btn_layout.addWidget(btn_eliminar)
        btn_eliminar.clicked.connect(self.inhabilitar_usuario)

        self.stack.addWidget(container)

    # ============== Buscar informacion Eliminar ======================
    def buscar_usuario_a_eliminar(self):

        user_id = self.search_bar_del.combo.currentData()

        if not user_id:
            QMessageBox.warning(self, "Aviso", "Seleccione un usuario")
            return

        data = obtener_informacion_del_usuario(user_id)

        if not data:
            QMessageBox.critical(self, "Error", "No se pudo cargar el usuario")
            return

        self.usuario_actual_id = user_id

        # Llenar campos
        self.user_info.set_data(data)

        
    # ==================== Deshablitar =====================================
    def inhabilitar_usuario(self):

        if not self.usuario_actual_id:
            QMessageBox.warning(self, "Error", "Primero busque un usuario")
            return


        try:
            response = requests.put(
                f"http://localhost:8000/usuarios/desactivar-usuarios/{self.usuario_actual_id}",
                headers={
                    "Authorization": f"Bearer {get_token()}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )

            if response.status_code == 200:

                QMessageBox.information(self, "Éxito", "Usuario Desactivado")
                print("Usuario Desactivado con exito")

                # Recargar lista
                self.user_info.clear()
                self.usuario_actual_id = None
                # Recargar lista
                self.recargar_usuarios()

            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Error: {response.text}"
                )
                print(f"Error al Desactivar usuario: {response.text}")

        except requests.RequestException as e:
            QMessageBox.critical(self, "Error", str(e))
    
    #================== Recargar usuarios despues de crear,actualizar o inhabilitar ====================
    def recargar_usuarios(self):

        lista = self.cargar_usuarios()

        self.search_bar.combo.clear()
        self.search_bar_del.combo.clear()

        for u in lista:
            self.search_bar.combo.addItem(u["nombre"], u["id"])
            self.search_bar_del.combo.addItem(u["nombre"], u["id"])


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
      
    # ========== Aplicar validaciones ===============
    def aplicar_validaciones(self):

        # ================= TELÉFONO =================
        telefono_regex = QRegularExpression(r"\d{4}-\d{4}-\d{4}")
        telefono_validator = QRegularExpressionValidator(telefono_regex)

        self.input_telefono.setValidator(telefono_validator)


        # ================= EMAIL =================
        email_regex = QRegularExpression(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )
        email_validator = QRegularExpressionValidator(email_regex)

        self.input_email.setValidator(email_validator)


        # ================= PASSWORD =================
        # Min 8 chars, letras y números
        password_regex = QRegularExpression(
            r"^[A-Za-z0-9@$!%*#?&]{8,}$"
        )
        password_validator = QRegularExpressionValidator(password_regex)

        self.input_password.input.setValidator(password_validator)
        self.input_confirm_password.input.setValidator(password_validator)


        # ================= USUARIO =================
        usuario_regex = QRegularExpression(r"^[^\s]+$")
        usuario_validator = QRegularExpressionValidator(usuario_regex)

        self.input_usuario.setValidator(usuario_validator)


        # ================= NOMBRE =================
        nombre_regex = QRegularExpression(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$")
        nombre_validator = QRegularExpressionValidator(nombre_regex)

        self.input_nombre.setValidator(nombre_validator)


    # validaciones para modificacion
    def aplicar_validaciones_modificar(self):

        # ================= TELÉFONO =================
        telefono_regex = QRegularExpression(r"\d{4}-\d{4}-\d{4}")
        validator_tel = QRegularExpressionValidator(telefono_regex)

        self.edit_telefono.setValidator(validator_tel)


        # ================= EMAIL =================
        email_regex = QRegularExpression(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )
        validator_email = QRegularExpressionValidator(email_regex)

        self.edit_email.setValidator(validator_email)


        # ================= PASSWORD =================
        password_regex = QRegularExpression(
            r"^[A-Za-z0-9@$!%*#?&]{8,}$"
        )
        validator_password = QRegularExpressionValidator(password_regex)

        self.edit_current_password.input.setValidator(validator_password)
        self.edit_new_password.input.setValidator(validator_password)


        # ================= USUARIO =================
        usuario_regex = QRegularExpression(r"^[^\s]+$")
        validator_user = QRegularExpressionValidator(usuario_regex)

        self.edit_usuario.setValidator(validator_user)


        # ================= NOMBRE =================
        nombre_regex = QRegularExpression(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$")
        validator_nombre = QRegularExpressionValidator(nombre_regex)

        self.edit_nombre.setValidator(validator_nombre)
        
#=================== FUNCIONES EXTERNAS (API) ==================
def registrar_usuario(nombre, usuario, email, password, es_Admin, telefono):
        # Aquí la lógica para registrar un nuevo usuario
        if not all([nombre, usuario, email, password]):
            return {"error": "Todos los campos son obligatorios."}
        
        try:
            response = requests.post(
                "http://localhost:8000/usuarios/registro",
                json={
                    "usuario": usuario,
                    "nombre": nombre,
                    "password": password,
                    "es_admin": es_Admin,
                    "correo": email,
                    "telefono": telefono
                },
                headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {get_token()}"},
                timeout=10,
            )

            if response.status_code == 200:
                print("Usuario registrado exitosamente.")
                return {"success": "Usuario registrado exitosamente."}
            

        except Exception as e:
            return print(f"Error al registrar usuario: {e}")

# ================= Desactivar Empleado =======================
def eliminar_usuario(usuario_id):
        # Aquí la lógica para eliminar un usuario
        try:
            response = requests.delete(
                f"http://localhost:8000/usuarios/desactivar-usuarios/{usuario_id}",
                headers={"Authorization": f"Bearer {get_token()}"},
                timeout=10,
            )

            if response.status_code == 200:
                print("Usuario eliminado exitosamente.")
                return {"success": "Usuario eliminado exitosamente."}
            

        except Exception as e:
            return print(f"Error al eliminar usuario: {e}")


# ================== Obtener infirmacion actual del empleado ==================
def obtener_informacion_del_usuario(usuario_id):
        # Aquí la lógica para obtener información de un usuario
        try:
            token = get_session().get("token")
            response = requests.get(
                f"http://localhost:8000/usuarios/{usuario_id}",
                headers={ "Content-Type": "application/json","Authorization": f"Bearer {token}"},
                timeout=10,
            )

            if response.status_code == 200:
                usuario_info = response.json()
                print("Información del usuario obtenida exitosamente.")
                return usuario_info
            

        except Exception as e:
            return print(f"Error al obtener información del usuario: {e}")


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 11)
    app.setFont(font)
    window = UserManagementUI()
    window.show()
    sys.exit(app.exec_())
