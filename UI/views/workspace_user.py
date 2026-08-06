import os
# jason
from PyQt5.QtWidgets import QMessageBox
from Config import Global
# naye
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
    QWidget,
    QSizePolicy,
)
import requests  # jason
from UI.config import BASE_DIR, ASSETS_DIR, WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR
from UI.config import set_session, _session, get_session
from UI.components.table_scroll_style import apply_table_scrollbar_style
from UI.components.base_window import BaseWindow
from UI.components.table_validations import setup_row_logic
from UI.components.btns_windows import WindowButtons  # ← IMPORTADO
from src.Config.version import CURRENT_VERSION
from src.utils.updater import verificar_actualizacion_async
from UI.components.classic_msgbox import ClassicMsgBox



class WorkspaceUserUI(BaseWindow):
    def __init__(self):
        super().__init__()

        # infimas pendientes para analizar
        self.Pendientes_de_analisis = {}

        # infimas pendientes de eliminacion
        self.eliminacion_pendiente = {}

        self.datos_filas = {}              # {row: dict_completo_de_infima}


        self.setWindowTitle(f"Gestorex {CURRENT_VERSION} - Usuario")
        # Ahora la ventana es redimensionable
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        # ================= BOTONES VENTANA =================
        # ← AÑADIDO: Botones minimizar/maximizar/cerrar en parte superior
        self.window_buttons = WindowButtons(self)
        self.window_buttons.setGeometry(0, 0, WINDOW_WIDTH, 35)

        # ================== LAYOUT PRINCIPAL ==================
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 50, 30, 20)
        main_layout.setSpacing(18)

        # ================== MENÚ SUPERIOR ==================
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(12)

        self.btn_actualizar = self.menu_actualizar("⟳  Actualizar")
        self.btn_recomendados = self.menu_tab("Recomendados", active=True)
        self.btn_revision = self.menu_tab("Revisión y Envío")
        #self.btn_revision.clicked.connect(self.open_workspace_userRE)

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

        title = QLabel(f"Gestorex {CURRENT_VERSION}")
        title.setFont(QFont("Arial", 15, QFont.Bold))
        title.setStyleSheet("color: white;")

        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(title)
        menu_layout.addLayout(brand_layout)

        main_layout.addLayout(menu_layout)

        # ================== TABLA ==================
        self.table = QTableWidget(0, 7)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setHorizontalHeaderLabels(
            ["", "NIC", "Descripción", "Grado de recomendación", "Nivel","URL", "Acción"]
        )

        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.ElideNone)

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 32)

        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

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
                background: rgba(255,255,255,190);
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

        self.Cargar_infimas()
        self.table.sortItems(4, Qt.AscendingOrder)
        main_layout.addWidget(self.table)
        apply_table_scrollbar_style(self.table) 

        # ================== BOTÓN INFERIOR ==================
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        # ======================= Boton Analizar ====================
        self.btn_analizar = self.action_button("Analizar")
        self.btn_analizar.clicked.connect(self.confirmar_analisis)

        #===================== Boton Actualizar =================
        self.btn_actualizar.clicked.connect(self.Cargar_infimas)

        #====================== Boton Revision =======================
        self.btn_revision.clicked.connect(self.open_workspace_userRE)

        bottom_layout.addWidget(self.btn_analizar)
        main_layout.addLayout(bottom_layout)

    # Abrir maximizada
    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()
        #Actualizar ancho de botones al maximizar
        self.window_buttons.setGeometry(0, 0, self.width(), 35)
        #verificar actualización después de que cargue la UI
        QTimer.singleShot(2000, self._verificar_actualizacion)

    def _verificar_actualizacion(self):
        self._hilo_update = verificar_actualizacion_async(self)

    # Actualizar botones al redimensionar - Misma Funcion que showEvent se deberia eliminar
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.window_buttons.setGeometry(0, 0, self.width(), 35)

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

    def delete_button(self, bg_color, row):
        container = QWidget()
        container.setStyleSheet(f"background-color: {bg_color};")
        container.setCursor(Qt.PointingHandCursor)  # ← Agregar cursor
        container.setProperty("enabled_state", True)  # ← estado habilitado por defecto

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("🗑")
        icon.setStyleSheet("color: rgb(140, 30, 30); font-size: 15px;")
        icon.setObjectName("icon")  # ← nombre para encontrar el boton

        text = QLabel("Eliminar")
        text.setStyleSheet("color: rgb(180, 40, 40); font-weight: bold;")
        text.setObjectName("text")  # ← nombre para encontrarlo después

        def enter_event(event):
            if not container.property("enabled_state"):  # ← verificar estado
                return
            icon.setStyleSheet("color: rgb(220, 20, 20); font-size: 17px;")
            text.setStyleSheet("""
                color: rgb(220, 60, 60);
                font-weight: bold;
                text-decoration: underline;
            """)

        def leave_event(event):
            if not container.property("enabled_state"):  # ← verificar estado
                return
            icon.setStyleSheet("color: rgb(140, 30, 30); font-size: 15px;")
            text.setStyleSheet("color: rgb(180, 40, 40); font-weight: bold;")

        # Detectar clic en el botón
        def mouse_press_event(event):
            if not container.property("enabled_state"):  # ← bloquear clic
                return
            self.on_eliminar_clicked(row)  # ← Llamar función al hacer clic

        container.enterEvent = enter_event
        container.leaveEvent = leave_event
        container.mousePressEvent = mouse_press_event  # ← Conectar evento

        layout.addWidget(icon)
        layout.addWidget(text)
        return container



    #================= Funciones Auxiliares para evitar confilcto de selecciones ==========================

    def deshabilitar_boton_eliminar(self, row):
        """Desactiva visualmente el botón eliminar de una fila."""
        widget = self.table.cellWidget(row, 6)
        if not widget:
            return

        widget.setProperty("enabled_state", False)
        widget.setCursor(Qt.ForbiddenCursor)  # ← Cursor de prohibido

        # Cambiar estilo a gris apagado
        icon = widget.findChild(QLabel, "icon")
        text = widget.findChild(QLabel, "text")
        if icon:
            icon.setStyleSheet("color: rgb(180, 180, 180); font-size: 15px;")
        if text:
            text.setStyleSheet("color: rgb(180, 180, 180); font-weight: bold;")

    def habilitar_boton_eliminar(self, row):
        """Reactiva visualmente el botón eliminar de una fila."""
        widget = self.table.cellWidget(row, 6)
        if not widget:
            return

        widget.setProperty("enabled_state", True)
        widget.setCursor(Qt.PointingHandCursor)

        # Restaurar estilo original
        icon = widget.findChild(QLabel, "icon")
        text = widget.findChild(QLabel, "text")
        if icon:
            icon.setStyleSheet("color: rgb(140, 30, 30); font-size: 15px;")
        if text:
            text.setStyleSheet("color: rgb(180, 40, 40); font-weight: bold;")



    # ==================Cargar datos en la tabla ==================

    def Cargar_infimas(self):
        sesion = get_session()
        try:
            response = requests.get(
                f"{Global.BACKEND_URL}/recomendaciones-usuario/mis-infimas",
                headers={"Authorization": f"Bearer {sesion.get('token')}"},
                timeout=20,
            )

            if response.status_code != 200:
                ClassicMsgBox.critical("Error",f"Error al obtener ínfimas.")
                #QMessageBox.critical(self,"Error",f"Error al obtener ínfimas.",)
                return

            data = response.json()
            print("INFIMAS RECIBIDA:", len(data))
            #print("INFIMAS CARGADAS:", data)

            # Si la API devuelve {"data": [...]}
            if isinstance(data, dict) and "data" in data:
                data = data["data"]

            if not isinstance(data, list):
                #ClassicMsgBox.warning("Error", "La API no devolvió una lista de registros.")
                #QMessageBox.critical(self, "Error", "La API no devolvió una lista de registros.")
                print("DATA INVALIDA en cargar Infimas:", data)
                return
            

        except requests.RequestException as e:
            ClassicMsgBox.warning("Error", "No se pudo conectar al servidor.")
            #QMessageBox.warning(self, "Error", "No se pudo conectar al servidor.")
            print("EXCEPTION:", e)
            return

        #  Limpiar antes de cargar los datos
        self.table.setRowCount(0)
        self.Pendientes_de_analisis.clear()
        self.eliminacion_pendiente.clear()
        self.datos_filas.clear()

        if not data:
            ClassicMsgBox.warning("Advertencia", "No hay registros para mostrar")
            print("⚠️ No hay registros para mostrar")
            return
        
        # Ciclo para cargar las filas en la tabla, obtenemos el numero de 
        # registros en "data" para crear la fila y guardamos la informacion en item 
        for row, item in enumerate(data):
            self.table.insertRow(row)

            #  Guardamos las "filas" de cada registro obtenido en la respuesta del endpoint
            #  y que guardamos en "data" 
            self.datos_filas[row] = item

            nivel = (
                item.get("nivel_de_oportunidad") or "no asignado"
            )  # sino tiene nivel asignado por defecto sera "no asignado" aunque deberia ser "nivel 3" 

            if nivel == "nivel 1":
                row_color = QColor(150, 215, 175)
                grado = "Recomendado"
            elif nivel == "nivel 2":
                row_color = QColor(220, 200, 140)
                grado = "Poco recomendado"
            else:
                row_color = QColor(220, 170, 170)
                grado = "No recomendado"

            text_color = QColor(0, 0, 0)

            # ================= Celdas nuevo ==================
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

            # Grado
            self.table.setCellWidget(row, 3, self.grado_button(grado, nic, row_color))

            # nivel
            cell = QTableWidgetItem(str(nivel))
            cell.setFlags(Qt.ItemIsEnabled)
            cell.setForeground(text_color)
            cell.setBackground(row_color)
            cell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, cell)

            # URL
            url = item.get("entidad_contratante_url", "")
            cell = QTableWidgetItem(url)
            cell.setFlags(Qt.ItemIsEnabled)
            cell.setBackground(row_color)
            cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setCellWidget(row, 5, self.link_button(url, row_color))

            # Col 5: Acción
            self.table.setCellWidget(row, 6, self.delete_button(row_color.name(),row))
            # ================= Fin Celdas nuevo ==================

            #Conectar evento de checkbox (FUERA DEL LOOP)
        try:
            self.table.itemChanged.disconnect()
        except:
            pass
            
        self.table.itemChanged.connect(self.on_table_item_changed)
            
        print("Ínfimas cargadas y eventos conectados")

        setup_row_logic(self.table, row, nic_col=0, action_col=5) 

    def on_table_item_changed(self, item: QTableWidgetItem):
        """
        Se ejecuta cuando CUALQUIER item de la tabla cambia.
        Filtramos solo cambios en columna 0 (checkboxes).
        """
        # Solo procesar cambios en columna 0 (checkboxes)
        if item.column() != 0:
            return
        
        #fila del checbox
        row = item.row()
        
        # Verificamos que la fila forme parte delos registros obtenidos  guardados en data_filas previamente
        if row not in self.datos_filas:
            print(f" No hay datos para la fila {row}")
            return
        
        # Obtenemos los datos de la fila
        item_data = self.datos_filas[row]
        
        # Procesar el check/uncheck
        self.on_infima_check_analisis(row, item, item_data)

    def on_infima_check_analisis(self, row: int, check_item: QTableWidgetItem, item_data: dict):
        """
        Cuando el usuario marca/desmarca el checkbox para análisis.
        """
        esta_marcado = check_item.checkState() == Qt.CheckState.Checked
        id_infima = item_data.get("id_infima")
        codigo_necesidad = item_data.get("codigo_necesidad", "N/A")
        
        if not id_infima:
            print(f" Fila {row}: no tiene id_infima")
            return
        
        # Si está MARCADO → agregar a pendientes
        if esta_marcado:
            #  Verificar si ya está en pendientes de eliminación
            if row in self.eliminacion_pendiente:
                # Ya está en eliminación → rechazar sin warning (ya está bloqueado visualmente)
                self.table.blockSignals(True)
                check_item.setCheckState(Qt.Unchecked)
                self.table.blockSignals(False)
                return
            
            self.Pendientes_de_analisis[row] = {
                "id_infima": id_infima,
                "codigo_necesidad": codigo_necesidad
            }

            self.deshabilitar_boton_eliminar(row)  # Desactivamos el boton eliminar para evitar conflicto

            print(f" Fila {row}: Ínfima {id_infima} ({codigo_necesidad}) agregada")
            print(f" Pendientes_de_analisis = {self.Pendientes_de_analisis}")
        
        # Si está DESMARCADO → quitar de pendientes
        else:
            if row in self.Pendientes_de_analisis:
                del self.Pendientes_de_analisis[row]
                self.habilitar_boton_eliminar(row)  # ← Habilitamos el boton si ya no esta seleccionada
                print(f" Fila {row}: Ínfima {id_infima} removida")
                print(f" Pendientes_de_analisis = {self.Pendientes_de_analisis}")

    def on_eliminar_clicked(self, row_original: int):
        """
        Cuando el usuario hace clic en el botón Eliminar.
        """
        #  Buscar la fila actual en la tabla usando id_infima
        # porque el row original puede haber cambiado después del sort
        
        if row_original not in self.datos_filas:
            print(f" No hay datos para la fila original {row_original}")
            return
        
        item_data = self.datos_filas[row_original]
        id_infima = item_data.get("id_infima")
        codigo_necesidad = item_data.get("codigo_necesidad", "N/A")
        
        if not id_infima:
            print(f" Fila {row_original}: no tiene id_infima")
            return
        
        #  Buscar en qué fila ACTUAL está este id_infima (después del sort)
        row_actual = None
        for r in range(self.table.rowCount()):
            # Buscar por el código NIC en columna 1
            nic_item = self.table.item(r, 1)
            if nic_item and nic_item.text() == codigo_necesidad:
                row_actual = r
                break
        
        if row_actual is None:
            print(f" No se encontró la fila actual para id_infima {id_infima}")
            return
        
        print(f" Fila original: {row_original}, Fila actual: {row_actual}")
        
        # Si ya está en pendientes de eliminación → removerla
        if row_actual in self.eliminacion_pendiente:
            del self.eliminacion_pendiente[row_actual]
            print(f"Ínfima {id_infima} removida de eliminación")
            
            # Rehabilitar checkbox
            self.table.blockSignals(True)
            check_item = self.table.item(row_actual, 0)
            if check_item:
                check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            self.table.blockSignals(False)

            # Restaurar color original según nivel
            nivel = item_data.get("nivel_de_oportunidad", "no asignado")
            if nivel == "nivel 1":
                row_color = QColor(150, 215, 175)
                hex_color = "#96d7af"
            elif nivel == "nivel 2":
                row_color = QColor(220, 200, 140)
                hex_color = "#dcc88c"
            else:
                row_color = QColor(220, 170, 170)
                hex_color = "#dcaaaa"
            
            #  Repintar fila ACTUAL (no la original)
            for c in range(self.table.columnCount()):
                item = self.table.item(row_actual, c)  # ← Usar row_actual
                if item:
                    item.setBackground(row_color)

            # Restaurar también el widget del botón
            widget = self.table.cellWidget(row_actual, 5)
            if widget:
                widget.setStyleSheet(f"background-color: {hex_color};")

            print(f" Fila {row_actual} restaurada a color original")
            
            # Si NO está → agregarla
        else:
            # Agregar a eliminación
            self.eliminacion_pendiente[row_actual] = {
                "id_infima": id_infima,
                "codigo_necesidad": codigo_necesidad
            }
            print(f"Ínfima {id_infima} agregada para eliminación")
            
            # Deshabilitar checkbox
            self.table.blockSignals(True)
            check_item = self.table.item(row_actual, 0)
            if check_item:
                check_item.setFlags(Qt.ItemIsEnabled)  # ← Quitar Qt.ItemIsUserCheckable
            self.table.blockSignals(False)

            #  Pintar fila ACTUAL de rojo claro
            color_eliminacion = QColor(255, 200, 200)
            for c in range(self.table.columnCount()):
                item = self.table.item(row_actual, c)  # ← Usar row_actual
                if item:
                    item.setBackground(color_eliminacion)
            
            # Pintar también el widget del botón
            widget = self.table.cellWidget(row_actual, 5)
            if widget:
                widget.setStyleSheet("background-color: #ffc8c8;")  # mismo rojo claro en hex
            #print(f" Fila {row_actual} pintada de rojo (eliminación)")
        
        print(f" Pendientes_de_eliminacion = {self.eliminacion_pendiente}")

    
    # Confirmar análisis (IGUAL ESTRUCTURA QUE confirmar_asignaciones del manager)
    def confirmar_analisis(self):
        """
        Procesa todas las ínfimas marcadas con checkbox.
        Cambia su etapa a 'en generacion'.
        """
        
        if not self.Pendientes_de_analisis and not self.eliminacion_pendiente:
            ClassicMsgBox.info("Información","No hay ínfimas seleccionadas para anailisis ni para eliminacion.")
            #QMessageBox.information(self,"Información","No hay ínfimas seleccionadas para anailisis ni para eliminacion.")
            return
        
        token = get_session().get("token")
        
        if not token:
            ClassicMsgBox.critical( "Error", "No hay sesión activa.")
            #QMessageBox.critical(self, "Error", "No hay sesión activa.")
            return
        
        # ====== PASO 1: CONFIRMAR ELIMINACIÓN (si hay) ======
        if self.eliminacion_pendiente:
            
            confirm_eliminar = ClassicMsgBox.question(
                "⚠️ Confirmar Eliminación",
                f"¿Deseas eliminar {len(self.eliminacion_pendiente)} ínfima(s)?\n\n"
                "Esta acción las quitará de tus asignaciones.",
                QMessageBox.Yes | QMessageBox.No)
            #QMessageBox.question(self,"⚠️ Confirmar Eliminación",f"¿Deseas eliminar {len(self.eliminacion_pendiente)} ínfima(s)?\n\n""Esta acción las quitará de tus asignaciones.",QMessageBox.Yes | QMessageBox.No            )
            
            if confirm_eliminar != QMessageBox.Yes:
                print(" Usuario canceló la eliminación")
                return  # ← Cancelar el proceso
            
            # Eliminar ínfimas
            eliminadas_exitosas, eliminadas_errores = self.ejecutar_eliminacion(token)
        else:
            eliminadas_exitosas = 0
            eliminadas_errores = 0

        # ====== PASO 2: CONFIRMAR ANÁLISIS (si hay) ======
        if self.Pendientes_de_analisis:
            
            

            confirm_analizar = ClassicMsgBox.question(
                "✅ Confirmar Análisis",
                f"¿Marcar {len(self.Pendientes_de_analisis)} ínfima(s) para análisis?",
                QMessageBox.Yes | QMessageBox.No)
            
            if confirm_analizar != QMessageBox.Yes:
                print(" Usuario canceló el análisis")
                # No recargar tabla para que mantenga las selecciones
                return
            
            # Analizar ínfimas
            analizadas_exitosas, analizadas_errores = self.ejecutar_analisis(token)
        
        else:
            analizadas_exitosas = 0
            analizadas_errores = 0
        
        # ====== PASO 3: LIMPIAR Y RECARGAR ======
        self.Pendientes_de_analisis.clear()
        self.eliminacion_pendiente.clear()
        self.Cargar_infimas()
        
        # ====== PASO 4: MOSTRAR RESULTADO ======
        mensaje = ""
        if eliminadas_exitosas > 0 or analizadas_exitosas > 0:
            mensaje += f"✅ Completado:\n"
            if eliminadas_exitosas > 0:
                mensaje += f"  • {eliminadas_exitosas} ínfima(s) eliminada(s)\n"
            if analizadas_exitosas > 0:
                mensaje += f"  • {analizadas_exitosas} ínfima(s) marcada(s) para análisis\n"
        
        if eliminadas_errores > 0 or analizadas_errores > 0:
            mensaje += f"\n⚠️ Errores:\n"
            if eliminadas_errores > 0:
                mensaje += f"  • {eliminadas_errores} error(es) al eliminar\n"
            if analizadas_errores > 0:
                mensaje += f"  • {analizadas_errores} error(es) al analizar\n"
        
        if eliminadas_errores > 0 or analizadas_errores > 0:
            ClassicMsgBox.warning("Exito Parcial", mensaje)
            #QMessageBox.warning(self, "Completado con errores", mensaje)
        else:
            ClassicMsgBox.warning("Exito", mensaje)
            #QMessageBox.information(self, "Éxito", mensaje)

    def ejecutar_eliminacion(self, token):
        """
        Elimina las ínfimas en pendientes_de_eliminacion.
        Retorna: (exitosas, errores)
        """
        exitosas = 0
        errores = 0
        
        pendientes_copia = dict(self.eliminacion_pendiente)
        
        for fila, datos in pendientes_copia.items():
            payload = datos["id_infima"]
            
            try:
                resp = requests.patch(
                    f"{Global.BACKEND_URL}/infimas/no-seleccionada/{payload}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20,
                )
                
                if resp.status_code == 200:
                    exitosas += 1
                    print(f" Ínfima {payload} marcada como no seleccionada")
                    
                else:
                    errores += 1
                    try:
                        error_msg = resp.json().get("detail", resp.text)
                    except:
                        error_msg = resp.text
                    print(f" Error al <<marcar infimas como no seleccionada>>  {payload}: {error_msg}")
                
            except requests.RequestException as e:
                errores += 1
                print(f" Error de conexión al <<marcar infimas como no seleccionada>>  {payload}: {e}")
        
        return exitosas, errores

    def ejecutar_analisis(self, token):
        """
        Analiza las ínfimas en Pendientes_de_analisis.
        Retorna: (exitosas, errores)
        """
        exitosas = 0
        errores = 0
        
        pendientes_copia = dict(self.Pendientes_de_analisis)
        
        for fila, datos in pendientes_copia.items():
            id_infima = datos["id_infima"]
            
            try:
                resp = requests.patch(
                    f"{Global.BACKEND_URL}/infimas/analizar-infimas/{id_infima}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20,
                )
                
                print(f" PATCH /analizar-infimas/{id_infima} → Status: {resp.status_code}")
                
                if resp.status_code == 200:
                    exitosas += 1
                    
                    # Pintar fila de verde
                    for c in range(self.table.columnCount()):
                        item = self.table.item(fila, c)
                        if item:
                            item.setBackground(QColor(180, 240, 180))
                    
                    # Desmarcar checkbox
                    self.table.blockSignals(True)
                    check_item = self.table.item(fila, 0)
                    if check_item:
                        check_item.setCheckState(Qt.Unchecked)
                        check_item.setFlags(Qt.ItemIsEnabled)
                    self.table.blockSignals(False)
                    
                    print(f" Ínfima {id_infima} marcada para análisis")
                
                else:
                    errores += 1
                    try:
                        error_msg = resp.json().get("detail", "Error desconocido")
                    except:
                        error_msg = resp.text
                    print(f" Error al analizar ínfima {id_infima}: {error_msg}")
            
            except requests.RequestException as e:
                errores += 1
                print(f" Error de conexión al analizar ínfima {id_infima}: {e}")
        
        return exitosas, errores

    # ================== Funciones para celdas personalizadas ==================

    def link_button(self, url: str, bg_color: QColor):
        """Celda con enlace clickeable que abre el navegador."""
        container = QWidget()
        container.setStyleSheet(f"background-color: rgb({bg_color.red()},{bg_color.green()},{bg_color.blue()});")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel()

        if url and url.strip():

            label.setText('<a href="{}" style="color:#1A00FF;font-weight:bold;"> Abrir enlace</a>'.format(url))
            label.setOpenExternalLinks(True)  # ← abre el navegador al hacer clic
            label.setCursor(Qt.PointingHandCursor)
        else:
            label.setText("Sin enlace")
            label.setStyleSheet("color: rgb(150,150,150);")
        layout.addWidget(label)
        
        return container

    def grado_button(self, grado: str, codigo_necesidad: str, bg_color: QColor):
        """Botón de grado que abre un popup con la evaluación de la ínfima."""
        container = QWidget()
        container.setStyleSheet(
        f"""
        QWidget {{
            background-color: rgb({bg_color.red()},{bg_color.green()},{bg_color.blue()});
        }}
        QWidget:hover {{
            background-color: rgb({bg_color.red()-30},{bg_color.green()-30},{bg_color.blue()-30});
        }}
        """
        )
        container.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setAlignment(Qt.AlignCenter)

        # Texto según grado
        if grado == "Recomendado":
            texto = "✅ Recomendado"
            color_texto = "rgb(30, 120, 60)"
        elif grado == "Poco recomendado":
            texto = "⚠️ Poco recomendado"
            color_texto = "rgb(160, 100, 0)"
        else:
            texto = "❌ No recomendado"
            color_texto = "rgb(160, 30, 30)"

        label = QLabel(texto)
        label.setFont(QFont("Arial", 9, QFont.Bold))
        label.setStyleSheet(f"color: {color_texto};")
        label.setAlignment(Qt.AlignCenter)

        def mouse_press_event(event):
            self.mostrar_evaluacion(codigo_necesidad)

        container.mousePressEvent = mouse_press_event

        layout.addWidget(label)
        return container

    def mostrar_evaluacion(self, codigo_necesidad: str):
        """Consulta y muestra la evaluación de una ínfima."""
        token = get_session().get("token")

        try:
            response = requests.get(
                f"{Global.BACKEND_URL}/infimas/obtener-evaluacion-infima/{codigo_necesidad}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )

            #print(f"STATUS: {response.status_code}")
            #print(f"RESPUESTA: {response.text}") 

            if response.status_code == 404:
                ClassicMsgBox.info(
                    "Sin evaluación",
                    f"La ínfima {codigo_necesidad} no tiene contraindicaciones registradas."
                )
                return

            if response.status_code != 200:
                ClassicMsgBox.warning("Error", "No se pudo obtener las contraindicaciones.")
                return

            data = response.json()

            # Normalizar si viene como {"data": {...}}
            if isinstance(data, dict) and "data" in data:
                data = data["data"]

            # Verificar si hay justificación (no vacía, no null, no None)
            justificacion = data.get("justificacion", "").strip()
            
            # Si no hay justificación (recomendación nivel 1 - bueno)
            if not justificacion or justificacion.lower() in ["null", "none", ""]:
                justificacion = "No hay Contraindicaciones Encontradas en el análisis. Revisar link de proceso para más información."
                es_nivel_1 = True
            else:
                es_nivel_1 = False

            # Mostrar el popup
            msg = QMessageBox()
            msg.setWindowTitle("Evaluación de ínfima")
            msg.setText(f"<b>Código NIC:</b> {codigo_necesidad}")
            msg.setInformativeText(f"<b>Justificación:</b><br>{justificacion}")
            
            # Opcional: Cambiar ícono o agregar info extra si es nivel 1
            if es_nivel_1:
                msg.setIcon(QMessageBox.Information)
                # Podrías agregar un texto adicional
                msg.setDetailedText("Esto indica una recomendación de Nivel 1 (buen resultado)")
            else:
                msg.setIcon(QMessageBox.Information)
                
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()

        except requests.RequestException:
            ClassicMsgBox.warning("Error", "No se pudo conectar al servidor.")

    # llamar al RE
    def open_workspace_userRE(self):
        print("Abriendo Workspace User RE...")
        try:
            from UI.views.workspace_userRE import WorkspaceUserREUI
            self.workspace_re = WorkspaceUserREUI()
            self.workspace_re.show()
            #self.hide()
            QTimer.singleShot(2000, self.hide)  # Esperar 2 segundos antes de ocultar
        except ImportError as e:
            print(f"Error de importación: {e}")
            ClassicMsgBox.warning("Error", f"No se pudo abrir la ventana")
            #QMessageBox.critical(self, "Error", f"No se pudo abrir la ventana: {e}")
        except Exception as e:
            print(f"Error al crear ventana: {e}")