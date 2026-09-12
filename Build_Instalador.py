"""
Build_Instalador.py - compila el instalable del FRONTEND de Gestorex.

Ejecutar esto en lugar de compilar a mano:

    python Build_Instalador.py

Cadena completa:
    src/Config/version.py  ->  instalador.iss  ->  PyInstaller (run.spec)
    ->  dist/run.exe + dist/.env  ->  Inno Setup  ->  instalador_output/

El resultado se llama Installer_Gestorex_v<VERSION>.exe, nombre que debe
coincidir exactamente con el que publica src/Config/version_route.py, porque
es el que busca el autoactualizador (src/utils/updater.py) en los releases
de GitHub.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── Trabajar siempre desde la raiz del repo, se invoque desde donde se invoque ──
RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ))

from src.Config.version import CURRENT_VERSION

ISS_PATH = RAIZ / "instalador.iss"
ENV_PATH = RAIZ / ".env"
DIST = RAIZ / "dist"
BUILD = RAIZ / "build"
SALIDA = RAIZ / "instalador_output"
NOMBRE_INSTALADOR = f"Installer_Gestorex_v{CURRENT_VERSION}.exe"


def abortar(mensaje: str) -> None:
    print(f"\n[ERROR] {mensaje}")
    sys.exit(1)


print(f"Compilando Gestorex v{CURRENT_VERSION} (solo frontend)...\n")

# ── 0. Comprobaciones previas ──────────────────────────────────────────────
if not ENV_PATH.exists():
    abortar(
        ".env no encontrado en la raiz del repositorio.\n"
        "        El instalador lo empaqueta y la app no arranca sin el.\n"
        "        Copia .env.example a .env y rellena los valores reales."
    )

env_texto = ENV_PATH.read_text(encoding="utf-8", errors="replace")


def valor_env(clave: str) -> str:
    m = re.search(rf"^{clave}\s*=\s*(.*)$", env_texto, re.MULTILINE)
    return m.group(1).strip() if m else ""


faltantes = [c for c in ("BACKEND_URL", "SECRET_KEY_JWT") if not valor_env(c)]
if faltantes:
    abortar(f".env incompleto, faltan valores para: {', '.join(faltantes)}")

if not valor_env("GITHUB_KEY"):
    print(
        "[AVISO] GITHUB_KEY esta vacio o ausente en .env.\n"
        "        El instalable se generara igual, pero el autoactualizador\n"
        "        (src/utils/updater.py) fallara en cada cliente con\n"
        "        'No se encontro el token de GitHub'.\n"
    )

if not (RAIZ / "UI" / "assets" / "Logo_app.ico").exists():
    abortar("Falta UI/assets/Logo_app.ico (icono de la app y del instalador).")

# ── 1. Sincronizar la version en instalador.iss ────────────────────────────
contenido = ISS_PATH.read_text(encoding="utf-8")
contenido = re.sub(
    r'#define AppVersion ".*?"',
    f'#define AppVersion "{CURRENT_VERSION}"',
    contenido,
)
contenido = re.sub(
    r"OutputBaseFilename=.*",
    f"OutputBaseFilename=Installer_Gestorex_v{CURRENT_VERSION}",
    contenido,
)
ISS_PATH.write_text(contenido, encoding="utf-8")
print(f"[OK] instalador.iss sincronizado a v{CURRENT_VERSION}")

# ── 2. Limpiar builds anteriores ───────────────────────────────────────────
for carpeta in (BUILD, DIST):
    if carpeta.exists():
        shutil.rmtree(carpeta, ignore_errors=True)
print("[OK] build/ y dist/ eliminadas")

# ── 3. Compilar con PyInstaller ────────────────────────────────────────────
print("\nCompilando con PyInstaller (esto tarda varios minutos)...\n")
resultado = subprocess.run(
    [sys.executable, "-m", "PyInstaller", "--noconfirm", "run.spec"],
    cwd=RAIZ,
)
if resultado.returncode != 0:
    abortar(f"PyInstaller fallo con codigo {resultado.returncode}. Revisa el log de arriba.")

exe_generado = DIST / "run.exe"
if not exe_generado.exists():
    abortar(f"PyInstaller termino pero no existe {exe_generado}.")

mb = exe_generado.stat().st_size / (1024 * 1024)
print(f"\n[OK] dist/run.exe generado ({mb:.1f} MB)")

# ── 4. Copiar .env junto al ejecutable ─────────────────────────────────────
shutil.copy(ENV_PATH, DIST / ".env")
print("[OK] .env copiado a dist/")

# ── 5. Compilar el instalador con Inno Setup ───────────────────────────────
SALIDA.mkdir(exist_ok=True)

usuario = os.environ.get("USERNAME", "")
rutas_inno = [
    Path(rf"C:\Users\{usuario}\AppData\Local\Programs\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
]
desde_path = shutil.which("ISCC")
if desde_path:
    rutas_inno.insert(0, Path(desde_path))

inno_exe = next((p for p in rutas_inno if p.exists()), None)

if not inno_exe:
    print(
        "\n[AVISO] Inno Setup 6 no esta instalado (no se encontro ISCC.exe).\n"
        "        El ejecutable ya esta listo en dist/run.exe, pero falta empaquetarlo.\n"
        "        Instala Inno Setup 6 desde https://jrsoftware.org/isdl.php y vuelve\n"
        "        a ejecutar este script, o abre instalador.iss con Inno Setup y pulsa F9."
    )
    sys.exit(2)

print(f"\nInno Setup encontrado en: {inno_exe}")
resultado = subprocess.run([str(inno_exe), str(ISS_PATH)], cwd=RAIZ)
if resultado.returncode != 0:
    abortar(f"Inno Setup fallo con codigo {resultado.returncode}.")

instalador = SALIDA / NOMBRE_INSTALADOR
if not instalador.exists():
    abortar(f"Inno Setup termino pero no existe {instalador}.")

mb = instalador.stat().st_size / (1024 * 1024)
print(f"\n[OK] {instalador} ({mb:.1f} MB)")
print(f"\nBuild v{CURRENT_VERSION} completado.")
print(
    f"Publicalo en el release con tag 'v{CURRENT_VERSION}' del repo mmedinafv/UIPATH\n"
    f"con el nombre de asset exacto: {NOMBRE_INSTALADOR}"
)
