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
from config import WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR, get_session
from components.base_window import BaseWindow
from components.btns_windows import WindowButtons  # ← IMPORTADO



class WorkspaceManagerUI(BaseWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Gestorex 1.1 - Manager")

        # Tamaño base (se maximiza después correctamente)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        # ================= BOTONES VENTANA =================
        # ← AÑADIDO: Botones minimizar/maximizar/cerrar en parte superior
        self.window_buttons = WindowButtons(self)
        self.window_buttons.setGeometry(0, 0, WINDOW_WIDTH, 35)

        # ================= LAYOUT PRINCIPAL =================
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 50, 30, 20)
        main_layout.setSpacing(18)

        # ================== MENÚ SUPERIOR ==================
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(12)

        self.btn_actualizar = self.menu_actualizar("⟳  Actualizar")
        self.btn_actualizar.clicked.connect(self.cargar_datos_bd)

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
            44, 44,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
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

        # 🔥 Cargar datos reales al iniciar
        self.cargar_datos_bd()

    # 🔥 Abrir ventana maximizada correctamente
    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()
        # ← AÑADIDO: Actualizar ancho de botones al maximizar
        self.window_buttons.setGeometry(0, 0, self.width(), 35)

    # ← AÑADIDO: Actualizar botones al redimensionar
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.window_buttons.setGeometry(0, 0, self.width(), 35)

    # ================== BOTÓN ACTUALIZAR ==================
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
            QMessageBox.warning(
                self, "Sesión", "Token no encontrado. Inicie sesión nuevamente."
            )
            return

        try:
            response = requests.get(
                "http://127.0.0.1:8000/infimas/ingresadas ",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            if response.status_code != 200:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Error al obtener datos.\nCódigo: {response.status_code}",
                )
                return

            data = response.json()

            if isinstance(data, dict) and "data" in data:
                data = data["data"]

            if not data:
                QMessageBox.information(
                    self, "Información", "No hay registros disponibles."
                )
                return

        except requests.RequestException as e:
            QMessageBox.warning(
                self, "Error", "No se pudo conectar al servidor."
            )
            print("EXCEPTION:", e)
            return

        # 🔥 LIMPIAR TABLA
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

            valores = [
                item.get("usuario", ""),
                item.get("codigo_necesidad", ""),
                item.get("descripcion_objeto_compra", ""),
                item.get("etapa", ""),
            ]

            for col, value in enumerate(valores):
                cell = QTableWidgetItem(str(value))

                if col == 3:
                    cell.setTextAlignment(Qt.AlignCenter)
                    cell.setFont(QFont("Arial", 9, QFont.Bold))

                cell.setFlags(Qt.ItemIsEnabled)
                cell.setForeground(text_color)
                cell.setBackground(row_color)

                self.table.setItem(row, col, cell)