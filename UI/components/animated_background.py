from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QLinearGradient, QPainterPath
from PyQt5.QtWidgets import QWidget


class AnimatedCurvedLine(QWidget):
    def __init__(self, points, parent=None, delay=0.0):
        super().__init__(parent)

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.points = points
        self.t = delay

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    # 🔥 CLAVE: seguir siempre el tamaño del parent
    def paintEvent(self, event):
        if not self.points or len(self.points) < 4:
            return

        # 🔥 Ajustar siempre al tamaño del parent
        if self.parent():
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.moveTo(*self.points[0])
        path.cubicTo(*self.points[1], *self.points[2], *self.points[3])

        # Línea base (SIN CAMBIOS)
        base = QLinearGradient(0, 0, self.width(), 0)
        base.setColorAt(0, QColor(0, 170, 220, 0))
        base.setColorAt(0.5, QColor(0, 200, 255, 200))
        base.setColorAt(1, QColor(0, 170, 220, 0))

        p.setPen(QPen(base, 2))
        p.drawPath(path)

        # Brillo (SIN CAMBIOS)
        glow = QLinearGradient(
            self.t * self.width() - 60, 0,
            self.t * self.width() + 60, 0
        )
        glow.setColorAt(0, QColor(0, 220, 255, 0))
        glow.setColorAt(0.5, QColor(230, 250, 255, 220))
        glow.setColorAt(1, QColor(0, 220, 255, 0))

        p.setPen(QPen(glow, 4))
        p.drawPath(path)

    def animate(self):
        self.t += 0.005
        if self.t > 1.2:
            self.t = 0.0
        self.update()
