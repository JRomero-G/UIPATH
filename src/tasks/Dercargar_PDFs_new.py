import os
import re
import time
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

import mysql.connector

# =====================================================
# 1. CONFIGURACIÓN GENERAL
# =====================================================
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "",
    "database": "nexus_try"
}

BASE_DOWNLOAD_PATH = r"C:\\Users\\Marissa\\Downloads\\Contratación\\"

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
# 2. UTILITARIAS
# =====================================================
def safe_value(value, default="SIN_VALOR"):
    return default if pd.isna(value) or value is None else str(value).strip()

def obtener_datos_preseleccionados():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT codigo_necesidad, entidad_contratante_url FROM preseleccionados")
        datos = cursor.fetchall()
        cursor.close()
        conn.close()
        df = pd.DataFrame(datos)
        total = len(df)
        if total == 0:
            return None 
        return df
    except Exception:
        return None  

# =====================================================
# 3. CANTIDADES 
# =====================================================
def encontrar_tabla_cantidad(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for tabla in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in tabla.find_all("th")]
        if not headers:
            continue
        headers_str = " | ".join(headers)
        if all(x in headers_str for x in ["no.", "cpc", "descripción", "cantidad"]):
            return tabla, 5
    return None, None

def extraer_y_limpiar_cantidad(celda):
    input_tag = celda.find("input")
    if input_tag and input_tag.get("value"):
        texto = input_tag["value"].strip()
    else:
        texto = celda.get_text(separator=" ", strip=True)
    
    texto_limpio = re.sub(r"[^\d.,]", "", texto)
    if "." in texto_limpio and "," in texto_limpio and len(texto_limpio.split(",")[-1]) <= 2:
        texto_limpio = texto_limpio.replace(".", "").replace(",", ".")
    else:
        texto_limpio = texto_limpio.replace(",", ".")
    
    if not texto_limpio:
        return None
    try:
        return float(texto_limpio)
    except ValueError:
        return None

def obtener_suma_cantidades(html_content):
    tabla, col_index = encontrar_tabla_cantidad(html_content)
    if not tabla:
        return None
    
    suma_total = 0.0
    filas = tabla.find_all("tr")[1:]
    
    for fila in filas:
        celdas = fila.find_all(["td", "th"])
        if len(celdas) <= col_index:
            continue
        
        valor = extraer_y_limpiar_cantidad(celdas[col_index])
        if valor and valor > 0:
            suma_total += valor
    
    if suma_total == 0:
        return None
    elif suma_total > 10:
        return None
    else:
        return suma_total

# =====================================================
# 4. DETECCIÓN DE EXTENSIÓN
# =====================================================
def detectar_extension(url, descripcion="", primeros_bytes=b''):
    path = urlparse(url).path.lower()
    if path.endswith(('.pdf', '.docx', '.xlsx', '.doc', '.xls')):
        return os.path.splitext(path)[1]

    if primeros_bytes:
        if primeros_bytes.startswith(b'%PDF'):
            return '.pdf'
        if primeros_bytes.startswith(b'PK\x03\x04'):
            return '.docx' if b'word/' in primeros_bytes.lower() else '.xlsx'
        if primeros_bytes.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
            return '.doc'

    desc = descripcion.lower()
    if any(p in desc for p in ['forma', 'subir oferta', 'oferta', 'formato', 'anexo']):
        return '.docx'
    if any(p in desc for p in ['presupuesto', 'referencial', 'costo', 'excel']):
        return '.xlsx'
    return '.pdf'

# =====================================================
# 5. DESCARGA ROBUSTA (sin prints excesivos)
# =====================================================
def descargar_archivo(url, ruta_base, descripcion="", max_reintentos=5):
    for intento in range(1, max_reintentos + 1):
        try:
            with session.get(url, stream=True, timeout=TIMEOUT_DESCARGA) as r:
                r.raise_for_status()
                iterator = r.iter_content(chunk_size=32768)
                primeros_bytes = next(iterator, b'')
                
                extension = detectar_extension(url, descripcion, primeros_bytes)
                ruta_final = ruta_base + extension
                temp_final = ruta_final + '.part'

                with open(temp_final, 'wb') as f:
                    if primeros_bytes:
                        f.write(primeros_bytes)
                    for chunk in iterator:
                        if chunk:
                            f.write(chunk)

                if os.path.exists(ruta_final):
                    os.remove(ruta_final)
                os.rename(temp_final, ruta_final)
                return ruta_final

        except Exception:
            if intento < max_reintentos:
                time.sleep(7 * intento)
    
    return None

def obtener_y_descargar_documentos(html_content, base_url, carpeta_destino):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    seccion = soup.find(string=lambda t: t and any(texto in str(t).upper() for texto in [
        "DOCUMENTOS ANEXOS", "ARCHIVO QUE CONTIENE LAS ESPECIFICACIONES", 
        "TÉRMINOS DE REFERENCIA", "ANEXOS", "DOCUMENTOS ADJUNTOS"
    ]))
    
    if not seccion:
        return 0
    
    tabla = seccion.find_next('table')
    if not tabla:
        return 0
    
    descargados = 0
    filas = tabla.find_all('tr')
    
    for fila in filas:
        celdas = fila.find_all('td')
        if len(celdas) < 2:
            continue
        
        descripcion = celdas[0].get_text(strip=True)
        enlace = celdas[1].find('a', href=True)
        if not enlace:
            continue
        
        url_archivo = urljoin(base_url, enlace['href'])
        
        nombre_limpio = re.sub(r'[<>:"/\\|?*]', '_', 
                               "".join(c for c in descripcion if c.isalnum() or c in " _-()")).strip()
        if not nombre_limpio:
            nombre_limpio = f"documento_{descargados + 1}"
        
        ruta_base = os.path.join(carpeta_destino, nombre_limpio)
        
        resultado = descargar_archivo(url_archivo, ruta_base, descripcion)
        if resultado:
            descargados += 1
        
        time.sleep(PAUSA_ENTRE_ARCHIVOS)
    
    return descargados

# =====================================================
# 6. MAIN - LIMPIO PARA UIPATH
# =====================================================
def main():
    df = obtener_datos_preseleccionados()
    if df is None or df.empty:
        return "ERROR: No se pudieron obtener datos o no hay registros."

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

            suma = obtener_suma_cantidades(resp.text)
            if not suma:
                continue

            carpeta = os.path.join(BASE_DOWNLOAD_PATH, codigo)
            os.makedirs(carpeta, exist_ok=True)

            descargados = obtener_y_descargar_documentos(resp.text, url, carpeta)
            archivos_totales += descargados

        except Exception:
            continue
        
        time.sleep(PAUSA_ENTRE_PROCESOS)

    return f"COMPLETADO: {archivos_totales} archivos descargados de {total_procesos} procesos."

if __name__ == "__main__":
    main()