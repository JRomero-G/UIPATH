# ===========================================================
# SECCIÓN 1 — IMPORTACIONES BASE (ORIGINALES)
# ===========================================================

import os
from google.cloud import storage
from vertexai.generative_models import GenerativeModel, Part
import vertexai

# Credenciales GCP (SIN CAMBIOS)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
    "src/Credentials/Clave_bucket_AIgemini.json"
)

PROJECT_ID = "moonlit-oven-483902-e4"
LOCATION = "us-central1"
BUCKET_NAME = "nexusbucket1"

vertexai.init(project=PROJECT_ID, location=LOCATION)

model = GenerativeModel("gemini-2.5-flash")

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

MAX_WORKERS = 5
MAX_DOCUMENTS_PER_FOLDER = 20
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
    # ⚠️ MODIFICADO: nuevas credenciales solicitadas
    return mysql.connector.connect(
        host="35.225.240.246", user="root", password="Admin123%", database="gestorex"
    )


# ===========================================================
# SECCIÓN 6 — EXTRACCIÓN DE DATOS BASE
# ===========================================================


def obtener_contraindicaciones(cursor):
    cursor.execute("""
        SELECT contraindicacion, peso
        FROM contraindicaciones
    """)
    filas = cursor.fetchall()

    # Lista separada por comas (uso IA)
    lista_texto = ", ".join([f[0] for f in filas])

    # Diccionario contraindicación → peso
    pesos = {f[0]: float(f[1]) for f in filas}

    return lista_texto, pesos


def obtener_codigos_preseleccionados(cursor):
    # MODIFICADO: solo etapa = preseleccionada
    cursor.execute("""
        SELECT codigo_necesidad
        FROM infimas
        WHERE etapa = 'preseleccionada'
    """)
    return [f[0] for f in cursor.fetchall()]


# ===========================================================
# SECCIÓN 7 — HASH PARA CACHEO
# ===========================================================


def generar_hash_documento(blob_name, tipo):
    return hashlib.sha256(f"{tipo}:{blob_name}".encode("utf-8")).hexdigest()


# ===========================================================
# SECCIÓN 8 — EXTRACCIÓN PAC (FASE 1)
# ===========================================================


def analizar_documento_pac(blob):
    doc_hash = generar_hash_documento(blob.name, "PAC")

    with cache_lock:
        if doc_hash in CACHE_IA:
            return CACHE_IA[doc_hash]

    document_part = Part.from_uri(
        uri=f"gs://{BUCKET_NAME}/{blob.name}", mime_type="application/pdf"
    )

    prompt = """
    Analiza el documento y busca referencias al Plan Anual de Contratación,
    partida presupuestaria o monto total de la necesidad.
    Devuelve exclusivamente un número decimal.
    Si no existe, devuelve 0.
    """

    response = model.generate_content([document_part, prompt])

    try:
        pac = float(response.text.strip())
    except:
        pac = 0.0

    with cache_lock:
        CACHE_IA[doc_hash] = pac

    return pac


# ===========================================================
# SECCIÓN 9 — FUNCIÓN PAC POR CÓDIGO
# ===========================================================


def obtener_pac_codigo(codigo_necesidad):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)

    prefijo = f"Documentos de contratación/{codigo_necesidad}/"
    blobs = [
        b
        for b in bucket.list_blobs(prefix=prefijo)
        if b.name.lower().endswith((".pdf", ".docx", ".txt"))
    ][:MAX_DOCUMENTS_PER_FOLDER]

    pacs = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(analizar_documento_pac, b) for b in blobs]
        for f in as_completed(futures):
            pac = f.result()
            if pac > 0:
                pacs.append(pac)

    return max(pacs) if pacs else 0.0


# ===========================================================
# SECCIÓN 10 — CONTRAINDICACIONES (FASE 2)
# ===========================================================


