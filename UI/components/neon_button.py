from PyQt5.QtCore import QRect, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QPushButton


class NeonButton(QPushButton):
    def __init__(self, text, x, y, parent):
        super().__init__(text, parent)
        self.setGeometry(x, y, 360, 52)
        self.setFont(QFont("Arial", 12, QFont.Bold))

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(160) ######
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        self.normal_rect = self.geometry()

        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 2px solid rgb(0,190,240);
                color: white;
                border-radius: 14px;
            }
        """)

    def enterEvent(self, e):
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(QRect(
            self.normal_rect.x() - 4,
            self.normal_rect.y() - 4,
            self.normal_rect.width() + 8,
            self.normal_rect.height() + 8
        ))
        self.anim.start()

    def leaveEvent(self, e):
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(self.normal_rect)
        self.anim.start()
