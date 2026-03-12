import os
from functools import partial
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QColor, QPixmap
from PyQt5.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHBoxLayout,
    QVBoxLayout,
    QHeaderView,
    QMessageBox,
    QComboBox,
)
import requests
from config import WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR, get_session
from UI.components.table_scroll_style import apply_table_scrollbar_style
from components.base_window import BaseWindow
from components.btns_windows import WindowButtons  # ← IMPORTADO



class WorkspaceManagerUI(BaseWindow):
    def __init__(self):
        super().__init__()

        # Guarda asignaciones pendientes
        # { row: {id_infima, usuario_id} }
        self.asignaciones_pendientes = {}

        self.setWindowTitle("Gestorex 1.1 - Manager")

        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        self.window_buttons = WindowButtons(self)
        self.window_buttons.setGeometry(0, 0, WINDOW_WIDTH, 35)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 50, 30, 20)
        main_layout.setSpacing(18)

        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(12)

        # 🔵 BOTÓN USUARIOS (NUEVO)
        self.btn_usuarios = self.menu_usuarios_icon()
        self.btn_usuarios.clicked.connect(self.abrir_ventana_usuarios)

        self.btn_actualizar = self.menu_actualizar("⟳  Actualizar")
        self.btn_actualizar.clicked.connect(self.cargar_datos_bd)

        self.btn_reportes = self.menu_tab("Asignaciones", active=True)

        # ORDEN NUEVO (Usuarios primero)
        menu_layout.addWidget(self.btn_usuarios)
        menu_layout.addWidget(self.btn_actualizar)
        menu_layout.addWidget(self.btn_reportes)
        menu_layout.addStretch()

        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)
        brand_layout.setAlignment(Qt.AlignVCenter)

        logo_label = QLabel()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "..", "assets", "logo2.png")

        pixmap = QPixmap(logo_path).scaled(
            44, 44,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        logo_label.setPixmap(pixmap)

        title = QLabel("Gestorex 1.1")
        title.setFont(QFont("Arial", 15, QFont.Bold))
        title.setStyleSheet("color: white;")

        # ✅ NUEVO: botón Asignar (a la izquierda del logo)
        self.btn_asignar = self.menu_actualizar("Asignar")
        self.btn_asignar.clicked.connect(self.confirmar_asignaciones)  # ✅ usa tu método existente

        brand_layout.addWidget(self.btn_asignar)   # ← primero botón
        brand_layout.addWidget(logo_label)         # ← luego logo (se queda en su sitio)
        brand_layout.addWidget(title)              # ← luego el título

        menu_layout.addLayout(brand_layout)

        main_layout.addLayout(menu_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Usuario", "NIC", "Descripción", "Etapa"]
        )

        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.ElideNone)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 120)

        self.table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.table.verticalHeader().setMinimumSectionSize(38)
        self.table.verticalHeader().setVisible(False)

        self.table.setAlternatingRowColors(True)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(255,255,255,15);
                color: white;
                gridline-color: rgba(255,255,255,25);
                border-radius: 10px;
                alternate-background-color: rgb(255, 255, 255);
                border: 1px solid rgba(255,255,255,90);
            }

            QHeaderView::section {
                background-color: rgba(0,0,0,110);
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
                border-bottom: 2px solid rgba(255,255,255,120);
            }
        """)

        main_layout.addWidget(self.table)
        apply_table_scrollbar_style(self.table)

        self.cargar_datos_bd()

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()
        self.window_buttons.setGeometry(0, 0, self.width(), 35)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.window_buttons.setGeometry(0, 0, self.width(), 35)

    # 🔵 MÉTODO NUEVO BOTÓN REDONDO
    def menu_usuarios_icon(self):
        btn = QPushButton("⚙")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(36, 36)
        btn.setFont(QFont("Arial", 14))
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 35);
                color: white;
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,40);
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 60);
                border: 1px solid rgba(255,255,255,80);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 80);
            }
        """)
        return btn

    def menu_actualizar(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setFont(QFont("Arial", 12, QFont.Bold))
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 35);
                color: white;
                border-radius: 8px;
                padding: 4px 14px;
                border: 1px solid rgba(255,255,255,40);
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 55);
                border: 1px solid rgba(255,255,255,70);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 75);
            }
        """)
        return btn

    # ================== MENÚ TAB ==================
    def menu_tab(self, text, active=False):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setFont(QFont("Arial", 12))

        if active:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: rgb(120, 220, 255);
                    border: none;
                    font-weight: bold;
                    border-bottom: 2px solid rgb(120, 220, 255);
                }
                QPushButton:hover {
                    color: rgb(170, 235, 255);
                    border-bottom: 2px solid rgb(170, 235, 255);
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: rgba(210,210,210,170);
                    border: none;
                }
                QPushButton:hover {
                    color: rgb(160, 220, 255);
                    border-bottom: 2px solid rgba(160, 220, 255, 140);
                }
            """)
        return btn

    # ================== CARGAR DATOS DESDE API ==================
    def cargar_datos_bd(self):

        token = get_session().get("token")

        if not token:
            QMessageBox.warning(self, "Sesión", "Debe iniciar sesión.")
            return

        try:
            response = requests.get(
                "http://127.0.0.1:8000/recomendaciones-usuario/admin/infimas-disponibles",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            if response.status_code != 200:
                QMessageBox.critical(self, "Error", "No se pudieron cargar datos.")
                return

            data = response.json()

            if isinstance(data, dict) and "data" in data:
                data = data["data"]

        except requests.RequestException:
            QMessageBox.warning(self, "Error", "Servidor no disponible.")
            return

        # Cargar usuarios
        lista_usuarios = cargar_empleados(self)

        # Limpiar tabla
        self.table.setRowCount(0)

        # Limpiar asignaciones anteriores
        self.asignaciones_pendientes.clear()

        for row, item in enumerate(data):

            self.table.insertRow(row)

            id_infima = item.get("id_infima")

            nivel = item.get("nivel_de_oportunidad") or 1

            if nivel == 1:
                color = QColor(150, 215, 175)
            elif nivel == 2:
                color = QColor(220, 200, 140)
            else:
                color = QColor(220, 170, 170)

            # ====== COLUMNA 0 → COMBO ======

            combo = QComboBox()
            combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: rgb({color.red()},{color.green()},{color.blue()});
                    color: black;
                    border: none;
                    padding: 3px;
                }}

                QComboBox QAbstractItemView {{
                    background-color: rgb(220,235,255);
                    color: black;
                    selection-background-color: rgb(80,140,230);
                    selection-color: white;
                }}

                QComboBox::item {{
                    background-color: rgb(220,235,255);
                    color: black;
                }}

                QComboBox::item:selected {{
                    background-color: rgb(80,140,230);
                    color: white;
                }}
            """)

            combo.addItem("Seleccionar usuario")
            combo.addItems(lista_usuarios)

            combo.currentIndexChanged.connect(
                partial(self.on_usuario_changed, row, combo, item)
            )

            self.table.setCellWidget(row, 0, combo)

            # ====== DATOS ======

            datos = [
                item.get("codigo_necesidad", ""),
                item.get("descripcion_objeto_compra", ""),
                item.get("etapa", ""),
            ]

            for col, val in enumerate(datos, start=1):

                cell = QTableWidgetItem(str(val))
                cell.setFlags(Qt.ItemIsEnabled)
                cell.setBackground(color)
                cell.setForeground(QColor(0, 0, 0))

                if col == 3:
                    cell.setTextAlignment(Qt.AlignCenter)

                self.table.setItem(row, col, cell)
        print("Infimas disponibles Actualizadas")

    # 🔵 MÉTODO NUEVO PARA ABRIR VENTANA
    def abrir_ventana_usuarios(self):
            print("Abriendo Workspace User RE...")
            try:
                from views.user_management import UserManagementUI
                self.user = UserManagementUI()
                self.user.show()
                #self.hide()
                QTimer.singleShot(2000, self.hide)  # Esperar 2 segundos antes de ocultar
            except ImportError as e:
                print(f"Error de importación: {e}")
                QMessageBox.critical(self, "Error", f"No se pudo abrir la ventana: {e}")
            except Exception as e:
                print(f"Error al crear ventana: {e}")

    # ================== GESTIÓN DE ASIGNACIONES PENDIENTES ==================
    def on_usuario_changed(self, row, combo: QComboBox, item_data: dict):

        texto = combo.currentText()

        # Si vuelve a "Seleccionar", borrar buffer
        if texto == "Seleccionar usuario":

            if row in self.asignaciones_pendientes:
                del self.asignaciones_pendientes[row]

            return

        usuario_id = self.usuarios_dict.get(texto)
        id_infima = item_data.get("id_infima")

        if not usuario_id or not id_infima:
            return

        # Guardar en memoria
        self.asignaciones_pendientes[row] = {
            "usuario_id": usuario_id,
            "id_infima": id_infima
        }

        print("Pendientes:", self.asignaciones_pendientes)

    # ==================== CONFIRMAR ASIGNACIONES PENDIENTES ==================
    def confirmar_asignaciones(self):

        if not self.asignaciones_pendientes:
            QMessageBox.information(
                self,
                "Información",
                "No hay asignaciones seleccionadas."
            )
            return

        token = get_session().get("token")

        confirm = QMessageBox.question(
            self,
            "Confirmar",
            f"¿Asignar {len(self.asignaciones_pendientes)} ínfimas?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        errores = 0

        for fila, datos in self.asignaciones_pendientes.items():

            payload = {
                "usuario_id": datos["usuario_id"],
                "id_infima": datos["id_infima"]
            }

            try:
                resp = requests.post(
                    "http://127.0.0.1:8000/recomendaciones-usuario/admin/asignar-infima-individual",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10,
                )

                if resp.status_code == 200:

                    # Pintar verde
                    for c in range(self.table.columnCount()):
                        item = self.table.item(fila, c)
                        if item:
                            item.setBackground(QColor(180, 240, 180))

                    combo = self.table.cellWidget(fila, 0)
                    if combo:
                        combo.setEnabled(False)

                else:
                    errores += 1

            except requests.RequestException:
                errores += 1

        # Limpiar memoria
        self.asignaciones_pendientes.clear()
        self.cargar_datos_bd()

        if errores == 0:
            QMessageBox.information(
                self, "OK", "Asignaciones completadas."
            )
        else:
            QMessageBox.warning(
                self,
                "Parcial",
                f"{errores} asignaciones fallaron."
            )

# ================== cargar empleados ==================
def cargar_empleados(self):

        token = get_session().get("token")

        resp = requests.get(
            "http://127.0.0.1:8000/usuarios/empleados-activos",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

        if resp.status_code != 200:
            return []

        usuarios = resp.json()

        # { nombre: id }
        self.usuarios_dict = {
            u["usuario"]: u["id_usuario"] for u in usuarios
        }

        return list(self.usuarios_dict.keys())