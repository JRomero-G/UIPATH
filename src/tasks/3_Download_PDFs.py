import os
import time
import re
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from google.cloud import storage
import mysql.connector

# =====================================================
# 1. CONFIGURACIÓN
# =====================================================
MYSQL_CONFIG = {
    "host": "35.225.240.246",
    "user": "root",
    "password": "Admin123%",
    "database": "gestorex",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-EC,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.compraspublicas.gob.ec/",
}

TIMEOUT_PAGINA = 60
TIMEOUT_DESCARGA = 120  # aumentar timeout para archivos grandes
PAUSA_ENTRE_PROCESOS = 4
PAUSA_ENTRE_ARCHIVOS = 1

# Google Cloud - siempre en base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    BASE_DIR, "data", "moonlit-oven-483902-e4-c3e17a7fda32.json"
)
BUCKET_NAME = "nexusbucket1"

session = requests.Session()
session.headers.update(HEADERS)


# =====================================================
# 2. UTILITARIAS
# =====================================================
def safe_value(value, default="SIN_VALOR"):
    return default if pd.isna(value) or value is None else str(value).strip()


def obtener_datos_preseleccionados():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT codigo_necesidad, entidad_contratante_url FROM infimas where etapa = 'preseleccionada'"
        )
        datos = cursor.fetchall()
        cursor.close()
        conn.close()
        df = pd.DataFrame(datos)
        return df if not df.empty else None
    except Exception as e:
        print(f"[ERROR DB] {e}")
        return None


# =====================================================
# 3. DETECCIÓN DE EXTENSIÓN
# =====================================================
def detectar_extension(url, descripcion="", primeros_bytes=b""):
    # Forzar .pdf para archivos .cpe de Compras Públicas
    if "ExeGENBajarArchivoGeneral.cpe" in url:
        return ".pdf"

    path = urlparse(url).path.lower()
    if path.endswith((".pdf", ".docx", ".xlsx", ".doc", ".xls")):
        return os.path.splitext(path)[1]

    if primeros_bytes:
        if primeros_bytes.startswith(b"%PDF"):
            return ".pdf"
        if primeros_bytes.startswith(b"PK\x03\x04"):
            return ".docx" if b"word/" in primeros_bytes.lower() else ".xlsx"
        if primeros_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            return ".doc"

    desc = descripcion.lower()
    if any(p in desc for p in ["forma", "subir oferta", "oferta", "formato", "anexo"]):
        return ".docx"
    if any(p in desc for p in ["presupuesto", "referencial", "costo", "excel"]):
        return ".xlsx"
    return ".pdf"


# =====================================================
# 4. SUBIDA A BUCKET
# =====================================================
def subir_a_bucket(bucket_name, archivo_local, ruta_destino):
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(ruta_destino)
        blob.upload_from_filename(archivo_local)
        return True
    except Exception as e:
        print(f"[ERROR SUBIDA] {archivo_local}: {e}")
        return False


# =====================================================
# 5. DESCARGA Y SUBIDA DIRECTA
# =====================================================
def descargar_y_subir_archivo(url, codigo, nombre_original, descripcion=""):
    """Descarga el archivo y lo sube al bucket manteniendo nombre y extensión correcta"""
    try:
        for intento in range(1, 6):
            try:
                with session.get(url, stream=True, timeout=TIMEOUT_DESCARGA) as r:
                    r.raise_for_status()

                    # Detectar extensión real
                    primeros_bytes = next(r.iter_content(chunk_size=32768), b"")
                    extension = detectar_extension(url, descripcion, primeros_bytes)

                    # Limpiar nombre
                    nombre_limpio = re.sub(
                        r'[<>:"/\\|?*]', "_", nombre_original
                    ).strip()
                    if not nombre_limpio:
                        nombre_limpio = "documento"

                    temp_file = f"{nombre_limpio}{extension}.part"
                    final_file = f"{nombre_limpio}{extension}"

                    # Guardar temporal
                    with open(temp_file, "wb") as f:
                        if primeros_bytes:
                            f.write(primeros_bytes)
                        for chunk in r.iter_content(chunk_size=32768):
                            if chunk:
                                f.write(chunk)

                    # Renombrar
                    if os.path.exists(final_file):
                        os.remove(final_file)
                    os.rename(temp_file, final_file)

                    # Subir al bucket
                    ruta_bucket = f"Documentos de contratación/{codigo}/{final_file}"
                    subir_a_bucket(BUCKET_NAME, final_file, ruta_bucket)

                    os.remove(final_file)
                    return ruta_bucket

            except Exception as e:
                print(f"[WARNING] Intento {intento} descarga {url}: {e}")
                time.sleep(5 * intento)

        print(f"[ERROR] No se pudo descargar: {url}")
        return None

    except Exception as e:
        print(f"[ERROR] General descarga: {url}: {e}")
        return None


# =====================================================
# 5B. OBTENER Y SUBIR TODOS LOS DOCUMENTOS
# =====================================================
def obtener_y_subir_todos_documentos(html_content, base_url, codigo):
    """
    Recorre todas las secciones de documentos y sube todos los archivos
    al bucket manteniendo el nombre original y extensión correcta.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    subidos = 0

    secciones = soup.find_all(
        string=lambda t: t
        and any(
            texto in str(t).upper()
            for texto in [
                "DOCUMENTOS ANEXOS",
                "ARCHIVO QUE CONTIENE LAS ESPECIFICACIONES",
                "TÉRMINOS DE REFERENCIA",
                "ANEXOS",
                "DOCUMENTOS ADJUNTOS",
            ]
        )
    )

    for seccion in secciones:
        tabla = seccion.find_next("table")
        if not tabla:
            continue

        filas = tabla.find_all("tr")
        for fila in filas:
            celdas = fila.find_all("td")
            if not celdas:
                continue

            # Buscar enlaces en cualquier celda
            enlaces = []
            for celda in celdas:
                enlaces.extend(celda.find_all("a", href=True))

            for enlace in enlaces:
                url_archivo = urljoin(base_url, enlace["href"])
                nombre_original = os.path.basename(urlparse(enlace["href"]).path)
                if nombre_original.lower().endswith(".cpe"):
                    nombre_original = nombre_original + ".pdf"

                resultado = descargar_y_subir_archivo(
                    url_archivo, codigo, nombre_original
                )
                if resultado:
                    subidos += 1

                time.sleep(PAUSA_ENTRE_ARCHIVOS)

    return subidos


# =====================================================
# 6. MAIN
# =====================================================
def main():
    df = obtener_datos_preseleccionados()
    if df is None or df.empty:
        print("ERROR: No se pudieron obtener datos o no hay registros.")
        return

    total_procesos = len(df)
    archivos_totales = 0

    for index, row in df.iterrows():
        codigo = safe_value(row["codigo_necesidad"])
        url = safe_value(row["entidad_contratante_url"])

        if url == "SIN_VALOR":
            continue

        try:
            resp = session.get(url, timeout=TIMEOUT_PAGINA)
            if resp.status_code != 200:
                continue

            # Subimos todos los documentos del código
            subidos = obtener_y_subir_todos_documentos(resp.text, url, codigo)
            archivos_totales += subidos

        except Exception as e:
            print(f"[ERROR PROCESO {codigo}] {e}")
            continue

        time.sleep(PAUSA_ENTRE_PROCESOS)

    print(
        f"COMPLETADO: {archivos_totales} archivos subidos de {total_procesos} procesos."
    )


if __name__ == "__main__":
    main()
