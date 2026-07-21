import mysql.connector
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import urljoin, urlparse
import time
import shutil
from google.cloud import storage
import sys
from pathlib import Path
import tempfile

#raíz del proyecto al path de Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from Config import Global

# =====================================================
# 1. CONFIGURACIÓN GENERAL
# =====================================================
MYSQL_CONFIG = {
    "host": Global.DB_HOST,
    "user": Global.DB_USER,
    "password": Global.DB_PASSWORD,
    "database": Global.DATABASE,
    "use_pure": True,              # ← Usa implementación Python pura
    "connect_timeout": 30,         # ← Timeout de conexión
    "connection_timeout": 60, 
}

# Ruta base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carpeta temporal dentro del proyecto
BASE_DOWNLOAD_PATH = os.path.join(BASE_DIR, "data")
os.makedirs(BASE_DOWNLOAD_PATH, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
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
# 1.1 GOOGLE CLOUD STORAGE
# =====================================================
def obtener_ruta_credenciales():
    """
    Retorna (ruta, es_temporal).
    El llamador debe hacer os.remove(ruta) si es_temporal=True.
    """
    credentials_json = Global.RENDER_CRENDENTIALS_JSON
    if credentials_json:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".json", mode="w"
        ) as temp:
            temp.write(credentials_json)
            return temp.name, True  # ← flag para limpieza

    if Global.GEMINI_CREDENTIALS:
        return Global.GEMINI_CREDENTIALS, False

    raise Exception("No se encontraron credenciales")



#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
#    BASE_DIR, "data", "Clave_bucket_AIgemini.json"
#)

BUCKET_NAME = Global.BUCKET_NAME
storage_client = None
bucket = None


def subir_archivo_a_gcs_temporal(ruta_local, codigo_necesidad):
    try:
        nombre_archivo = os.path.basename(ruta_local)
        blob_path = f"Documentos de Contratación/{codigo_necesidad}/{nombre_archivo}"

        blob = bucket.blob(blob_path)
        blob.upload_from_filename(ruta_local)

        print(f"    [GCS] Subido: {nombre_archivo}")
        return f"gs://{BUCKET_NAME}/{blob_path}"

    except Exception as e:
        print(f"    [GCS] Error: {e}")
        return None


def verificar_carpeta_existe_en_gcs(codigo_necesidad):
    """
    Verifica si ya existe una carpeta (con archivos) en GCS para el código de necesidad.
    
    Args:
        codigo_necesidad (str): Código de necesidad a verificar
        
    Returns:
        bool: True si existe carpeta con archivos, False si no existe
    """
    try:
        # Prefijo de la carpeta en GCS
        prefijo = f"Documentos de Contratación/{codigo_necesidad}/"
        
        # Listar blobs con ese prefijo (limit=1 es suficiente para verificar existencia)
        blobs = list(bucket.list_blobs(prefix=prefijo, max_results=1))
        
        # Si hay al menos un blob, la carpeta existe
        return len(blobs) > 0
        
    except Exception as e:
        print(f"    [GCS] Error al verificar carpeta: {e}")
        # En caso de error, devolver False para intentar la descarga
        return False


# =====================================================
# 2. UTILITARIAS
# =====================================================
def safe_value(value, default="SIN_VALOR"):
    return default if pd.isna(value) or value is None else str(value).strip()


def obtener_datos_preseleccionados():
    """Obtiene ínfimas en etapa 'preseleccionada'"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT codigo_necesidad, entidad_contratante_url "
            "FROM infimas WHERE etapa = 'preseleccionada' "
            "ORDER BY codigo_necesidad"
        )

        datos = cursor.fetchall()
        cursor.close()
        conn.close()

        df = pd.DataFrame(datos)
        return None if df.empty else df

    except Exception as e:
        print(f"[ERROR] BD: {e}")
        return None


def obtener_datos_seleccionados():
    """Obtiene ínfimas en etapa 'seleccionada' con PACdoc en NULL (sin análisis de PAC)"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT codigo_necesidad, entidad_contratante_url "
            "FROM infimas WHERE etapa = 'seleccionada' "
            "AND entidad_contratante_url IS NOT NULL "
            "AND entidad_contratante_url != ''"
            "AND PACdoc IS NULL" 
        )

        datos = cursor.fetchall()
        cursor.close()
        conn.close()

        df = pd.DataFrame(datos)
        return None if df.empty else df

    except Exception as e:
        print(f"[ERROR] BD: {e}")
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


def obtener_suma_cantidades(html_content):
    """
    Retorna la suma de cantidades o None si no hay tabla.
    MODIFICADO: Solo retorna el valor, no actualiza la BD.
    """
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

    return suma if suma > 0 else None


