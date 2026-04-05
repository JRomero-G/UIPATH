import os

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QColor, QPixmap
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QVBoxLayout,
    QHeaderView, QWidget, QMessageBox
)

from UI.config import *
from UI.components.table_scroll_style import apply_table_scrollbar_style
from UI.components.base_window import BaseWindow
from UI.components.btns_windows import WindowButtons
from Config import Global
import requests
from UI.config import get_session
from src.Config.version import CURRENT_VERSION
from UI.components.classic_msgbox import ClassicMsgBox
from src.utils.Descargar_documentos_bucket import descargar_archivos_nic


class WorkspaceUserREUI(BaseWindow):
    def __init__(self):
        super().__init__()

        # ── Ínfimas pendientes de envío ──
        self.pendientes_de_envio = {}   # {row: {"id_infima": int, "codigo_necesidad": str}}
        self.datos_filas         = {}   # {row: dict_completo}

        self.setWindowTitle(f"Gestorex {CURRENT_VERSION} - Usuario")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(f"background-color:{BG_COLOR};")

        # ================= BOTONES VENTANA =================
        self.window_buttons = WindowButtons(self)
        self.window_buttons.setGeometry(0, 0, WINDOW_WIDTH, 35)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 50, 30, 20)
        main_layout.setSpacing(18)

        # ================== MENÚ SUPERIOR ==================
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(12)

        self.btn_actualizar   = self.menu_actualizar("⟳  Actualizar")
        self.btn_recomendados = self.menu_tab("Recomendados", active=False)
        self.btn_revision     = self.menu_tab("Revisión y Envío", active=True)

        menu_layout.addWidget(self.btn_actualizar)
        menu_layout.addWidget(self.btn_recomendados)
        menu_layout.addWidget(self.btn_revision)
        menu_layout.addStretch()

        # ---- LOGO + TEXTO ----
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)
        brand_layout.setAlignment(Qt.AlignVCenter)

        logo_label = QLabel()
        base_dir   = os.path.dirname(os.path.abspath(__file__))
        logo_path  = os.path.join(base_dir, "..", "assets", "logo2.png")
        pixmap     = QPixmap(logo_path).scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_label.setPixmap(pixmap)

        title = QLabel(f"Gestorex {CURRENT_VERSION}")
        title.setFont(QFont("Arial", 15, QFont.Bold))
        title.setStyleSheet("color: white;")

        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(title)
        menu_layout.addLayout(brand_layout)
        main_layout.addLayout(menu_layout)

        # ================== TABLA ==================
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "", "NIC", "Resumen", "Fecha límite","URL", "Documento de contratación"
        ])
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
        """)

        main_layout.addWidget(self.table)
        apply_table_scrollbar_style(self.table)

        # ================== BOTONES INFERIORES ==================
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_enviar = self.action_button("Enviar")
        self.btn_enviar.clicked.connect(self.confirmar_envio)
        self.btn_enviar.setEnabled(False)   # inicia deshabilitado

        bottom_layout.addWidget(self.btn_enviar)
        main_layout.addLayout(bottom_layout)

        #CARGAR DATOS
        self.Cargar_Datos()
        
        # ================== CONEXIONES ==================
        self.btn_actualizar.clicked.connect(self.Cargar_Datos)
        self.btn_recomendados.clicked.connect(self.open_workspace_user)
        self.table.itemChanged.connect(self.on_table_item_changed)

        self.update_send_button_state()
        QTimer.singleShot(0, self.showMaximized)

    # ================== REDIMENSIONAR ==================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.window_buttons.setGeometry(0, 0, self.width(), 35)

    # ================== ESTILOS DE BOTONES ==================
    def menu_actualizar(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setFont(QFont("Arial", 12, QFont.Bold))
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,35);
                color: white; border-radius: 8px;
                padding: 4px 14px;
                border: 1px solid rgba(255,255,255,40);
            }
            QPushButton:hover { background-color: rgba(255,255,255,55); }
            QPushButton:pressed { background-color: rgba(255,255,255,75); }
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
                    background: transparent; color: rgb(120,220,255);
                    border: none; font-weight: bold;
                    border-bottom: 2px solid rgb(120,220,255);
                }
                QPushButton:hover { color: rgb(170,235,255); }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: rgba(210,210,210,170); border: none;
                }
                QPushButton:hover {
                    color: rgb(160,220,255);
                    border-bottom: 2px solid rgba(160,220,255,140);
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
                background-color: rgb(60,130,200);
                color: white; border-radius: 22px; border: none;
            }
            QPushButton:hover { background-color: rgb(80,150,220); }
            QPushButton:pressed { background-color: rgb(45,110,175); }
            QPushButton:disabled {
                background-color: rgba(100,100,100,120);
                color: rgba(255,255,255,80);
            }
        """)
        return btn

    # ================== BOTÓN DE CARPETA POR FILA ==================
    def document_links(self, bg_color, nic=""):
        container = QWidget()
        container.setStyleSheet(f"background-color: {bg_color};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setAlignment(Qt.AlignCenter)

        btn = QPushButton("📁  Revisar los Documentos")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                color: rgb(90,160,220); font-weight: bold;
                background: transparent; border: none;
                text-align: left; padding: 2px 4px;
            }
            QPushButton:hover {
                color: rgb(120,190,255);
                text-decoration: underline;
            }
        """)
        btn.clicked.connect(lambda checked, n=nic: self.abrir_carpeta(n))
        layout.addWidget(btn)
        return container

    def abrir_carpeta(self, nic):
        """Descarga los archivos del bucket y abre la carpeta local."""
        import subprocess
        from pathlib import Path
        from PyQt5.QtWidgets import QApplication

        directorio_base = Path.home() / "Documents" / "Documentos de Contratacion"
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            carpeta_nic = descargar_archivos_nic(
                codigo_necesidad=nic,
                directorio_base=directorio_base
            )
            subprocess.Popen(f'explorer "{carpeta_nic}"')

            # Marcar el check de esa fila automáticamente
            for row in range(self.table.rowCount()):
                nic_item = self.table.item(row, 1)
                if nic_item and nic_item.text() == nic:
                    self.mark_row_checked(row)
                    break

        except RuntimeError as e:
            ClassicMsgBox.warning("Archivos no disponibles", str(e))
        except Exception as e:
            ClassicMsgBox.critical(
                "Error al descargar",
                f"Ocurrió un error al conectarse al bucket:\n\n{str(e)}"
            )
        finally:
            QApplication.restoreOverrideCursor()

    # ================== CARGA DE DATOS ==================
    def Cargar_Datos(self):
        try:
            session_data = get_session()
            token = session_data.get("token") if session_data else None

            response = requests.get(
                f"{Global.BACKEND_URL}/recomendaciones-usuario/mis-infimas-finalizadas",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=25
            )
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.ConnectionError:
            ClassicMsgBox.critical("Error", "No se pudo conectar al servidor.")
            return
        except requests.exceptions.Timeout:
            ClassicMsgBox.critical("Error", "El servidor tardó demasiado en responder.")
            return
        except Exception as e:
            ClassicMsgBox.critical("Error", f"Error al cargar datos: {str(e)}")
            return

        self.pendientes_de_envio.clear()
        self.datos_filas.clear()

        self.table.blockSignals(True)
        self.table.setRowCount(len(data))

        for row, item in enumerate(data):
            self.datos_filas[row] = item
            row_color = QColor(150, 215, 175)

            # Col 0 — Check
            check_item = QTableWidgetItem()
            check_item.setCheckState(Qt.Unchecked)
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setBackground(row_color)
            self.table.setItem(row, 0, check_item)

            # Col 1 — NIC
            nic = item.get("codigo_necesidad", "")
            nic_item = QTableWidgetItem(nic)
            nic_item.setFlags(Qt.ItemIsEnabled)
            nic_item.setBackground(row_color)
            nic_item.setForeground(QColor(0, 0, 0))
            self.table.setItem(row, 1, nic_item)

            # Col 2 — Descripción
            desc_item = QTableWidgetItem(item.get("descripcion_objeto_compra", ""))
            desc_item.setFlags(Qt.ItemIsEnabled)
            desc_item.setBackground(row_color)
            desc_item.setForeground(QColor(0, 0, 0))
            self.table.setItem(row, 2, desc_item)

            # Col 3 — Fecha límite
            fecha = item.get("fecha_limite_proformas", "")
            if fecha:
                try:
                    from datetime import datetime
                    fecha = datetime.strptime(fecha[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    pass
            fecha_item = QTableWidgetItem(fecha)
            fecha_item.setFlags(Qt.ItemIsEnabled)
            fecha_item.setTextAlignment(Qt.AlignCenter)
            fecha_item.setBackground(row_color)
            fecha_item.setForeground(QColor(0, 0, 0))
            self.table.setItem(row, 3, fecha_item)

            # Col 4 → enlace clickeable
            url = item.get("entidad_contratante_url", "")
            self.table.setCellWidget(row, 4, self.link_button(url, row_color))

            # Col 5 — Botón carpeta
            self.table.setCellWidget(row, 5, self.document_links(row_color.name(), nic))

        self.table.blockSignals(False)
        self.update_send_button_state()

    # ================== LÓGICA DE CHECKS ==================
    def on_table_item_changed(self, item: QTableWidgetItem):
        if item.column() != 0:
            return
        row = item.row()
        if row not in self.datos_filas:
            return
        self.on_infima_check_envio(row, item, self.datos_filas[row])

    def on_infima_check_envio(self, row: int, check_item: QTableWidgetItem, item_data: dict):
        esta_marcado  = check_item.checkState() == Qt.Checked
        id_infima     = item_data.get("id_infima")
        codigo        = item_data.get("codigo_necesidad", "N/A")

        if not id_infima:
            return

        if esta_marcado:
            self.pendientes_de_envio[row] = {
                "id_infima":        id_infima,
                "codigo_necesidad": codigo
            }
            print(f" Fila {row}: {codigo} agregada para envío")
        else:
            self.pendientes_de_envio.pop(row, None)
            print(f" Fila {row}: {codigo} removida de envío")

        print(f"   pendientes_de_envio = {self.pendientes_de_envio}")
        self.update_send_button_state()

    def mark_row_checked(self, row: int):
        """Marca el check de una fila sin disparar itemChanged en cadena."""
        item = self.table.item(row, 0)
        if not item:
            return
        self.table.blockSignals(True)
        item.setCheckState(Qt.Checked)
        self.table.blockSignals(False)
        # Agregar manualmente a pendientes
        if row in self.datos_filas:
            d = self.datos_filas[row]
            self.pendientes_de_envio[row] = {
                "id_infima":        d.get("id_infima"),
                "codigo_necesidad": d.get("codigo_necesidad", "")
            }
        self.update_send_button_state()

    def update_send_button_state(self):
        """Habilita Enviar solo si hay al menos una fila marcada."""
        self.btn_enviar.setEnabled(bool(self.pendientes_de_envio))

    # ================== CONFIRMAR Y EJECUTAR ENVÍO ==================
    def confirmar_envio(self):
        if not self.pendientes_de_envio:
            ClassicMsgBox.info("Información", "No hay ínfimas seleccionadas para enviar.")
            return

        token = get_session().get("token")
        if not token:
            ClassicMsgBox.critical("Error", "No hay sesión activa.")
            return

        confirmacion = ClassicMsgBox.question(
            "✅ Confirmar Envío",
            f"¿Deseas marcar {len(self.pendientes_de_envio)} ínfima(s) como 'enviada'?\n\n"
            "Esta acción cambiará su etapa a 'enviada'.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirmacion != QMessageBox.Yes:
            return

        exitosas, errores = self.ejecutar_envio(token)

        self.pendientes_de_envio.clear()
        self.Cargar_Datos()

        if errores == 0:
            ClassicMsgBox.info(
                "Éxito",
                f"✅ {exitosas} ínfima(s) marcada(s) como 'enviada' correctamente."
            )
        else:
            ClassicMsgBox.warning(
                "Completado con errores",
                f"✅ {exitosas} enviada(s) correctamente.\n⚠️ {errores} error(es) al enviar."
            )

    def ejecutar_envio(self, token: str):
        """
        Llama a PATCH /infimas/enviar-infimas/{id_infima} por cada pendiente.
        Retorna (exitosas, errores).
        """
        exitosas = 0
        errores  = 0

        for row, datos in dict(self.pendientes_de_envio).items():
            id_infima = datos["id_infima"]
            codigo    = datos["codigo_necesidad"]

            try:
                resp = requests.patch(
                    f"{Global.BACKEND_URL}/infimas/enviar-infimas/{id_infima}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20,
                )
                print(f"PATCH /enviar-infimas/{id_infima} → {resp.status_code}")

                if resp.status_code == 200:
                    exitosas += 1
                    # Pintar la fila de azul claro para indicar éxito
                    color_enviado = QColor(180, 210, 240)
                    for c in range(self.table.columnCount()):
                        cell = self.table.item(row, c)
                        if cell:
                            cell.setBackground(color_enviado)
                    # Desmarcar y bloquear checkbox
                    self.table.blockSignals(True)
                    check = self.table.item(row, 0)
                    if check:
                        check.setCheckState(Qt.Unchecked)
                        check.setFlags(Qt.ItemIsEnabled)
                    self.table.blockSignals(False)
                    print(f"  ✅ {codigo} enviada correctamente")
                else:
                    errores += 1
                    try:
                        msg = resp.json().get("detail", "Error desconocido")
                    except Exception:
                        msg = resp.text
                    print(f"  ❌ Error al enviar {codigo}: {msg}")

            except requests.RequestException as e:
                errores += 1
                print(f"  ❌ Conexión fallida para {codigo}: {e}")

        return exitosas, errores

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

    # ================== NAVEGACIÓN ==================
    def open_workspace_user(self):
        try:
            from UI.views.workspace_user import WorkspaceUserUI
            self.workspace = WorkspaceUserUI()
            self.workspace.show()
            QTimer.singleShot(200, self.hide)
        except Exception as e:
            print(f"Error al abrir WorkspaceUserUI: {e}")
            ClassicMsgBox.warning("Error", "No se pudo abrir la ventana de Recomendados.")