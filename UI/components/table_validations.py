from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

def setup_row_logic(table, row, nic_col=0, action_col=4):
    """
    Gestiona la fila para que:
    - No se pueda marcar NIC y Eliminar al mismo tiempo.
    - Cambia el color de toda la fila al presionar Eliminar (incluyendo widgets en celdas).
    - Permite deshacer Eliminar.
    """

    nic_item = table.item(row, nic_col)
    delete_widget = table.cellWidget(row, action_col)
    doc_widget = table.cellWidget(row, 3)  # columna de documentos

    if nic_item is None or delete_widget is None or doc_widget is None:
        return

    # Estado inicial
    deleted = False
    original_color = QColor(150, 215, 175)
    delete_color = QColor(255, 165, 0)

    def set_row_color(color):
        # Cambiar color de items
        for col in range(table.columnCount()):
            cell = table.item(row, col)
            if cell:
                cell.setBackground(color)
        # Cambiar color de widgets
        doc_widget.setStyleSheet(f"background-color: {color.name()};")
        delete_widget.setStyleSheet(f"background-color: {color.name()};")

    def toggle_eliminar(event):
        nonlocal deleted
        deleted = not deleted

        if deleted:
            # Bloquea NIC
            nic_item.setFlags(Qt.ItemIsEnabled)
            nic_item.setCheckState(Qt.Unchecked)
            set_row_color(delete_color)
        else:
            # Desbloquea NIC
            nic_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            set_row_color(original_color)

    delete_widget.mousePressEvent = toggle_eliminar

    # Bloqueo de Eliminar si NIC está marcado
    def nic_changed(item):
        if item.row() == row:
            if item.checkState() == Qt.Checked:
                delete_widget.setEnabled(False)
            else:
                delete_widget.setEnabled(True)

    table.itemChanged.connect(nic_changed)