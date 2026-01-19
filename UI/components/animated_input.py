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

        self.normal_rect = self.geometry()

        self.setStyleSheet("""
            QLineEdit {
                background: rgba(10,20,40,230);
                border: 2px solid rgb(0,170,220);
                color: white;
                padding-left: 12px;
                border-radius: 10px;
            }
        """)

    def enterEvent(self, e):
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(QRect(
            self.normal_rect.x() - 3,
            self.normal_rect.y() - 3,
            self.normal_rect.width() + 6,
            self.normal_rect.height() + 6
        ))
        self.anim.start()

    def leaveEvent(self, e):
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(self.normal_rect)
        self.anim.start()
