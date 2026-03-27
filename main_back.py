import subprocess
import sys
from datetime import datetime

SCRIPTS = [
    "src/tasks/1_Recolector.py",
    "src/tasks/2_Keywords.py",
    "src/tasks/3_Download_PDFs.py",
    "src/tasks/4_Contraindications.py",
]

def run_all_scripts():
    print(f"\n{'='*50}")
    print(f" Inicio de ciclo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    for i, script in enumerate(SCRIPTS, 1):
        print(f"\n▶ [{i}/{len(SCRIPTS)}] Ejecutando: {script}")

        result = subprocess.run(
            [sys.executable, script],
            check=False,
            capture_output=False  # muestra logs en tiempo real en Render
        )

        if result.returncode != 0:
            print(f"\n Error en {script} (código {result.returncode})")
            print(" Cadena detenida. Los siguientes scripts NO se ejecutarán.")
            sys.exit(1)  # Render marcará este job como fallido
        else:
            print(f" [{i}/{len(SCRIPTS)}] {script} completado.")

    print(f"\n Ciclo completo: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    run_all_scripts()