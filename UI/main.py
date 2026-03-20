def Iniciar():
    import sys
    import os
    from dotenv import load_dotenv
    from PyQt5.QtWidgets import QApplication
    from UI.views.login import LoginUI
    
    # ===== Cargar variables de entorno =====
    if getattr(sys, 'frozen', False):
        # Si está ejecutando como .exe
        env_path = os.path.join(os.path.dirname(sys.executable), ".env")
    else:
        # Desarrollo
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")

    load_dotenv(env_path)

    # ===== Iniciar aplicación =====
    app = QApplication(sys.argv)

    login = LoginUI()
    login.show()

    sys.exit(app.exec_())