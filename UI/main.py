import sys
import os
# Agrega 'UI/' al path → Python encuentra: views, components, config
UI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, UI_DIR)

# Agrega 'UIPATH/' al path → Python encuentra: UI como paquete
ROOT_DIR = os.path.dirname(UI_DIR)
sys.path.insert(0, ROOT_DIR)

from PyQt5.QtWidgets import QApplication
from views.login import LoginUI


if __name__ == "__main__":
    app = QApplication(sys.argv)

    login = LoginUI()  # 👈 referencia viva
    login.show()

    sys.exit(app.exec_())
