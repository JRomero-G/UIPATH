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
    QWidget,
    QStackedWidget,
)

import requests
from UI.config import WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR, get_session
from UI.components.table_scroll_style import apply_table_scrollbar_style
from UI.components.base_window import BaseWindow
from UI.components.btns_windows import WindowButtons
from Config import Global
from src.Config.version import CURRENT_VERSION
from src.utils.updater import verificar_actualizacion_async
from UI.components.classic_msgbox import ClassicMsgBox


class WorkspaceManagerUI(BaseWindow):
    def __init__(self):
        super().__init__()

        # =========================================================
        # DATOS GENERALES
        # =========================================================
        self.asignaciones_pendientes = {}
        self.usuarios_dict = {}

        self.setWindowTitle(f"Gestorex {CURRENT_VERSION} - Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        self.window_buttons = WindowButtons(self)
        self.window_buttons.setGeometry(0, 0, WINDOW_WIDTH, 35)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 50, 30, 20)
        main_layout.setSpacing(18)

        # =========================================================
        # HEADER SUPERIOR
        # =========================================================
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(12)

        # ---------------------------------------------------------
        # IZQUIERDA: BOTONES GENERALES Y PESTAÑAS
        # ---------------------------------------------------------
        self.btn_usuarios = self.menu_usuarios_icon()
        self.btn_usuarios.clicked.connect(self.abrir_ventana_usuarios)

        self.btn_actualizar = self.menu_actualizar("⟳  Actualizar")
        self.btn_actualizar.clicked.connect(self.actualizar_vista_actual)

        # Pestaña 1: Asignaciones
        self.btn_asignaciones_tab = self.menu_tab("Asignaciones", active=True)
        self.btn_asignaciones_tab.clicked.connect(self.mostrar_tab_asignaciones)

        # Pestaña 2: Reportes
        self.btn_reportes_tab = self.menu_tab("Reportes", active=False)
        self.btn_reportes_tab.clicked.connect(self.mostrar_tab_reportes)

        # Pestaña 3: Ínfimas rechazadas
        self.btn_rechazadas_tab = self.menu_tab("Ínfimas rechazadas", active=False)
        self.btn_rechazadas_tab.clicked.connect(self.mostrar_tab_rechazadas)

        menu_layout.addWidget(self.btn_usuarios)
        menu_layout.addWidget(self.btn_actualizar)
        menu_layout.addWidget(self.btn_asignaciones_tab)
        menu_layout.addWidget(self.btn_reportes_tab)
        menu_layout.addWidget(self.btn_rechazadas_tab)
        menu_layout.addStretch()

        # ---------------------------------------------------------
        # DERECHA: ACCIÓN DINÁMICA + LOGO
        # ---------------------------------------------------------
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)
        brand_layout.setAlignment(Qt.AlignVCenter)

        # Acción visible en ASIGNACIONES
        self.btn_asignar = self.menu_actualizar("Asignar")
        self.btn_asignar.clicked.connect(self.confirmar_asignaciones)

        # Acción visible en REPORTES
        self.combo_usuarios_reportes = QComboBox()
        self.combo_usuarios_reportes.setFixedHeight(32)
        self.combo_usuarios_reportes.setFont(QFont("Arial", 11, QFont.Bold))
        self.combo_usuarios_reportes.setMinimumWidth(180)
        self.combo_usuarios_reportes.addItem("Usuarios")
        self.combo_usuarios_reportes.currentIndexChanged.connect(
            self.on_usuario_reporte_changed
        )
        self.combo_usuarios_reportes.setStyleSheet(
            """
            QComboBox {
                background-color: rgba(255, 255, 255, 35);
                color: white;
                border-radius: 8px;
                padding: 4px 14px;
                border: 1px solid rgba(255,255,255,40);
            }
            QComboBox:hover {
                background-color: rgba(255, 255, 255, 55);
                border: 1px solid rgba(255,255,255,70);
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(25, 35, 55);
                color: white;
                border: 1px solid rgba(255,255,255,80);
                selection-background-color: rgba(120, 220, 255, 140);
            }
        """
        )
        self.combo_usuarios_reportes.hide()

        # En RECHAZADAS no habrá botón/acción, por eso aquí no agregamos nada extra.

        logo_label = QLabel()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "..", "assets", "logo2.png")

        pixmap = QPixmap(logo_path).scaled(
            44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        logo_label.setPixmap(pixmap)

        title = QLabel(f"Gestorex {CURRENT_VERSION}")
        title.setFont(QFont("Arial", 15, QFont.Bold))
        title.setStyleSheet("color: white;")

        brand_layout.addWidget(self.btn_asignar)
        brand_layout.addWidget(self.combo_usuarios_reportes)
        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(title)

        menu_layout.addLayout(brand_layout)
        main_layout.addLayout(menu_layout)

        # =========================================================
        # CONTENIDO CENTRAL CON PESTAÑAS
        # =========================================================
        self.stack_pages = QStackedWidget()
        main_layout.addWidget(self.stack_pages)

        # =========================================================
        # PÁGINA 1: ASIGNACIONES
        # =========================================================
        self.page_asignaciones = QWidget()
        page_asignaciones_layout = QVBoxLayout(self.page_asignaciones)
        page_asignaciones_layout.setContentsMargins(0, 0, 0, 0)

        self.table_asignaciones = QTableWidget(0, 4)
        self.table_asignaciones.setHorizontalHeaderLabels(
            ["Usuario", "NIC", "Descripción", "Etapa"]
        )
        self.table_asignaciones.setWordWrap(True)
        self.table_asignaciones.setTextElideMode(Qt.ElideNone)

        header_asignaciones = self.table_asignaciones.horizontalHeader()
        header_asignaciones.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_asignaciones.setColumnWidth(0, 120)
        header_asignaciones.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_asignaciones.setSectionResizeMode(2, QHeaderView.Stretch)
        header_asignaciones.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table_asignaciones.setColumnWidth(3, 120)

        self.table_asignaciones.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.table_asignaciones.verticalHeader().setMinimumSectionSize(38)
        self.table_asignaciones.verticalHeader().setVisible(False)
        self.table_asignaciones.setAlternatingRowColors(True)

        self.table_asignaciones.setStyleSheet(
            """
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
        """
        )

        page_asignaciones_layout.addWidget(self.table_asignaciones)
        apply_table_scrollbar_style(self.table_asignaciones)

        # =========================================================
        # PÁGINA 2: REPORTES
        # =========================================================
        self.page_reportes = QWidget()
        page_reportes_layout = QVBoxLayout(self.page_reportes)
        page_reportes_layout.setContentsMargins(0, 0, 0, 0)

        self.table_reportes = QTableWidget(0, 4)
        self.table_reportes.setHorizontalHeaderLabels(
            ["Usuario", "NIC", "Descripción", "Etapa"]
        )
        self.table_reportes.setWordWrap(True)
        self.table_reportes.setTextElideMode(Qt.ElideNone)

        header_reportes = self.table_reportes.horizontalHeader()
        header_reportes.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_reportes.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_reportes.setSectionResizeMode(2, QHeaderView.Stretch)
        header_reportes.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table_reportes.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.table_reportes.verticalHeader().setMinimumSectionSize(38)
        self.table_reportes.verticalHeader().setVisible(False)
        self.table_reportes.setAlternatingRowColors(True)

        self.table_reportes.setStyleSheet(
            """
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
        """
        )

        page_reportes_layout.addWidget(self.table_reportes)
        apply_table_scrollbar_style(self.table_reportes)

        # =========================================================
        # PÁGINA 3: ÍNFIMAS RECHAZADAS
        # =========================================================
        self.page_rechazadas = QWidget()
        page_rechazadas_layout = QVBoxLayout(self.page_rechazadas)
        page_rechazadas_layout.setContentsMargins(0, 0, 0, 0)

        self.table_rechazadas = QTableWidget(0, 3)
        self.table_rechazadas.setHorizontalHeaderLabels(["NIC", "Descripción", "Etapa"])
        self.table_rechazadas.setWordWrap(True)
        self.table_rechazadas.setTextElideMode(Qt.ElideNone)

        header_rechazadas = self.table_rechazadas.horizontalHeader()
        header_rechazadas.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_rechazadas.setSectionResizeMode(1, QHeaderView.Stretch)
        header_rechazadas.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.table_rechazadas.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.table_rechazadas.verticalHeader().setMinimumSectionSize(38)
        self.table_rechazadas.verticalHeader().setVisible(False)
        self.table_rechazadas.setAlternatingRowColors(True)

        self.table_rechazadas.setStyleSheet(
            """
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
        """
        )

        page_rechazadas_layout.addWidget(self.table_rechazadas)
        apply_table_scrollbar_style(self.table_rechazadas)

        # =========================================================
        # AGREGAR PÁGINAS AL STACK
        # =========================================================
        self.stack_pages.addWidget(self.page_asignaciones)
        self.stack_pages.addWidget(self.page_reportes)
        self.stack_pages.addWidget(self.page_rechazadas)

        # =========================================================
        # VISTA INICIAL Y CARGAS
        # =========================================================
        self.mostrar_tab_asignaciones()
        self.cargar_datos_asignaciones()
        self.cargar_lista_usuarios_reportes()

    # =========================================================
    # EVENTOS DE VENTANA
    # =========================================================
    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()
        self.window_buttons.setGeometry(0, 0, self.width(), 35)
        # ← NUEVO: verificar actualización después de que cargue la UI
        QTimer.singleShot(2000, self._verificar_actualizacion)

    def _verificar_actualizacion(self):
        self._hilo_update = verificar_actualizacion_async(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.window_buttons.setGeometry(0, 0, self.width(), 35)

    # =========================================================
    # ESTILOS DE BOTONES
    # =========================================================
    def menu_usuarios_icon(self):
        btn = QPushButton("⚙")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(36, 36)
        btn.setFont(QFont("Arial", 14))
        btn.setStyleSheet(
            """
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
        """
        )
        return btn

    def menu_actualizar(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setFont(QFont("Arial", 12, QFont.Bold))
        btn.setStyleSheet(
            """
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
        """
        )
        return btn

    def menu_tab(self, text, active=False):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setFont(QFont("Arial", 12))

        if active:
            btn.setStyleSheet(
                """
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
            """
            )
        else:
            btn.setStyleSheet(
                """
                QPushButton {
                    background: transparent;
                    color: rgba(210,210,210,170);
                    border: none;
                }
                QPushButton:hover {
                    color: rgb(160, 220, 255);
                    border-bottom: 2px solid rgba(160, 220, 255, 140);
                }
            """
            )
        return btn

    # =========================================================
    # CONTROL DE PESTAÑAS
    # =========================================================
    def mostrar_tab_asignaciones(self):
        """Muestra la vista de ASIGNACIONES."""
        self.stack_pages.setCurrentWidget(self.page_asignaciones)

        self.btn_asignaciones_tab.setStyleSheet(self.menu_tab("x", True).styleSheet())
        self.btn_reportes_tab.setStyleSheet(self.menu_tab("x", False).styleSheet())
        self.btn_rechazadas_tab.setStyleSheet(self.menu_tab("x", False).styleSheet())

        self.btn_asignar.show()
        self.combo_usuarios_reportes.hide()

    def mostrar_tab_reportes(self):
        """Muestra la vista de REPORTES."""
        self.stack_pages.setCurrentWidget(self.page_reportes)

        self.btn_asignaciones_tab.setStyleSheet(self.menu_tab("x", False).styleSheet())
        self.btn_reportes_tab.setStyleSheet(self.menu_tab("x", True).styleSheet())
        self.btn_rechazadas_tab.setStyleSheet(self.menu_tab("x", False).styleSheet())

        self.btn_asignar.hide()
        self.combo_usuarios_reportes.show()
        url_inicial =f"{Global.BACKEND_URL}/recomendaciones-usuario/admin/obtener-infimas-asignadas"
        self.cargar_datos_reportes(url_inicial)

    def mostrar_tab_rechazadas(self):
        """Muestra la vista de ÍNFIMAS RECHAZADAS."""
        self.stack_pages.setCurrentWidget(self.page_rechazadas)

        self.btn_asignaciones_tab.setStyleSheet(self.menu_tab("x", False).styleSheet())
        self.btn_reportes_tab.setStyleSheet(self.menu_tab("x", False).styleSheet())
        self.btn_rechazadas_tab.setStyleSheet(self.menu_tab("x", True).styleSheet())

        # En esta pestaña no hay botón/acción superior
        self.btn_asignar.hide()
        self.combo_usuarios_reportes.hide()

        self.cargar_datos_rechazadas()

    def actualizar_vista_actual(self,):  # ---------------------------------------------------------------------------------------
        """Actualiza la pestaña actualmente visible."""
        current_widget = self.stack_pages.currentWidget()

        if current_widget == self.page_asignaciones:
            self.cargar_datos_asignaciones()
        elif current_widget == self.page_reportes:
            self.cargar_datos_reportes()
        elif current_widget == self.page_rechazadas:
            self.cargar_datos_rechazadas()

    # =========================================================
    # ===================== ASIGNACIONES ======================
    # =========================================================
    def cargar_datos_asignaciones(self):
        token = get_session().get("token")

        if not token:
            ClassicMsgBox.warning("Sesión", "Debe iniciar sesión.")
            #QMessageBox.warning(self, "Sesión", "Debe iniciar sesión.")
            return

        try:
            response = requests.get(
                f"{Global.BACKEND_URL}/recomendaciones-usuario/admin/infimas-disponibles",
                headers={"Authorization": f"Bearer {token}"},
                timeout=70,
            )

            if response.status_code != 200:
                ClassicMsgBox.warning("Error", "No se pudieron cargar datos.")
                #QMessageBox.critical(self, "Error", "No se pudieron cargar datos.")
                return

            data = response.json()

            if isinstance(data, dict) and "data" in data:
                data = data["data"]

        except requests.RequestException:
            ClassicMsgBox.warning( "Error", "Servidor no disponible.")
            #QMessageBox.warning(self, "Error", "Servidor no disponible.")
            return

        lista_usuarios = cargar_empleados(self)
        self.table_asignaciones.setRowCount(0)
        self.asignaciones_pendientes.clear()

        for row, item in enumerate(data):
            self.table_asignaciones.insertRow(row)

            nivel = item.get("nivel_de_oportunidad") or 1

            if nivel == 1:
                color = QColor(150, 215, 175)
            elif nivel == 2:
                color = QColor(220, 200, 140)
            else:
                color = QColor(220, 170, 170)

            # Columna 0: Usuario (combo)
            combo = QComboBox()
            combo.setStyleSheet(
                f"""
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
            """
            )

            combo.addItem("Seleccionar usuario")
            combo.addItems(lista_usuarios)
            combo.currentIndexChanged.connect(
                partial(self.on_usuario_changed, row, combo, item)
            )

            self.table_asignaciones.setCellWidget(row, 0, combo)

            # Columnas 1, 2, 3
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

                self.table_asignaciones.setItem(row, col, cell)

        print("Ínfimas disponibles actualizadas")

    def on_usuario_changed(self, row, combo: QComboBox, item_data: dict):
        texto = combo.currentText()

        if texto == "Seleccionar usuario":
            if row in self.asignaciones_pendientes:
                del self.asignaciones_pendientes[row]
            return

        usuario_id = self.usuarios_dict.get(texto)
        id_infima = item_data.get("id_infima")

        if not usuario_id or not id_infima:
            return

        self.asignaciones_pendientes[row] = {
            "usuario_id": usuario_id,
            "id_infima": id_infima,
        }

        print("Pendientes:", self.asignaciones_pendientes)

    def confirmar_asignaciones(self):
        if not self.asignaciones_pendientes:
            ClassicMsgBox.info("Información", "No hay asignaciones seleccionadas.")
            #QMessageBox.information(self, "Información", "No hay asignaciones seleccionadas.")
            return

        token = get_session().get("token")

        confirm =  ClassicMsgBox.question(
            "Confirmar",
            f"¿Asignar {len(self.asignaciones_pendientes)} ínfimas?",
            QMessageBox.Yes | QMessageBox.No)
            #QMessageBox.question(self,"Confirmar",f"¿Asignar {len(self.asignaciones_pendientes)} ínfimas?",QMessageBox.Yes | QMessageBox.No,)
        if confirm != QMessageBox.Yes:
            return

        errores = 0

        for fila, datos in self.asignaciones_pendientes.items():
            payload = {
                "usuario_id": datos["usuario_id"],
                "id_infima": datos["id_infima"],
            }

            try:
                resp = requests.post(
                    f"{Global.BACKEND_URL}/recomendaciones-usuario/admin/asignar-infima-individual",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                )

                if resp.status_code == 200:
                    for c in range(self.table_asignaciones.columnCount()):
                        item = self.table_asignaciones.item(fila, c)
                        if item:
                            item.setBackground(QColor(180, 240, 180))

                    combo = self.table_asignaciones.cellWidget(fila, 0)
                    if combo:
                        combo.setEnabled(False)
                else:
                    errores += 1

            except requests.RequestException:
                errores += 1
                #TypeError: setWindowTitle(self, title: Optional[str]): argument 1 has unexpected type 'WorkspaceManagerUI'

        self.asignaciones_pendientes.clear()
        self.cargar_datos_asignaciones()

        if errores == 0:
            ClassicMsgBox.info( "Exito", "Asignaciones completadas.")
            #QMessageBox.information(self, "OK", "Asignaciones completadas.")
        else:
            ClassicMsgBox.warning("Parcial", f"{errores} asignaciones fallaron.")
            #QMessageBox.warning(self, "Parcial", f"{errores} asignaciones fallaron.")

    # =========================================================
    # ======================= REPORTES ========================
    # =========================================================
    def cargar_datos_reportes(self,url):
        """
        FUNCIÓN DECLARADA PARA REPORTES.
        Aquí se cargará la información desde BD para poblar la tabla de reportes.

        Columnas esperadas:
        - Usuario
        - NIC
        - Descripción
        - Etapa

        """

        token = get_session().get("token")

        if not token:
            ClassicMsgBox.warning("Sesión", "Debe iniciar sesión.")
            #QMessageBox.warning(self, "Sesión", "Debe iniciar sesión.")
            return

        try:
            # =====================================================
            # CONSUMIR AMBOS ENDPOINTS
            # =====================================================
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=70,
            )

            if response.status_code != 200:
                ClassicMsgBox.warning("Error", "No se pudieron cargar los reportes.")
                #QMessageBox.critical(self, "Error", "No se pudieron cargar los reportes.")
                return

            data_obtenida = response.json()

            # Normalizar estructura si viene como { data: [...] }
            if isinstance(data_obtenida, dict) and "data" in data_obtenida:
                data_obtenida = data_obtenida["data"]

            print(f"Reportes obtenidos: {len(data_obtenida)}")

        except requests.RequestException:
            ClassicMsgBox.critical("Error", "Servidor no disponible.")
            #QMessageBox.warning(self, "Error", "Servidor no disponible.")
            return

        # =====================================================
        # LIMPIAR TABLA
        # =====================================================
        self.table_reportes.setRowCount(0)

        # =====================================================
        # LLENAR TABLA
        # =====================================================
        for row, item in enumerate(data_obtenida):
            self.table_reportes.insertRow(row)

            # Color opcional según etapa
            etapa = item.get("etapa", "").lower()

            if "generacion" in etapa:
                color = QColor(180, 210, 255)  # azul suave
            elif "finalizada" in etapa:
                color = QColor(170, 220, 170)  # verde suave
            else:
                color = QColor(220, 220, 220)  # gris

            # Datos esperados
            datos = [
                item.get("usuario", ""), 
                item.get("codigo_necesidad", ""),
                item.get("descripcion_objeto_compra", ""),
                item.get("etapa", ""),
            ]

            for col, val in enumerate(datos):
                cell = QTableWidgetItem(str(val))
                cell.setFlags(Qt.ItemIsEnabled)
                cell.setBackground(color)
                cell.setForeground(QColor(0, 0, 0))

                if col == 3:
                    cell.setTextAlignment(Qt.AlignCenter)

                self.table_reportes.setItem(row, col, cell)

        print("Reportes cargados correctamente")

    def cargar_lista_usuarios_reportes(self):
        """
        FUNCIÓN DECLARADA.
        Debe cargar todos los usuarios en el combo de la pestaña Reportes.
        La lógica real puede ser reemplazada o ampliada luego.
        """
        self.combo_usuarios_reportes.blockSignals(True)
        self.combo_usuarios_reportes.clear()
        self.combo_usuarios_reportes.addItem("Todos los usuarios")

        try:
            lista_usuarios = cargar_empleados(self)
            for usuario in lista_usuarios:
                user_id = self.usuarios_dict.get(usuario)
                self.combo_usuarios_reportes.addItem(usuario,user_id)
        except Exception:
            pass

        self.combo_usuarios_reportes.blockSignals(False)

    def on_usuario_reporte_changed(self):
        """
        FUNCIÓN DECLARADA.
        Al seleccionar un usuario en la pestaña Reportes,
        se debe filtrar la tabla para mostrar únicamente
        las ínfimas que ese usuario está trabajando.
        """
        user_id = self.combo_usuarios_reportes.currentData()

        if user_id is None:
            url = f"{Global.BACKEND_URL}/recomendaciones-usuario/admin/obtener-infimas-asignadas"
        else:
            url = f"{Global.BACKEND_URL}/recomendaciones-usuario/admin/obtener-infimas-asignadas-por-usuario/{user_id}"
        
        print(f"Asignaciones Filtradas por: {user_id}")
        self.cargar_datos_reportes(url)


    # =========================================================
    # ================== ÍNFIMAS RECHAZADAS ===================
    # =========================================================
    def cargar_datos_rechazadas(self):
        """
        FUNCIÓN DECLARADA PARA ÍNFIMAS RECHAZADAS.

        Esta tabla debe mostrar únicamente ínfimas que estén
        en etapa rechazada.

        Columnas esperadas:
        - NIC
        - Descripción
        - Etapa

        La funcionalidad real se implementará después.
        """

        token = get_session().get("token")

        if not token:
            ClassicMsgBox.warning("Sesión", "Debe iniciar sesión.")
            #QMessageBox.warning(self, "Sesión", "Debe iniciar sesión.")
            return

        try:
            # =====================================================
            # CONSUMIR AMBOS ENDPOINTS
            # =====================================================
            response = requests.get(
                f"{Global.BACKEND_URL}/infimas/obtener-infimas-rechazadas",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            if response.status_code != 200:
                ClassicMsgBox.warning("Error", "No se pudieron cargar las infimas rechazadas.")
                #QMessageBox.critical(self, "Error", "No se pudieron cargar las infimas rechazadas.")
                return

            data_rechazadas = response.json()

            # Normalizar estructura si viene como { data: [...] }
            if isinstance(data_rechazadas, dict) and "data" in data_rechazadas:
                data_rechazadas = data_rechazadas["data"]

            # =====================================================
            # UNIFICAR DATA
            # =====================================================
            data = data_rechazadas

            #print(f"Infimas Rechazadas obtenidas: {len(data)}")

        except requests.RequestException:
            ClassicMsgBox.warning("Error", "Servidor no disponible.")
            #QMessageBox.warning(self, "Error", "Servidor no disponible.")
            return

        # =====================================================
        # LIMPIAR TABLA
        # =====================================================
        self.table_rechazadas.setRowCount(0)

        # =====================================================
        # LLENAR TABLA
        # =====================================================
        for row, item in enumerate(data):
            self.table_rechazadas.insertRow(row)

            # Color opcional según etapa
            etapa = item.get("etapa", "").lower()

            if "no seleccionada" in etapa:
                color = QColor(180, 210, 255)  # azul suave

            # Datos esperados
            datos = [
                item.get("codigo_necesidad", ""),
                item.get("descripcion_objeto_compra", ""),
                item.get("etapa", ""),
            ]

            for col, val in enumerate(datos):
                cell = QTableWidgetItem(str(val))
                cell.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                cell.setBackground(color)
                cell.setForeground(QColor(0, 0, 0))

                if col == 3:
                    cell.setTextAlignment(Qt.AlignCenter)

                self.table_rechazadas.setItem(row, col, cell)

        print("Infimas cargadas correctamente")

    # =========================================================
    # VENTANA DE USUARIOS
    # =========================================================
    def abrir_ventana_usuarios(self):
        print("Abriendo gestión de usuarios...")
        try:
            from UI.views.user_management import UserManagementUI

            self.user = UserManagementUI()
            self.user.show()
            QTimer.singleShot(2000, self.hide)
        except ImportError as e:
            print(f"Error de importación: {e}")
            ClassicMsgBox.critical("Error", f"No se pudo abrir la ventana")
            #QMessageBox.critical(self, "Error", f"No se pudo abrir la ventana: {e}")
        except Exception as e:
            print(f"Error al crear ventana: {e}")


# =========================================================
# FUNCIÓN EXTERNA: CARGAR EMPLEADOS
# =========================================================
def cargar_empleados(self):
    token = get_session().get("token")

    resp = requests.get(
        f"{Global.BACKEND_URL}/usuarios/empleados-activos",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    if resp.status_code != 200:
        return []

    usuarios = resp.json()

    self.usuarios_dict = {u["usuario"]: u["id_usuario"] for u in usuarios}

    return list(self.usuarios_dict.keys())