def analizar_documento_contra(blob, lista_contra):
    doc_hash = generar_hash_documento(blob.name, "CONTRA")

    with cache_lock:
        if doc_hash in CACHE_IA:
            return CACHE_IA[doc_hash]

    document_part = Part.from_uri(
        uri=f"gs://{BUCKET_NAME}/{blob.name}", mime_type="application/pdf"
    )

    prompt = f"""
    Revisa el documento y detecta si contiene alguna de las siguientes
    palabras o frases (contraindicaciones):
    {lista_contra}
    Devuelve solo las encontradas separadas por coma.
    """

    response = model.generate_content([document_part, prompt])

    encontrados = [x.strip() for x in response.text.split(",") if x.strip()]

    with cache_lock:
        CACHE_IA[doc_hash] = encontrados

    return encontrados


def obtener_contraindicaciones_codigo(codigo_necesidad, lista_contra):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)

    prefijo = f"Documentos de contratación/{codigo_necesidad}/"
    blobs = [
        b
        for b in bucket.list_blobs(prefix=prefijo)
        if b.name.lower().endswith((".pdf", ".docx", ".txt"))
    ][:MAX_DOCUMENTS_PER_FOLDER]

    encontradas = set()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(analizar_documento_contra, b, lista_contra) for b in blobs
        ]
        for f in as_completed(futures):
            encontradas.update(f.result())

    return list(encontradas)


# ===========================================================
# SECCIÓN 11 — CÁLCULO DEL PESO
# ===========================================================


def calcular_peso(contras, pesos):
    valores = [pesos[c] for c in contras if c in pesos]
    if not valores:
        return 0.0
    producto = reduce(lambda a, p: a * (1 - p), valores, 1)
    return round(1 - producto, 6)


# ===========================================================
# SECCIÓN 12 — ACTUALIZACIONES BD
# ===========================================================


def actualizar_pac(cursor, conexion, codigo, pac):
    cursor.execute(
        """
        UPDATE infimas
        SET PAC = %s
        WHERE codigo_necesidad = %s
    """,
        (pac, codigo),
    )
    conexion.commit()


def insertar_evaluacion(cursor, conexion, codigo, peso, justificacion):
    cursor.execute(
        """
        INSERT INTO evaluaciones (codigo_necesidad, peso, justificacion)
        VALUES (%s, %s, %s)
    """,
        (codigo, peso, justificacion),
    )
    conexion.commit()


def actualizar_etapa_por_pac(cursor, conexion, codigo_necesidad, pac):
    """
    Actualiza la columna 'etapa' en la tabla infimas según el valor del PAC.
    - PAC > 0  -> 'seleccionada'
    - PAC = 0  -> 'no seleccionada'
    """

    etapa = "seleccionada" if pac > 0 else "no seleccionada"

    cursor.execute(
        """
        UPDATE infimas
        SET etapa = %s
        WHERE codigo_necesidad = %s
    """,
        (etapa, codigo_necesidad),
    )

    conexion.commit()


# ===========================================================
# SECCIÓN 13 — FLUJO PRINCIPAL
# ===========================================================


def main():
    conexion = conectar_base_datos()
    cursor = conexion.cursor()

    lista_contra, pesos = obtener_contraindicaciones(cursor)
    codigos = obtener_codigos_preseleccionados(cursor)

    # FASE 1 — PAC
    pac_por_codigo = {}
    for codigo in codigos:
        pac = obtener_pac_codigo(codigo)
        pac_por_codigo[codigo] = pac
        actualizar_pac(cursor, conexion, codigo, pac)
        actualizar_etapa_por_pac(cursor, conexion, codigo, pac)

    # FASE 2 — CONTRAINDICACIONES + PESO
    for codigo, pac in pac_por_codigo.items():
        if pac > 0:
            contras = obtener_contraindicaciones_codigo(codigo, lista_contra)
            peso = calcular_peso(contras, pesos)
            justificacion = ", ".join(contras)
            insertar_evaluacion(cursor, conexion, codigo, peso, justificacion)

    guardar_cache(CACHE_IA)
    cursor.close()
    conexion.close()


# ===========================================================
# PUNTO DE ENTRADA
# ===========================================================

if __name__ == "__main__":
    main()
