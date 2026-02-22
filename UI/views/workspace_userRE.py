import os

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
    QWidget,
)

from config import *
from components.base_window import BaseWindow


class WorkspaceUserREUI(BaseWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Gestorex 1.1 - Usuario")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(18)

        # ================== MENÚ SUPERIOR ==================
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(12)

        self.btn_actualizar = self.menu_actualizar("⟳  Actualizar")
        self.btn_recomendados = self.menu_tab("Recomendados", active=False)
        self.btn_revision = self.menu_tab("Revisión y Envío", active=True)

        menu_layout.addWidget(self.btn_actualizar)
        menu_layout.addWidget(self.btn_recomendados)
        menu_layout.addWidget(self.btn_revision)
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
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["", "NIC", "Resumen", "Documento de contratación", "Acción"]
        )

        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.ElideNone)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 32)

        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 110)

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
        """)

        self.load_demo_data()
        main_layout.addWidget(self.table)

        # ================== BOTÓN INFERIOR ==================
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_analizar = self.action_button("📤  Enviar")
        self.btn_analizar.clicked.connect(self.open_loading)

        bottom_layout.addWidget(self.btn_analizar)
        main_layout.addLayout(bottom_layout)

    # ================== BOTONES ==================
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

    def action_button(self, text):
        btn = QPushButton(text)
        btn.setFixedSize(140, 44)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(QFont("Arial", 13, QFont.Bold))
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(60, 130, 200);
                color: white;
                border-radius: 22px;
                border: none;
            }
            QPushButton:hover {
                background-color: rgb(80, 150, 220);
            }
            QPushButton:pressed {
                background-color: rgb(45, 110, 175);
            }
        """)
        return btn

    # ================== DOCUMENTOS ==================
    def document_links(self, bg_color):
        container = QWidget()
        container.setStyleSheet(f"background-color: {bg_color};")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        def link(text):
            lbl = QLabel(text)
            lbl.setCursor(Qt.PointingHandCursor)
            lbl.setStyleSheet("""
                QLabel {
                    color: rgb(90, 160, 220);
                    font-weight: bold;
                }
                QLabel:hover {
                    color: rgb(120, 190, 255);
                    text-decoration: underline;
                }
            """)
            return lbl

        layout.addWidget(link("📄 Informe de necesidad"))
        layout.addWidget(link("📎 Proforma"))
        return container

    # ================== ELIMINAR ==================
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
        data = [
            ("NIC:05601970001-2026-00001", "Equipo tecnológico especializado"),
            ("NIC:05601970001-2026-00002", "Materiales de construcción"),
            ("NIC:1160020493001-2026-00001", "Material educativo"),
        ]

        self.table.setRowCount(len(data))

        for row, item in enumerate(data):
            row_color = QColor(150, 215, 175)

            check_item = QTableWidgetItem()
            check_item.setCheckState(Qt.Unchecked)
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setBackground(row_color)
            self.table.setItem(row, 0, check_item)

            for col, value in enumerate(item, start=1):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(Qt.ItemIsEnabled)
                cell.setBackground(row_color)
                cell.setForeground(QColor(0, 0, 0))
                self.table.setItem(row, col, cell)

            self.table.setCellWidget(row, 3, self.document_links(row_color.name()))
            self.table.setCellWidget(row, 4, self.delete_button(row_color.name()))

    # ================== LLAMAR AL LOADING ==================
    def open_loading(self):
        from views.loading import LoadingUI

        self.loading = LoadingUI(duration_ms=3000)
        self.loading.show()
        self.hide()
