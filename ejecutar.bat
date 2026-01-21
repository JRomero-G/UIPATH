@echo off
cd /d %~dp0

if not exist logs mkdir logs

:: Forma universal de obtener fecha/hora (YYYYMMDD_HHMMSS)
for /f "tokens=1-6 delims=.:,/ " %%a in ('powershell -Command "Get-Date -format 'yyyyMMdd_HHmmss'"') do set datetime=%%a

set log_file=logs\log_%datetime%.txt

echo Iniciando proceso a las %time%... > %log_file%
python main.py >> %log_file% 2>&1

echo Proceso terminado.
pause