# build.py — ejecutar esto en lugar de compilar manualmente
import os
import subprocess
from src.Config.version import CURRENT_VERSION

print(f"🔨 Compilando versión {CURRENT_VERSION}...")

# ── 1. Actualizar versión en instalador.iss automáticamente ──
iss_path = "instalador.iss"

with open(iss_path, "r", encoding="utf-8") as f:
    contenido = f.read()

# Reemplazar la línea de versión
import re
contenido = re.sub(
    r'#define AppVersion ".*?"',
    f'#define AppVersion "{CURRENT_VERSION}"',
    contenido
)

# Reemplazar el nombre del archivo de salida
contenido = re.sub(
    r'OutputBaseFilename=.*',
    f'OutputBaseFilename=Installer_Gestorex_v{CURRENT_VERSION}',
    contenido
)

with open(iss_path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"✅ instalador.iss actualizado a v{CURRENT_VERSION}")

# ── 2. Limpiar builds anteriores ──
os.system("powershell Remove-Item -Recurse -Force build, dist")
print("✅ Carpetas build/ y dist/ eliminadas")

# ── 3. Compilar PyInstaller ──
print(" Compilando con PyInstaller...")
os.system("pyinstaller run.spec")

# ── 4. Copiar .env ──
os.system("copy .env dist\\.env")
print("✅ .env copiado a dist/")

# ── 5. Compilar Inno Setup ──


# ── Buscar Inno Setup automáticamente ──
usuario = os.environ.get("USERNAME", "")

inno_paths = [
    # Instalación por usuario (varía según quién lo instala)
    rf"C:\Users\{usuario}\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    # Instalación global
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]

inno_exe = next((p for p in inno_paths if os.path.exists(p)), None)

if inno_exe:
    print(f" Inno Setup encontrado en: {inno_exe}")
    subprocess.run([inno_exe, iss_path])
    print(f"✅ Installer_Gestorex_v{CURRENT_VERSION}.exe generado en instalador_output/")
else:
    print("⚠️  Inno Setup no encontrado en ninguna ruta conocida.")
    print("    Compila manualmente abriendo instalador.iss con Inno Setup (F9)")

print(f"\n Build v{CURRENT_VERSION} completado!")

