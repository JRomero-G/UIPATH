import sys
from PyQt5.QtWidgets import QApplication
from views.workspace_manager import WorkspaceManagerUI
from views.workspace_userRE import WorkspaceUserREUI
from views.workspace_user import WorkspaceUserUI
from views.user_management import UserManagementUI

app = QApplication(sys.argv)
w = UserManagementUI()
w.show()
sys.exit(app.exec_())