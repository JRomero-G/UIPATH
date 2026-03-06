# components/classic_msgbox.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox


class ClassicMsgBox:
    """
    QMessageBox con estilo clásico (fondo blanco, texto negro)
    incluso si la app usa un theme oscuro global (QSS).
    """

    @staticmethod
    def _run(show_fn):
        app = QApplication.instance()
        old_qss = app.styleSheet() if app else ""
        try:
            # Desactiva el QSS global temporalmente (esto es lo que lo hace "clásico")
            if app:
                app.setStyleSheet("")
            return show_fn()
        finally:
            # Restaura tu tema original
            if app:
                app.setStyleSheet(old_qss)

    @staticmethod
    def critical(title: str, text: str, parent=None):
        return ClassicMsgBox._run(lambda: QMessageBox.critical(None, title, text))

    @staticmethod
    def warning(title: str, text: str, parent=None):
        return ClassicMsgBox._run(lambda: QMessageBox.warning(None, title, text))

    @staticmethod
    def info(title: str, text: str, parent=None):
        return ClassicMsgBox._run(lambda: QMessageBox.information(None, title, text))

    @staticmethod
    def question(title: str, text: str, parent=None,
                 buttons=QMessageBox.Yes | QMessageBox.No,
                 default_button=QMessageBox.No):
        def _show():
            m = QMessageBox()
            m.setIcon(QMessageBox.Question)
            m.setWindowTitle(title)
            m.setText(text)
            m.setStandardButtons(buttons)
            m.setDefaultButton(default_button)
            m.setWindowModality(Qt.ApplicationModal)
            return m.exec_()
        return ClassicMsgBox._run(_show)