def extraer_cpc(html_content):
    """
    Extrae el código CPC de la tabla de artículos.
    El CPC se ubica en la segunda columna (índice 1), inmediatamente
    después del número de artículo "No." (índice 0). Es idéntico para
    todos los artículos de la necesidad, por lo que se toma el de la
    primera fila de datos.
    Se retorna como cadena de dígitos (no como entero) para preservar
    posibles ceros iniciales, ya que la columna CPC es VARCHAR.
    Retorna None si no se encuentra.
    """
    tabla, _ = encontrar_tabla_cantidad(html_content)
    if not tabla:
        return None

    for fila in tabla.find_all("tr")[1:]:
        celdas = fila.find_all(["td", "th"])
        if len(celdas) < 2:
            continue
        # Segunda columna = CPC (serie de dígitos consecutivos, 9-10 dígitos)
        texto = celdas[1].get_text(strip=True)
        match = re.search(r"\d{9,}", texto)
        if match:
            return match.group()
    return None


def actualizar_etapa(codigo_necesidad, nueva_etapa):
    """
    Actualiza la etapa de una ínfima en la base de datos.
    NUEVA FUNCIÓN para manejo centralizado de actualizaciones.
    """
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE infimas SET etapa = %s WHERE codigo_necesidad = %s",
            (nueva_etapa, codigo_necesidad),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"    [DB] Error actualizando etapa: {e}")
        return False


def actualizar_cpc(codigo_necesidad, cpc):
    """
    Guarda el código CPC (cadena de dígitos) de una ínfima en la columna
    CPC (VARCHAR) de la tabla infimas.
    """
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE infimas SET CPC = %s WHERE codigo_necesidad = %s",
            (cpc, codigo_necesidad),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"    [DB] Error actualizando CPC: {e}")
        return False


# =====================================================
# 4. EXTENSIÓN
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
            re.sub(r'[<>:"/\\|?*]', "_", descripcion) or f"documento_{descargados + 1}"
        )
        ruta_base = os.path.join(carpeta_destino, nombre)

        resultado = descargar_archivo(url_archivo, ruta_base, descripcion)
        if resultado and os.path.exists(resultado):
            subir_archivo_a_gcs_temporal(resultado, os.path.basename(carpeta_destino))
            descargados += 1

        time.sleep(PAUSA_ENTRE_ARCHIVOS)

    return descargados


# =====================================================
# 6. LIMPIEZA
# =====================================================
def eliminar_carpeta_temporal(carpeta):
    try:
        if os.path.exists(carpeta):
            shutil.rmtree(carpeta)
            print(f"    [CLEAN] Carpeta temporal eliminada")
    except Exception as e:
        print(f"    [CLEAN] Error: {e}")

# =====================================================
# 7. FASE 1: CLASIFICACIÓN
# =====================================================
def fase_clasificacion():
    """
    FASE 1: Clasificar ínfimas preseleccionadas según cantidad de artículos
    - Cantidad <= 10 → etapa = 'seleccionada'
    - Cantidad > 10  → etapa = 'no seleccionada'
    """
    print("\n" + "="*70)
    print(" "*20 + "FASE 1: CLASIFICACIÓN")
    print("="*70)
    
    df = obtener_datos_preseleccionados()
    if df is None:
        print("[INFO] No hay ínfimas preseleccionadas para clasificar\n")
        return 0, 0
    
    print(f"[INFO] {len(df)} ínfimas preseleccionadas encontradas\n")
    
    seleccionadas = 0
    no_seleccionadas = 0
    sin_datos = 0
    
    for idx, row in df.iterrows():
        codigo = safe_value(row["codigo_necesidad"])
        url = safe_value(row["entidad_contratante_url"])
        
        print(f"[{idx + 1}/{len(df)}] {codigo}")
        
        if url == "SIN_VALOR":
            print(f"  ⚠ URL faltante - OMITIDO")
            sin_datos += 1
            continue
        
        try:
            # Obtener página web
            r = session.get(url, timeout=TIMEOUT_PAGINA)
            if r.status_code != 200:
                print(f"  ✗ Error HTTP {r.status_code}")
                sin_datos += 1
                continue
            
            # Extraer suma de cantidades
            suma = obtener_suma_cantidades(r.text)

            # Extraer y guardar CPC (idéntico para todos los artículos)
            cpc = extraer_cpc(r.text)
            if cpc is not None and actualizar_cpc(codigo, cpc):
                print(f"  ⓘ CPC: {cpc}")

            if suma is None:
                print(f"  ⚠ Sin tabla de cantidades - OMITIDO")
                sin_datos += 1
            elif suma > 10:
                # Cantidad mayor a 10 → NO SELECCIONADA
                if actualizar_etapa(codigo, "no seleccionada"):
                    print(f"  ✗ Cantidad: {suma:.2f} > 10 → NO SELECCIONADA")
                    no_seleccionadas += 1
                else:
                    sin_datos += 1
            else:
                # Cantidad <= 10 → SELECCIONADA
                if actualizar_etapa(codigo, "seleccionada"):
                    print(f"  ✓ Cantidad: {suma:.2f} ≤ 10 → SELECCIONADA")
                    seleccionadas += 1
                else:
                    sin_datos += 1
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
            sin_datos += 1
        
        time.sleep(PAUSA_ENTRE_PROCESOS)
    
    # Resumen Fase 1
    print(f"\n{'='*70}")
    print(" "*22 + "RESUMEN FASE 1")
    print(f"{'='*70}")
    print(f"Total procesadas:      {len(df)}")
    print(f"Seleccionadas:         {seleccionadas}")
    print(f"No seleccionadas:      {no_seleccionadas}")
    print(f"Sin datos/errores:     {sin_datos}")
    print(f"{'='*70}\n")
    
    return seleccionadas, no_seleccionadas


