import os
from functools import partial
from PyQt5.QtCore import Qt
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
from ..config import WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR, get_session
from ..components.base_window import BaseWindow


class WorkspaceManagerUI(BaseWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Gestorex 1.1 - Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(18)

        # ================== MENÚ SUPERIOR ==================
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(12)
        self.btn_actualizar = self.menu_actualizar("⟳  Actualizar")
        self.btn_reportes = self.menu_tab("Reportes", active=True)
        menu_layout.addWidget(self.btn_actualizar)
        menu_layout.addWidget(self.btn_reportes)
        menu_layout.addStretch()

        # ---- LOGO + TEXTO ----
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)
        brand_layout.setAlignment(Qt.AlignVCenter)
        logo_label = QLabel()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "..", "assets", "logo2.png")
        pixmap = QPixmap(logo_path).scaled(
            44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        logo_label.setPixmap(pixmap)
        title = QLabel("Gestorex 1.1")
        title.setFont(QFont("Arial", 15, QFont.Bold))
        title.setStyleSheet("color: white;")
        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(title)
        menu_layout.addLayout(brand_layout)
        main_layout.addLayout(menu_layout)

        # ================== TABLA ==================
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Usuario", "NIC", "Descripción", "Etapa"])
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.ElideNone)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 120)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.verticalHeader().setMinimumSectionSize(38)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { background-color: rgba(255,255,255,15); color: white; 
                gridline-color: rgba(255,255,255,25); border-radius: 10px; 
                alternate-background-color: rgb(255, 255, 255); border: 1px solid rgba(255,255,255,90); }
            QHeaderView::section { background-color: rgba(0,0,0,110); color: white; 
                padding: 8px; border: none; font-weight: bold; border-bottom: 2px solid rgba(255,255,255,120); }
        """)
        main_layout.addWidget(self.table)

        # ================== CARGAR DATOS ==================
        self.load_demo_data()

    # ================== BOTONES ==================
    def menu_actualizar(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setFont(QFont("Arial", 12, QFont.Bold))
        btn.setStyleSheet("""
            QPushButton { background-color: rgba(255, 255, 255, 35); color: white; border-radius: 8px; padding: 4px 14px; border: 1px solid rgba(255,255,255,40); }
            QPushButton:hover { background-color: rgba(255, 255, 255, 55); border: 1px solid rgba(255,255,255,70); }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 75); }
        """)
        return btn

    def menu_tab(self, text, active=False):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setFont(QFont("Arial", 12))
        if active:
            btn.setStyleSheet("""
                QPushButton { background: transparent; color: rgb(120, 220, 255); border: none; font-weight: bold; border-bottom: 2px solid rgb(120, 220, 255); }
                QPushButton:hover { color: rgb(170, 235, 255); border-bottom: 2px solid rgb(170, 235, 255); }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton { background: transparent; color: rgba(210,210,210,170); border: none; }
                QPushButton:hover { color: rgb(160, 220, 255); border-bottom: 2px solid rgba(160, 220, 255, 140); }
            """)
        return btn

    # ================== CARGAR DATOS ==================
    def load_demo_data(self):
        try:
            # Obtener ínfimas
            response = requests.get(
                "http://127.0.0.1:8000/infimas/ingresadas",
                headers={"Authorization": f"Bearer {get_session().get('token')}"},
                timeout=10,
            )
            if response.status_code != 200:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Error al obtener ínfimas.\nCódigo: {response.status_code}",
                )
                return
            data = response.json()
            if isinstance(data, dict) and "data" in data:
                data = data["data"]

            # Obtener usuarios
            usuarios_resp = requests.get(
                "http://127.0.0.1:8000/usuarios/no-admin",
                headers={"Authorization": f"Bearer {get_session().get('token')}"},
                timeout=10,
            )
            usuarios = usuarios_resp.json() if usuarios_resp.status_code == 200 else []
            self.usuarios_dict = {u["usuario"]: u["id"] for u in usuarios}
            lista_usuarios = list(self.usuarios_dict.keys())

        except requests.RequestException as e:
            QMessageBox.warning(self, "Error", "No se pudo conectar al servidor.")
            print("EXCEPTION:", e)
            return

        # Limpiar tabla
        self.table.setRowCount(0)
        for row, item in enumerate(data):
            self.table.insertRow(row)
            nivel = item.get("nivel_de_oportunidad") or 1
            if nivel == 1:
                row_color = QColor(150, 215, 175)
            elif nivel == 2:
                row_color = QColor(220, 200, 140)
            else:
                row_color = QColor(220, 170, 170)
            text_color = QColor(0, 0, 0)

            # === Col 0: Usuario con ComboBox ===
            combo = QComboBox()
            combo.addItem("Seleccionar usuario")  # placeholder
            combo.addItems(lista_usuarios)
            combo.setStyleSheet("background-color: white; color: black;")
            combo.currentIndexChanged.connect(
                partial(self.asignar_usuario_infima, row, combo, item)
            )
            self.table.setCellWidget(row, 0, combo)

            # Col 1: NIC
            nic = item.get("codigo_necesidad", "")
            cell = QTableWidgetItem(nic)
            cell.setFlags(Qt.ItemIsEnabled)
            cell.setForeground(text_color)
            cell.setBackground(row_color)
            self.table.setItem(row, 1, cell)

            # Col 2: Descripción
            descripcion = item.get("descripcion_objeto_compra", "")
            cell = QTableWidgetItem(descripcion)
            cell.setFlags(Qt.ItemIsEnabled)
            cell.setForeground(text_color)
            cell.setBackground(row_color)
            self.table.setItem(row, 2, cell)

            # Col 3: Etapa
            Etapa = item.get("etapa", "")
            cell = QTableWidgetItem(Etapa)
            cell.setFlags(Qt.ItemIsEnabled)
            cell.setForeground(text_color)
            cell.setBackground(row_color)
            cell.setTextAlignment(Qt.AlignCenter)
            cell.setFont(QFont("Arial", 9, QFont.Bold))
            self.table.setItem(row, 3, cell)

    # ================== ASIGNAR ÍNFIMA ==================
    def asignar_usuario_infima(self, row, combo: QComboBox, item_data: dict):
        # 🚫 Evitar ejecución automática
        if combo.currentText() == "Seleccionar usuario":
            return

        usuario_seleccionado = combo.currentText()
        id_infima = item_data.get("id_infima")

        if not usuario_seleccionado or not id_infima:
            return

        usuario_id = self.usuarios_dict.get(usuario_seleccionado)
        if not usuario_id:
            return

        token = get_session().get("token")
        if not token:
            QMessageBox.warning(
                self, "Sesión", "Token no encontrado. Inicie sesión nuevamente."
            )
            return

        try:
            response = requests.post(
                "http://127.0.0.1:8000/recomendaciones-usuario/asignar",
                json=[  # ✅ siempre lista
                    {
                        "usuario_id": usuario_id,
                        "id_infima": id_infima,
                    }
                ],
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )

            if response.status_code == 200:
                # ✅ Feedback visual
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor(180, 240, 180))

                combo.setEnabled(False)  # bloquear reasignación

            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"No se pudo asignar la ínfima.\n"
                    f"Código: {response.status_code}\n{response.text}",
                )

        except requests.RequestException as e:
            QMessageBox.warning(self, "Error", "No se pudo conectar al servidor.")
            print("EXCEPTION:", e)
