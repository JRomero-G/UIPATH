from PyQt5.QtCore import QRect, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QPushButton


class NeonButton(QPushButton):
    def __init__(self, text, x, y, parent):
        super().__init__(text, parent)
        self.setGeometry(x, y, 360, 52)
        self.setFont(QFont("Arial", 12, QFont.Bold))

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(160)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        # Guardar geometría inicial
        self._normal_rect = self.geometry()

        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 2px solid rgb(0,190,240);
                color: white;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: rgba(0,190,240,20);
            }
            QPushButton:pressed {
                background: rgba(0,190,240,40);
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
            current.x() - 4,
            current.y() - 4,
            current.width() + 8,
            current.height() + 8
        ))
        self.anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(self._normal_rect)
        self.anim.start()
        super().leaveEvent(e)