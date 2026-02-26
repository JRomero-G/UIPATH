from PyQt5.QtCore import QRect, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLineEdit


class AnimatedInput(QLineEdit):
    def __init__(self, text, x, y, parent):
        super().__init__(parent)
        self.setGeometry(x, y, 360, 48)
        self.setPlaceholderText(text)
        self.setFont(QFont("Arial", 12))

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(160)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        # Guardar geometría inicial
        self._normal_rect = self.geometry()

        self.setStyleSheet("""
            QLineEdit {
                background: rgba(10,20,40,230);
                border: 2px solid rgb(0,170,220);
                color: white;
                padding-left: 12px;
                border-radius: 10px;
            }
        """)

    @property
    def normal_rect(self):
        """Siempre retorna la geometría actual como base"""
        return self._normal_rect

    def move(self, x, y):
        """Sobrescribir move para actualizar normal_rect"""
        super().move(x, y)
        self._normal_rect = self.geometry()

    def setGeometry(self, x, y, w, h):
        """Sobrescribir setGeometry para actualizar normal_rect"""
        super().setGeometry(x, y, w, h)
        self._normal_rect = self.geometry()

    def resize(self, w, h):
        """Sobrescribir resize para actualizar normal_rect"""
        super().resize(w, h)
        self._normal_rect = self.geometry()

    def enterEvent(self, e):
        current = self.geometry()
        self.anim.setStartValue(current)
        self.anim.setEndValue(QRect(
            current.x() - 3,
            current.y() - 3,
            current.width() + 6,
            current.height() + 6
        ))
        self.anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(self._normal_rect)
        self.anim.start()
        super().leaveEvent(e)