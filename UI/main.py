import sys
from PyQt5.QtWidgets import QApplication
from .views.login import LoginUI

if __name__ == "__main__":
    app = QApplication(sys.argv)

    login = LoginUI()  # 👈 referencia viva
    login.show()

    sys.exit(app.exec_())
