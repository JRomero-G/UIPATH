import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPixmap
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QVBoxLayout,
    QHeaderView, QWidget
)

from config import *
from components.base_window import BaseWindow


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
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Usuario", "NIC", "Descripción",
            "Grado de recomendación", "Nivel", "Acción"
        ])

        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.ElideNone)

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 90)

        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 170)

        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 60)

        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 110)

        # 👉 CAMBIO CLAVE (igual que User)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
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

            QScrollBar:vertical {
                background: rgba(255,255,255,40);
                width: 14px;
                margin: 2px;
                border-radius: 7px;
            }

            QScrollBar::handle:vertical {
                background: rgba(255,255,255,180);
                min-height: 40px;
                border-radius: 7px;
            }

            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,230);
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        self.load_demo_data()
        self.table.sortItems(4, Qt.AscendingOrder)

        main_layout.addWidget(self.table)

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

    # ================== BOTÓN ELIMINAR ==================
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

    # ================== DATOS de tabla ==================
    def load_demo_data(self):
        data = []

        self.table.setRowCount(len(data))

        for row, item in enumerate(data):
            row_color = QColor(150, 215, 175) if item[3] == "Recomendado" else QColor(220, 200, 140)
            text_color = QColor(0, 0, 0)

            for col, value in enumerate(item):
                if col == 3:
                    value = "✅  Recomendado" if value == "Recomendado" else "⚠️  Poco recomendado"
                    cell = QTableWidgetItem(value)
                    cell.setTextAlignment(Qt.AlignCenter)
                    cell.setFont(QFont("Arial", 9, QFont.Bold))
                elif col == 4:
                    cell = QTableWidgetItem(str(value))
                    cell.setTextAlignment(Qt.AlignCenter)
                else:
                    cell = QTableWidgetItem(str(value))
                    if col == 2:
                        cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                cell.setFlags(Qt.ItemIsEnabled)
                cell.setForeground(text_color)
                cell.setBackground(row_color)
                self.table.setItem(row, col, cell)

            self.table.setCellWidget(row, 5, self.delete_button(row_color.name()))
