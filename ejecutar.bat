@echo off
REM ======================================================
REM Ejecuta run_all.py y guarda logs en la carpeta "logs"
REM ======================================================

REM Cambia al directorio donde está este .bat
cd /d %~dp0

REM Crear carpeta logs si no existe
if not exist logs (
    mkdir logs
)

REM Obtener fecha y hora actual para el log
set datetime=%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
REM Reemplaza espacios en la hora
set datetime=%datetime: =0%

REM Nombre del archivo log dentro de logs
set log_file=logs\log_%datetime%.txt

REM Ejecuta Python y guarda salida en el log
python main.py >> %log_file% 2>&1
