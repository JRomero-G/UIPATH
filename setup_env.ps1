<#
.SYNOPSIS
Script para activar el entorno virtual, actualizar dependencias y ejecutar scripts.
USO:
1. Abrir PowerShell en la raíz del proyecto.
2. Ejecutar: .\setup_env.ps1
#>

# ------------------------------
# 1️⃣ Definir nombre del entorno
# ------------------------------
$VENV_NAME = ".venv"

# ------------------------------
# 2️⃣ Activar entorno virtual
# ------------------------------
if (Test-Path "$VENV_NAME\Scripts\Activate.ps1") {
    Write-Host "Activando entorno virtual $VENV_NAME..."
    . "$VENV_NAME\Scripts\Activate.ps1"
} else {
    Write-Host "No se encontró el entorno virtual. Creando uno nuevo..."
    python -m venv $VENV_NAME
    . "$VENV_NAME\Scripts\Activate.ps1"
}

# ------------------------------
# 3️⃣ Actualizar pip y hatch
# ------------------------------
Write-Host "Actualizando pip y setuptools..."
python -m pip install --upgrade pip setuptools

Write-Host "Instalando o actualizando Hatch..."
pip install --upgrade hatch

# ------------------------------
# 4️⃣ Instalar dependencias desde pyproject.toml
# ------------------------------
Write-Host "Instalando dependencias del proyecto desde pyproject.toml..."
# Esto instalará todas las dependencias especificadas y cualquier nueva que agregues
hatch env update

# ------------------------------
# 5️⃣ Recordatorio de uso
# ------------------------------
Write-Host "`n✅ Entorno listo."
Write-Host "Para ejecutar tus scripts dentro del entorno activado:"
Write-Host "hatch run python src\tasks\3_Download_PDFs.py"
Write-Host "O cualquier otro script dentro del proyecto."

Write-Host "`n💡 Cada vez que agregues una nueva librería a pyproject.toml, vuelve a ejecutar este script para actualizar el entorno."
