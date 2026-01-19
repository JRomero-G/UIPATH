from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt


class BaseWindow(QWidget):
    def showEvent(self, event):
        super().showEvent(event)
        self.center_window()

    def center_window(self):
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()

        window_geometry = self.frameGeometry()

        x = screen_geometry.center().x() - window_geometry.width() // 2
        y = screen_geometry.center().y() - window_geometry.height() // 2

        self.move(x, y)
