import os
import subprocess
import sys
import re

# ===========================================================
# Verificar que estamos usando Python 3.13 o mayor
# ===========================================================
if sys.version_info < (3, 13):
    print(
        f"Error: Este script requiere Python 3.13 o mayor, se detectó Python {sys.version_info.major}.{sys.version_info.minor}"
    )
    sys.exit(1)

# ===========================================================
# Carpeta del proyecto
# ===========================================================
PROYECTO_DIR = os.path.dirname(os.path.abspath(__file__))

# ===========================================================
# Patrón regex para detectar importaciones
# ===========================================================
import_pattern = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)")

librerias = set()

# ===========================================================
# Buscar en todos los archivos .py del proyecto y subcarpetas
# ===========================================================
for root, dirs, files in os.walk(PROYECTO_DIR):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    match = import_pattern.match(line)
                    if match:
                        librerias.add(match.group(1))

# ===========================================================
# Instalar cada librería usando pip
# ===========================================================
for lib in librerias:
    print(f"Instalando {lib}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
    except subprocess.CalledProcessError:
        print(f"No se pudo instalar: {lib}")

print("¡Todas las librerías detectadas se instalaron o ya estaban presentes!")
