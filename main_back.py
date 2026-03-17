import subprocess
import sys

SCRIPTS = [
    "src/tasks/1_Recolector.py",
    "src/tasks/2_Keywords.py",
    "src/tasks/3_Download_PDFs.py",
    "src/tasks/4_Contraindications.py",
    "src/tasks/5_Preforms_generator.py"
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
