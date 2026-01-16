import subprocess
import sys

SCRIPTS = [
    "src/tasks/1_Recolector.py",
    "src/tasks/3_keywords.py",
    "src/tasks/4_download_PDFs.py",
]


def run_all_scripts():
    for script in SCRIPTS:
        print(f"\nEjecutando: {script}")
        result = subprocess.run([sys.executable, script], check=False)
        if result.returncode != 0:
            print(f"Error en {script} (código {result.returncode})")
            break
        else:
            print(f"{script} terminado correctamente.")
