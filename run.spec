# -*- mode: python ; coding: utf-8 -*-
#
# Build SOLO del frontend (cliente PyQt5 de Gestorex).
#
# El frontend es un cliente HTTP puro: habla con el backend de Cloud Run via
# BACKEND_URL y descarga documentos desde GCS. NO ejecuta FastAPI/uvicorn,
# no abre MySQL y no corre los scripts de src/tasks (esos viven en GitHub
# Actions y en Cloud Run). Por eso aqui no se empaquetan ni esas dependencias
# ni src/tasks ni src/Credentials.

# leer la version automaticamente desde version.py
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from src.Config.version import CURRENT_VERSION

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Unico data real: los iconos/imagenes que carga la UI.
        # src/ NO se copia como data: sus modulos se recogen como codigo via
        # los hiddenimports de abajo, y copiarlo entero metia en el .exe la
        # service account de GCP (src/Credentials) y los scripts de backend.
        ('UI/assets', 'UI/assets'),
    ],
    hiddenimports=[
        # ── PyQt5 (toda la UI) ──
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'PyQt5.QtNetwork',
        'PyQt5.sip',

        # ── HTTP: todas las llamadas a BACKEND_URL y a la API de GitHub ──
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',

        # ── Google Cloud Storage (src/utils/Descargar_documentos_bucket.py) ──
        'google.cloud.storage',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'google.oauth2',
        'google.oauth2.service_account',
        # google.auth.crypt las importa de forma condicional:
        'cryptography',
        'rsa',
        'pyasn1',
        'pyasn1_modules',

        # ── Configuracion ──
        'dotenv',

        # ── Modulos internos usados por la UI ──
        'Config',                   # Config.py de la raiz (from Config import Global)
        'UI',
        'src.Config.version',
        'src.utils.updater',
        'src.utils.Descargar_documentos_bucket',

        # ── Sistema de actualizaciones ──
        'packaging',
        'packaging.version',
        'webbrowser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Stack de backend: no se usa en el cliente.
        'fastapi',
        'uvicorn',
        'starlette',
        'python_multipart',
        'pydantic',
        'pydantic_core',
        'email_validator',
        'sqlalchemy',
        'pymysql',
        'MySQLdb',
        'mysql',
        'jose',
        'passlib',
        'bcrypt',
        'vertexai',
        'google.genai',
        'src.tasks',
        'src.Database',

        # Scraping / ofimatica: solo en los workflows de recoleccion.
        'selenium',
        'webdriver_manager',
        'bs4',
        'docx',
        'openpyxl',

        # Cientifico / dev: nunca se usa.
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='run',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['UI/assets/Logo_app.ico'],
)
