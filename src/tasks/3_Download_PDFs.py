import mysql.connector
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import urljoin, urlparse
import time
from google.cloud import storage

# =====================================================
# 1. CONFIGURACIÓN GENERAL
# =====================================================
MYSQL_CONFIG = {
    "host": "35.225.240.246",
    "user": "root",
    "password": "Admin123%",
    "database": "gestorex",
}

# Carpeta local dentro del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_file_))))
BASE_DOWNLOAD_PATH = os.path.join(BASE_DIR, "data")  # Carpeta temporal de descarga

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "/",
    "Accept-Language": "es-EC,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.compraspublicas.gob.ec/",
}

TIMEOUT_PAGINA = 60
TIMEOUT_DESCARGA = 40

PAUSA_ENTRE_PROCESOS = 4
PAUSA_ENTRE_ARCHIVOS = 1

session = requests.Session()
session.headers.update(HEADERS)

# =====================================================
# 1.1 GOOGLE CLOUD STORAGE (TEMPORAL)
# =====================================================
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    BASE_DIR, "data", "Acceso_bucket_nexus.json"
)
BUCKET_NAME = "nexusbucket1"

storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)


def subir_archivo_a_gcs_temporal(ruta_local, codigo_necesidad):
    try:
        nombre_archivo = os.path.basename(ruta_local)
        blob_path = f"Documentos de Contratación/{codigo_necesidad}/{nombre_archivo}"

        blob = bucket.blob(blob_path)
        blob.upload_from_filename(ruta_local)

        return f"gs://{BUCKET_NAME}/{blob_path}"
    except Exception as e:
        print(f"Error subiendo a GCS: {e}")
        return None


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
            "SELECT codigo_necesidad, entidad_contratante_url FROM infimas WHERE etapa = 'preseleccionada'"
        )
        datos = cursor.fetchall()
        cursor.close()
        conn.close()
        df = pd.DataFrame(datos)
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"Error obteniendo datos: {e}")
        return None


# =====================================================
# 3. CANTIDADES
# =====================================================
def encontrar_tabla_cantidad(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for tabla in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in tabla.find_all("th")]
        if headers and all(
            x in " | ".join(headers) for x in ["no.", "cpc", "descripción", "cantidad"]
        ):
            return tabla, 5
    return None, None


def extraer_y_limpiar_cantidad(celda):
    input_tag = celda.find("input")
    texto = (
        input_tag["value"].strip()
        if input_tag and input_tag.get("value")
        else celda.get_text(strip=True)
    )

    texto = re.sub(r"[^\d.,]", "", texto)
    texto = (
        texto.replace(".", "").replace(",", ".")
        if texto.count(",") == 1
        else texto.replace(",", ".")
    )

    try:
        return float(texto)
    except Exception:
        return None


def obtener_suma_cantidades(html_content, codigo_necesidad):
    tabla, col_index = encontrar_tabla_cantidad(html_content)
    if not tabla:
        return None

    suma = 0.0
    for fila in tabla.find_all("tr")[1:]:
        celdas = fila.find_all(["td", "th"])
        if len(celdas) > col_index:
            valor = extraer_y_limpiar_cantidad(celdas[col_index])
            if valor:
                suma += valor

    # Si la suma es mayor a 10, actualizamos la etapa en la BD
    if suma > 10:
        try:
            conn = mysql.connector.connect(**MYSQL_CONFIG)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE infimas SET etapa = %s WHERE codigo_necesidad = %s",
                ("no seleccionada", codigo_necesidad),
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error actualizando etapa en BD: {e}")
        return "no seleccionada"

    return suma if 0 < suma <= 10 else None


# =====================================================
# 4. DETECCIÓN DE EXTENSIÓN
# =====================================================
def detectar_extension(url, descripcion="", primeros_bytes=b""):
    path = urlparse(url).path.lower()
    if path.endswith((".pdf", ".docx", ".xlsx", ".doc", ".xls")):
        return os.path.splitext(path)[1]

    if primeros_bytes.startswith(b"%PDF"):
        return ".pdf"
    if primeros_bytes.startswith(b"PK"):
        return ".docx"
    if primeros_bytes.startswith(b"\xd0\xcf"):
        return ".doc"

    return ".pdf"


# =====================================================
# 5. DESCARGA
# =====================================================
def descargar_archivo(url, ruta_base, descripcion="", max_reintentos=5):
    for intento in range(max_reintentos):
        try:
            with session.get(url, stream=True, timeout=TIMEOUT_DESCARGA) as r:
                r.raise_for_status()
                it = r.iter_content(32768)
                primeros_bytes = next(it, b"")

                extension = detectar_extension(url, descripcion, primeros_bytes)
                ruta_final = ruta_base + extension
                temp = ruta_final + ".part"

                with open(temp, "wb") as f:
                    f.write(primeros_bytes)
                    for chunk in it:
                        if chunk:
                            f.write(chunk)

                os.replace(temp, ruta_final)
                return ruta_final
        except Exception:
            time.sleep(7 * (intento + 1))
    return None


def obtener_y_descargar_documentos(html, base_url, carpeta_destino):
    soup = BeautifulSoup(html, "html.parser")
    seccion = soup.find(string=lambda t: t and "DOCUMENTOS" in t.upper())
    if not seccion:
        return 0

    tabla = seccion.find_next("table")
    if not tabla:
        return 0

    descargados = 0

    for fila in tabla.find_all("tr"):
        celdas = fila.find_all("td")
        if len(celdas) < 2:
            continue

        descripcion = celdas[0].get_text(strip=True)
        link = celdas[1].find("a", href=True)
        if not link:
            continue

        url_archivo = urljoin(base_url, link["href"])
        nombre = (
            re.sub(r'[<>:"/\\|?*]', "", descripcion) or f"documento{descargados + 1}"
        )
        ruta_base = os.path.join(carpeta_destino, nombre)

        resultado = descargar_archivo(url_archivo, ruta_base, descripcion)
        if resultado:
            # Primero guarda temporalmente en data
            # Luego sube a GCS
            subir_archivo_a_gcs_temporal(resultado, os.path.basename(carpeta_destino))
            # Puedes borrar el archivo local si quieres liberar espacio
            try:
                os.remove(resultado)
            except Exception:
                pass

            descargados += 1

        time.sleep(PAUSA_ENTRE_ARCHIVOS)

    return descargados


# =====================================================
# 6. MAIN
# =====================================================
def main():
    df = obtener_datos_preseleccionados()
    if df is None:
        return "ERROR: sin datos"

    total = 0
    for _, row in df.iterrows():
        codigo = safe_value(row["codigo_necesidad"])
        url = safe_value(row["entidad_contratante_url"])
        if url == "SIN_VALOR":
            continue

        try:
            r = session.get(url, timeout=TIMEOUT_PAGINA)
            if r.status_code != 200:
                continue

            etapa = obtener_suma_cantidades(r.text, codigo)
            if not etapa:
                continue

            carpeta = os.path.join(BASE_DOWNLOAD_PATH, codigo)
            os.makedirs(carpeta, exist_ok=True)

            total += obtener_y_descargar_documentos(r.text, url, carpeta)
        except Exception:
            continue

        time.sleep(PAUSA_ENTRE_PROCESOS)

    return f"COMPLETADO: {total} archivos subidos temporalmente a GCS"


if _name_ == "_main_":
    main()
