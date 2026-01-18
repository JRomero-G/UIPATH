# ===========================================================
# SECCIÓN 1 — IMPORTACIONES BASE (ORIGINALES)
# ===========================================================

import os
from google.cloud import storage
from vertexai.generative_models import GenerativeModel, Part
import vertexai

# Credenciales GCP
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "src/Credentials/Clave_bucket_AIgemini.json"

PROJECT_ID = "moonlit-oven-483902-e4"
LOCATION = "us-central1"
BUCKET_NAME = "nexusbucket1"

vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-1.5-flash")

# ===========================================================
# SECCIÓN 2 — IMPORTACIONES ADICIONALES
# ===========================================================

import mysql.connector
from mysql.connector import Error
from functools import reduce
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import threading

# ===========================================================
# SECCIÓN 3 — PARÁMETROS DE CONTROL (COSTOS / RENDIMIENTO)
# ===========================================================

MAX_WORKERS = 5               # Paralelización controlada (evita sobrecostos)
MAX_DOCUMENTS_PER_FOLDER = 20 # Límite duro de documentos por código
CACHE_FILE = "cache_resultados_ia.json"

cache_lock = threading.Lock()

# ===========================================================
# SECCIÓN 4 — CACHE LOCAL DE RESULTADOS IA
# ===========================================================

def cargar_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

CACHE_IA = cargar_cache()

# ===========================================================
# SECCIÓN 5 — CONEXIÓN A BASE DE DATOS
# ===========================================================

def conectar_base_datos():
    return mysql.connector.connect(
        host="35.225.240.246",
        user="root",
        password="Admin123%",
        database="gestorex"
    )

# ===========================================================
# SECCIÓN 6 — EXTRACCIÓN DE DATOS
# ===========================================================

def obtener_contraindicaciones(cursor):
    cursor.execute("""
        SELECT contraindicacion, peso
        FROM contraindicaciones
    """)
    filas = cursor.fetchall()

    lista_texto = ", ".join([f[0] for f in filas])
    pesos = {f[0]: float(f[1]) for f in filas}

    return lista_texto, pesos

def obtener_codigos_infimas(cursor):
    cursor.execute("""
        SELECT codigo_necesidad, PAC
        FROM infimas
        WHERE PAC > 0
    """)
    return cursor.fetchall()

# ===========================================================
# SECCIÓN 7 — HASH PARA CACHEO POR DOCUMENTO
# ===========================================================

def generar_hash_documento(blob_name):
    """
    Permite identificar un documento de forma única en cache.
    """
    return hashlib.sha256(blob_name.encode("utf-8")).hexdigest()

# ===========================================================
# SECCIÓN 8 — ANÁLISIS DE UN DOCUMENTO (UNIDAD PARALELIZABLE)
# ===========================================================

def analizar_documento(blob, lista_contraindicaciones):
    """
    Analiza un documento individual usando IA, con cacheo.
    """
    doc_hash = generar_hash_documento(blob.name)

    with cache_lock:
        if doc_hash in CACHE_IA:
            return CACHE_IA[doc_hash]

    document_part = Part.from_uri(
        uri=f"gs://{BUCKET_NAME}/{blob.name}",
        mime_type="application/pdf"
    )

    prompt = f"""
    Revisa el documento y detecta si contiene alguna de las siguientes
    palabras o frases (contraindicaciones):

    {lista_contraindicaciones}

    Devuelve únicamente las contraindicaciones encontradas,
    separadas por coma, o vacío si no hay ninguna.
    """

    response = model.generate_content([document_part, prompt])

    encontrados = []
    if response.text:
        encontrados = [x.strip() for x in response.text.split(",") if x.strip()]

    with cache_lock:
        CACHE_IA[doc_hash] = encontrados

    return encontrados

# ===========================================================
# SECCIÓN 9 — ANÁLISIS POR CÓDIGO DE CONTRATACIÓN (PARALELO)
# ===========================================================

def analizar_codigo_necesidad(codigo_necesidad, lista_contraindicaciones):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)

    prefijo = f"Documentos de contratación/{codigo_necesidad}/"
    blobs = [
        b for b in bucket.list_blobs(prefix=prefijo)
        if b.name.lower().endswith((".pdf", ".docx", ".txt"))
    ][:MAX_DOCUMENTS_PER_FOLDER]

    contra_encontradas = set()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(analizar_documento, blob, lista_contraindicaciones)
            for blob in blobs
        ]

        for future in as_completed(futures):
            resultado = future.result()
            contra_encontradas.update(resultado)

    return list(contra_encontradas)

# ===========================================================
# SECCIÓN 10 — CÁLCULO DEL PESO FINAL
# ===========================================================

def calcular_peso(contra_encontradas, pesos_individuales):
    valores = [
        pesos_individuales[c]
        for c in contra_encontradas
        if c in pesos_individuales
    ]

    if not valores:
        return 0.0

    producto = reduce(lambda acc, p: acc * (1 - p), valores, 1)
    return round(1 - producto, 6)

# ===========================================================
# SECCIÓN 11 — ACTUALIZACIÓN EN BASE DE DATOS
# ===========================================================

def actualizar_peso(cursor, conexion, codigo_necesidad, peso):
    cursor.execute("""
        UPDATE infimas
        SET peso = %s
        WHERE codigo_necesidad = %s
    """, (peso, codigo_necesidad))
    conexion.commit()

# ===========================================================
# SECCIÓN 12 — FLUJO PRINCIPAL
# ===========================================================

def main():
    conexion = conectar_base_datos()
    cursor = conexion.cursor()

    lista_contra, pesos_contra = obtener_contraindicaciones(cursor)
    codigos = obtener_codigos_infimas(cursor)

    for codigo_necesidad, pac in codigos:
        print(f"Procesando código: {codigo_necesidad}")

        contra_encontradas = analizar_codigo_necesidad(
            codigo_necesidad,
            lista_contra
        )

        peso_final = calcular_peso(contra_encontradas, pesos_contra)

        actualizar_peso(
            cursor,
            conexion,
            codigo_necesidad,
            peso_final
        )

        print(f"Peso calculado: {peso_final}\n")

    guardar_cache(CACHE_IA)

    cursor.close()
    conexion.close()

# ===========================================================
# PUNTO DE ENTRADA
# ===========================================================

if __name__ == "__main__":
    main()
