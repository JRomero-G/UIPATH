"""
gcs_downloader.py
Descarga ficha técnica (.docx) y proforma (.xlsm) desde el bucket GCS
directamente en la carpeta del NIC, sin subcarpetas.

Resultado:
    ~/Documents/Documentos de Contratacion/
        nic-1768013520001-2026-00071/
            nic-1768013520001-2026-00071_ficha_tecnica.docx
            nic-1768013520001-2026-00071.xlsm

Ubicación: src/utils/gcs_downloader.py
"""

import json
import tempfile
from pathlib import Path


def _obtener_cliente_gcs():
    from google.oauth2 import service_account
    from google.cloud import storage
    from Config import Global

    raw = Global.RENDER_CRENDENTIALS_JSON
    if raw is None:
        raise ValueError("RENDER_CRENDENTIALS_JSON no está definida en las variables de entorno.")

    stripped = raw.strip()
    if stripped.startswith("{"):
        creds_dict = json.loads(stripped)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(creds_dict, tmp)
        tmp.close()
        creds_path = tmp.name
    else:
        creds_path = stripped

    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    from Config import Global as G
    return storage.Client(credentials=creds, project=creds.project_id)


def descargar_archivos_nic(codigo_necesidad: str, directorio_base: Path = None) -> Path:
    """
    Descarga la ficha técnica y la proforma de un NIC directo en su carpeta,
    sin subcarpetas intermedias.

    Args:
        codigo_necesidad: Ej: "nic-1768013520001-2026-00071"
        directorio_base:  Por defecto ~/Documents/Documentos de Contratacion

    Returns:
        Path de la carpeta local del NIC.

    Raises:
        RuntimeError si no se encontró ningún archivo en el bucket.
    """
    from Config import Global

    if directorio_base is None:
        directorio_base = Path.home() / "Documents" / "Documentos de Contratacion"

    # Carpeta destino: .../Documentos de Contratacion/nic-.../
    carpeta_nic = directorio_base / codigo_necesidad
    carpeta_nic.mkdir(parents=True, exist_ok=True)

    gcs         = _obtener_cliente_gcs()
    bucket      = gcs.bucket(Global.BUCKET_NAME)
    encontrados = 0

    # Buscar en ambas carpetas del bucket
    for prefijo_bucket in ["Fichas Tecnicas", "Proformas"]:
        blobs = list(gcs.list_blobs(bucket, prefix=f"{prefijo_bucket}/"))

        # Filtrar solo los blobs que pertenecen a este NIC
        codigo_limpio = codigo_necesidad.replace("-", "_")
        blobs_nic = [
            b for b in blobs
            if codigo_limpio in b.name or codigo_necesidad in b.name
        ]

        for blob in blobs_nic:
            nombre_archivo = Path(blob.name).name
            destino        = carpeta_nic / nombre_archivo  # directo, sin subcarpetas

            # Descargar solo si no existe o si el tamaño cambió en el bucket
            if not destino.exists() or destino.stat().st_size != blob.size:
                blob.download_to_filename(str(destino))

            encontrados += 1

    if encontrados == 0:
        raise RuntimeError(
            f"No se encontraron archivos en el bucket para:\n{codigo_necesidad}\n\n"
            "Es posible que la IA aún no haya procesado esta ínfima."
        )

    return carpeta_nic