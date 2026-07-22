# -*- mode: python ; coding: utf-8 -*-

#leer la versión automáticamente desde version.py
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from src.Config.version import CURRENT_VERSION

block_cipher = None  

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('UI/assets', 'UI/assets'),
        ('src', 'src'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        # PyQt5
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'PyQt5.QtNetwork',
        'PyQt5.sip',

        # FastAPI + Uvicorn (modo local)
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        'starlette.responses',
        'python_multipart',

        # Base de datos
        'sqlalchemy',
        'sqlalchemy.dialects.mysql',
        'sqlalchemy.dialects.mysql.pymysql',
        'sqlalchemy.orm',
        'sqlalchemy.pool',
        'MySQLdb',
        'pymysql',
        'mysql.connector',
        'mysql.connector.plugins',
        'mysql.connector.plugins.mysql_native_password',

        # Autenticación y seguridad
        'jose',
        'jose.jwt',
        'jose.exceptions',
        'passlib',
        'passlib.handlers',
        'passlib.handlers.bcrypt',
        'passlib.context',
        'bcrypt',
        'cryptography',
        'rsa',
        'ecdsa',
        'pyasn1',

        # HTTP y red
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'dnspython',

        # Pydantic y validación
        'pydantic',
        'pydantic_core',
        'email_validator',
        'annotated_types',

        # Google / VertexAI
        'vertexai',
        'google.cloud.storage',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'google.oauth2',
        'google.oauth2.credentials',
        'google.oauth2.service_account',

        # Utilidades
        'dotenv',
        'python_dotenv',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'colorama',
        'packaging',
        'click',
        'anyio',
        'anyio._backends._asyncio',
        'h11',

        # Tus módulos internos
        'src.Database',
        'src.Config',
        'src.tasks',
        'src.utils',
        'UI',

        # ← NUEVOS: para el sistema de actualizaciones
        'src.Config.version',
        'src.Config.version_route',
        'src.utils.updater',
        'packaging.version',
        'webbrowser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    icon=['UI\\assets\\Logo_app.ico'],
)