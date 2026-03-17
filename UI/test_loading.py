import sys
from PyQt5.QtWidgets import QApplication
from ..UI.views.workspace_manager import WorkspaceManagerUI
from ..UI.views.workspace_userRE import WorkspaceUserREUI
from ..UI.views.workspace_user import WorkspaceUserUI
from ..UI.views.user_management import UserManagementUI

app = QApplication(sys.argv)
w = WorkspaceUserREUI()
w.show()
sys.exit(app.exec_())