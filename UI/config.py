import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(BASE_DIR, "assets")

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 650

BG_COLOR = "#020b1a"
TEXT_COLOR = "rgb(220,245,255)"

#=============== Parte de Login - Sesión ===============
_session = {}

def set_session(data: dict):
    global _session
    _session = data

def get_session():
    return _session

def get_token():
    return _session.get("token")

#=============== Fin de Login - Sesión ===============
