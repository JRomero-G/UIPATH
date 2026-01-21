from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QLinearGradient, QPainterPath
from PyQt5.QtWidgets import QWidget


class AnimatedCurvedLine(QWidget):
    def __init__(self, points, parent=None,delay=0.0):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(0, 0, parent.width(), parent.height())

        self.points = points
        self.t = 0.0
        self.dir = 1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    def animate(self):
        self.t += 0.012 * self.dir
        if self.t >= 1 or self.t <= 0:
            self.dir *= -1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.moveTo(*self.points[0])
        path.cubicTo(*self.points[1], *self.points[2], *self.points[3])

        base = QLinearGradient(0, 0, self.width(), 0)
        base.setColorAt(0, QColor(0, 170, 220, 0))
        base.setColorAt(0.5, QColor(0, 200, 255, 200))
        base.setColorAt(1, QColor(0, 170, 220, 0))

        p.setPen(QPen(base, 2))
        p.drawPath(path)

        glow = QLinearGradient(
            self.t * self.width() - 60, 0,
            self.t * self.width() + 60, 0
        )
        glow.setColorAt(0, QColor(0, 220, 255, 0))
        glow.setColorAt(0.5, QColor(230, 250, 255, 220))
        glow.setColorAt(1, QColor(0, 220, 255, 0))

        p.setPen(QPen(glow, 4))
        p.drawPath(path)
