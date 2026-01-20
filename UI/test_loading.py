import sys
from PyQt5.QtWidgets import QApplication
from views.workspace_user import WorkspaceUserUI

app = QApplication(sys.argv)
w = WorkspaceUserUI()
w.show()
sys.exit(app.exec_())