# =====================================================
# 8. FASE 2: DESCARGA
# =====================================================
def fase_descarga():
    """
    FASE 2: Descargar documentos SOLO de ínfimas en etapa 'seleccionada' con PACdoc en NULL
    """
    print("\n" + "="*70)
    print(" "*18 + "FASE 2: DESCARGA DE DOCUMENTOS")
    print("="*70)
    
    df = obtener_datos_seleccionados()
    if df is None:
        print("[INFO] No hay ínfimas seleccionadas para descargar\n")
        return 0
    
    print(f"[INFO] {len(df)} ínfimas seleccionadas para descargar\n")
    
    total_archivos = 0
    exitosas = 0
    fallidas = 0
    
    for idx, row in df.iterrows():
        codigo = safe_value(row["codigo_necesidad"])
        url = safe_value(row["entidad_contratante_url"])
        
        print(f"[{idx + 1}/{len(df)}] {codigo}")
        
        # Verificar si ya existe carpeta en GCS (evitar duplicados)
        if verificar_carpeta_existe_en_gcs(codigo):
            print(f"  ⚠ Carpeta ya existe en GCS - OMITIDO (evitando duplicados)")
            continue
        
        try:
            # Obtener página web
            r = session.get(url, timeout=TIMEOUT_PAGINA)
            if r.status_code != 200:
                print(f"  ✗ Error HTTP {r.status_code}")
                fallidas += 1
                continue
            
            # Crear carpeta temporal
            carpeta = os.path.join(BASE_DOWNLOAD_PATH, codigo)
            os.makedirs(carpeta, exist_ok=True)
            
            # Descargar documentos
            descargados = obtener_y_descargar_documentos(r.text, url, carpeta)
            total_archivos += descargados
            
            if descargados > 0:
                print(f"  ✓ {descargados} documento(s) procesado(s)")
                exitosas += 1
            else:
                print(f"  ⚠ No se encontraron documentos")
                fallidas += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            fallidas += 1
        finally:
            eliminar_carpeta_temporal(carpeta)  
        
        time.sleep(PAUSA_ENTRE_PROCESOS)
    
    # Resumen Fase 2
    print(f"\n{'='*70}")
    print(" "*22 + "RESUMEN FASE 2")
    print(f"{'='*70}")
    print(f"Total procesadas:      {len(df)}")
    print(f"Exitosas:              {exitosas}")
    print(f"Fallidas:              {fallidas}")
    print(f"Archivos descargados:  {total_archivos}")
    print(f"{'='*70}\n")
    
    return total_archivos


# =====================================================
# 9. MAIN
# =====================================================
def main():
    """
    Orquestador principal:
    1. Clasifica TODAS las preseleccionadas (FASE 1)
    2. Descarga documentos SOLO de las seleccionadas (FASE 2)
    """

    global storage_client, bucket

    print("\n" + "="*70)
    print(" "*15 + "SISTEMA DE GESTIÓN DE ÍNFIMAS")
    print(" "*12 + "Clasificación y Descarga de Documentos")
    print("="*70)

    # Inicializar GCS aquí, de forma controlada
    print("[INIT] Conectando a Google Cloud Storage...")
    ruta_creds, es_temp = obtener_ruta_credenciales()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ruta_creds
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    print("[INIT] ✓ GCS conectado")

    inicio_total = time.time()
    
    # ============================================================
    # FASE 1: CLASIFICAR TODAS LAS PRESELECCIONADAS
    # ============================================================
    seleccionadas, no_seleccionadas = fase_clasificacion()
    
    # ============================================================
    # FASE 2: DESCARGAR SOLO LAS SELECCIONADAS
    # ============================================================
    # NOTA: La FASE 2 se ejecuta SIEMPRE porque puede haber ínfimas
    # ya seleccionadas de ejecuciones anteriores (no solo las de FASE 1 actual)
    total_archivos = fase_descarga()
    
    # ============================================================
    # REPORTE FINAL
    # ============================================================
    duracion_total = (time.time() - inicio_total) / 60
    
    print("="*70)
    print(" "*22 + "PROCESO COMPLETADO")
    print("="*70)
    print(f"Ínfimas seleccionadas:      {seleccionadas}")
    print(f"Ínfimas no seleccionadas:   {no_seleccionadas}")
    print(f"Archivos descargados:       {total_archivos}")
    print(f"Tiempo total ejecución:     {duracion_total:.2f} minutos")
    print("="*70 + "\n")

    if es_temp:
        try:
            os.remove(ruta_creds)
        except Exception:
            pass


if __name__ == "__main__":
    main()