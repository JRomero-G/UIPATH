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
            ["", "NIC", "Descripción", "Grado de recomendación", "Acción"]
        )

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

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
        data = [
            (
                "NIC:05601970001-2026-00001",
                "adquisición  de equipo tecnológico especializado adquisición  de equipo tecnológico especializado adquisición  de equipo tecnológico especializado adquisición  de equipo tecnológico especializado adquisición  de equipo tecnológico especializado adquisición  de equipo tecnológico especializado para el fortalecimiento de los procesos internos",
                "Recomendado",
                1,
            ),
            (
                "NIC:05601970001-2026-00002",
                "materiales de construcción",
                "Recomendado",
                1,
            ),
            (
                "NIC:1160020493001-2026-00001",
                "material educativo extenso",
                "Recomendado",
                2,
            ),
            ("NIC:04600600001-2026-00001", "material de oficina", "Recomendado", 3),
            (
                "NIC:706007246001-2026-00001",
                "transporte institucional",
                "Poco recomendado",
                6,
            ),
        ]

        self.table.setRowCount(len(data))

        for row, item in enumerate(data):
            self.table.setItem(row, 1, QTableWidgetItem(item[0]))
            self.table.setItem(row, 2, QTableWidgetItem(item[1]))

            grade_item = QTableWidgetItem(item[2])
            grade_item.setTextAlignment(Qt.AlignCenter)

            if item[2] == "Recomendado":
                grade_item.setBackground(QColor(90, 160, 110))
            elif item[2] == "Poco recomendado":
                grade_item.setBackground(QColor(190, 170, 90))
            else:
                grade_item.setBackground(QColor(180, 90, 90))

                if col == 3:
                    cell.setText(
                        "✅  Recomendado"
                        if value == "Recomendado"
                        else "⚠️  Poco recomendado"
                    )
                    cell.setTextAlignment(Qt.AlignCenter)
                    cell.setFont(QFont("Arial", 9, QFont.Bold))
                elif col == 4:
                    cell.setTextAlignment(Qt.AlignCenter)
                elif col == 2:
                    cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                self.table.setItem(row, col, cell)

            self.table.setCellWidget(row, 5, self.delete_button(row_color.name()))

    # llamar al RE
    def open_workspace_userRE(self):
        from views.workspace_userRE import WorkspaceUserREUI

        self.workspace_re = WorkspaceUserREUI()
        self.workspace_re.show()
        self.hide()
