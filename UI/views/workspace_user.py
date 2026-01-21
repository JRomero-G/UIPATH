from tkinter import messagebox
from PyQt5.QtWidgets import QMessageBox

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHBoxLayout,
    QVBoxLayout,
    QHeaderView,
)
import requests

from config import *
from components.base_window import BaseWindow


class WorkspaceUserUI(BaseWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Gestorex 1.1 - Usuario")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        # ================== LAYOUT PRINCIPAL ==================
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(15)

        # ================== MENÚ SUPERIOR ==================
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(10)

        self.btn_actualizar = self.menu_button("Actualizar")
        self.btn_recomendados = self.menu_button("Recomendados", active=True)
        self.btn_revision = self.menu_button("Revisión y Envío")

        menu_layout.addWidget(self.btn_actualizar)
        menu_layout.addWidget(self.btn_recomendados)
        menu_layout.addWidget(self.btn_revision)
        menu_layout.addStretch()

        title = QLabel("Gestorex 1.1")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: white;")
        menu_layout.addWidget(title)

        main_layout.addLayout(menu_layout)

        # ================== TABLA ==================
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["", "NIC", "Descripción", "Grado de recomendación", "Nivel","Accion"]
        )

        # ===== AJUSTE DE COLUMNAS =====
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.ElideNone)

        header = self.table.horizontalHeader()

        # Col 0: checkbox (muy pequeña)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 32)

        # Col 1: NIC (auto por contenido)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        # Col 2: Descripción (ocupa lo restante)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        # Col 3: Grado (auto)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        # Col 4: Nivel (fija)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 60)

        # Col 5: Acción (fija)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 110)

        # Altura de filas
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.verticalHeader().setMinimumSectionSize(38)
        self.table.verticalHeader().setVisible(False)
        """
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        """
        

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(255,255,255,15);
                color: white;
                gridline-color: rgba(255,255,255,25);
                border-radius: 10px;
            }
            QHeaderView::section {
                background-color: rgba(0,0,0,80);
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)

       
        self.load_demo_data()
        self.table.sortItems(4, Qt.AscendingOrder)
        main_layout.addWidget(self.table)

        # ================== BOTONES ==================
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_analizar = self.action_button("📊  Analizar")
        self.btn_analizar.clicked.connect(self.open_workspace_userRE)

        bottom_layout.addWidget(self.btn_analizar)

        main_layout.addLayout(bottom_layout)

    # ================== BOTONES ==================
    def menu_button(self, text, active=False):
        btn = QPushButton(text)
        btn.setFixedHeight(42)

        if active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0,180,255,200);
                    color: white;
                    border-radius: 8px;
                    font-weight: bold;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,35);
                    color: white;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: rgba(0,180,255,120);
                }
            """)
        return btn

    def action_button(self, text):
        btn = QPushButton(text)
        btn.setFixedSize(130, 42)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0,180,255,200);
                color: white;
                border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0,220,255,230);
            }
        """)
        return btn

    def delete_button(self, bg_color):
        container = QWidget()
        container.setStyleSheet(f"background-color: {bg_color};")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("🗑")
        icon.setStyleSheet("color: rgb(140, 30, 30); font-size: 15px;")

        text = QLabel("Eliminar")
        text.setStyleSheet("color: rgb(180, 40, 40); font-weight: bold;")

        def enter_event(event):
            icon.setStyleSheet("color: rgb(220, 20, 20); font-size: 17px;")
            text.setStyleSheet("""
                color: rgb(220, 60, 60);
                font-weight: bold;
                text-decoration: underline;
            """)

        def leave_event(event):
            icon.setStyleSheet("color: rgb(140, 30, 30); font-size: 15px;")
            text.setStyleSheet("color: rgb(180, 40, 40); font-weight: bold;")

        container.enterEvent = enter_event
        container.leaveEvent = leave_event

        layout.addWidget(icon)
        layout.addWidget(text)
        return container

    # ================== DATOS ==================
    def load_demo_data(self):
        
        try:
            response = requests.get(
                #No hay infimas con etapa de seleccionadas, liste todas para pruebas
                "http://127.0.0.1:8000/infimas/Todas",
                headers={
                    "Authorization": f"Bearer {get_session().get('token')}"
                },
                timeout=10
            )

            print("STATUS:", response.status_code)

            if response.status_code != 200:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Error al obtener ínfimas.\nCódigo: {response.status_code}"
                )
                return

            data = response.json()
            print("INFIMAS RECIBIDA:", len(data))

            # 🔒 Si la API devuelve {"data": [...]}
            if isinstance(data, dict) and "data" in data:
                data = data["data"]

            if not isinstance(data, list):
                QMessageBox.critical(
                    self,
                    "Error",
                    "La API no devolvió una lista de registros."
                )
                print("DATA INVALIDA:", data)
                return

        except requests.RequestException as e:
            messagebox.warning(self, "Error", "No se pudo conectar al servidor.")
            print("EXCEPTION:", e)
            return
        
      
        # limpiar tabla
        self.table.setRowCount(0)

        if not data:
            print("⚠️ No hay registros para mostrar")
            return

        for row, item in enumerate(data):
            self.table.insertRow(row)

            nivel = item.get("nivel_de_oportunidad") or 1 #no tiene nivel asignado

            if nivel == 1:
                row_color = QColor(150, 215, 175)
                grado = "Recomendado"
            elif nivel == 2:
                row_color = QColor(220, 200, 140)
                grado = "Poco recomendado"
            else:
                row_color = QColor(220, 170, 170)
                grado = "No recomendado"

            text_color = QColor(0, 0, 0)

            # Col 0: Check
            check_item = QTableWidgetItem()
            
            check_item.setCheckState(Qt.Unchecked)
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setBackground(row_color)
            self.table.setItem(row, 0, check_item)

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
            cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 2, cell)

            # Col 3: Grado
            cell = QTableWidgetItem(
                "✅ Recomendado" if grado == "Recomendado"
                else "⚠️ Poco recomendado" if grado == "Poco recomendado"
                else "❌ No recomendado"
            )
            cell.setFlags(Qt.ItemIsEnabled)
            cell.setForeground(text_color)
            cell.setBackground(row_color)
            cell.setTextAlignment(Qt.AlignCenter)
            cell.setFont(QFont("Arial", 9, QFont.Bold))
            self.table.setItem(row, 3, cell)

            # Col 4: Nivel
            cell = QTableWidgetItem(str(nivel))
            cell.setFlags(Qt.ItemIsEnabled)
            cell.setForeground(text_color)
            cell.setBackground(row_color)
            cell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, cell)

            # Col 5: Acción
            self.table.setCellWidget(row, 5, self.delete_button(row_color.name()))


    # llamar al RE
    def open_workspace_userRE(self):
        from views.workspace_userRE import WorkspaceUserREUI

        self.workspace_re = WorkspaceUserREUI()
        self.workspace_re.show()
        self.hide()
