import subprocess
import sys
import logging
from datetime import datetime


# ══════════════════════════════════════
# CONFIGURACIÓN DEL LOGGER
# ══════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════
SCRIPTS = [
    "src/tasks/1_Recolector.py",
    "src/tasks/2_Keywords.py",
    "src/tasks/3_Download_PDFs.py",
    "src/tasks/4_Contraindications.py",
]


def formato_duracion(segundos):
    """Convierte segundos a formato legible: 1h 23m 45s"""
    segundos = int(segundos)
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segs = segundos % 60

    if horas > 0:
        return f"{horas}h {minutos}m {segs}s"
    elif minutos > 0:
        return f"{minutos}m {segs}s"
    else:
        return f"{segs}s"


def run_all_scripts():
    logger.info("=" * 55)
    logger.info("INICIO DE CICLO DE EJECUCIÓN")
    logger.info("=" * 55)

    tiempo_total_inicio = datetime.now()

    for i, script in enumerate(SCRIPTS, 1):
        logger.info(f"[{i}/{len(SCRIPTS)}] Iniciando: {script}")
        tiempo_inicio = datetime.now()

        result = subprocess.run(
            [sys.executable, script],
            check=False
        )

        duracion = (datetime.now() - tiempo_inicio).total_seconds() 

        if result.returncode != 0:
            logger.error(f"[{i}/{len(SCRIPTS)}] FALLÓ: {script} (código {result.returncode}) — {formato_duracion(duracion)}")
            logger.error("Cadena detenida. Scripts siguientes NO se ejecutarán.")
            sys.exit(1)
        else:
            logger.info(f"[{i}/{len(SCRIPTS)}] OK: {script} — {formato_duracion(duracion)}")

    duracion_total = (datetime.now() - tiempo_total_inicio).total_seconds()  
    logger.info("=" * 55)
    logger.info(f"CICLO COMPLETADO — Tiempo total: {formato_duracion(duracion_total)}")
    logger.info("=" * 55)


if __name__ == "__main__":
    run_all_scripts()