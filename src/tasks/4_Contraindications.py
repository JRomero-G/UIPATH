# ===========================================================
# SECCIÓN 1 — CÓDIGO ORIGINAL (HASTA LÍNEA 16)
# ===========================================================

import os
from google.cloud import storage
from vertexai.generative_models import GenerativeModel, Part
import vertexai

# CONFIGURACIÓN DE CREDENCIALES
# MODIFICACIÓN: se mantiene la línea original, solo se normaliza la barra para evitar errores en Windows
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "src/Credentials/Acceso_bucket_nexus.json"

PROJECT_ID = "moonlit-oven-483902-e4"
LOCATION = "us-central1"
BUCKET_NAME = "nexusbucket1"

# Inicialización de Vertex AI (sin cambios funcionales)
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-1.5-flash")

# ===========================================================
# SECCIÓN 2 — NUEVAS IMPORTACIONES (DESDE LÍNEA 18)
# ===========================================================

import mysql.connector
from mysql.connector import Error
from functools import reduce

# ===========================================================
# SECCIÓN 3 — CONEXIÓN A BASE DE DATOS
# ===========================================================

def conectar_base_datos():
    """
    Establece conexión con la base de datos MySQL gestorex.
    """
    return mysql.connector.connect(
        host="35.225.240.246",
        user="root",
        password="Nexus012026%",
        database="gestorex"
    )

# ===========================================================
# SECCIÓN 4 — EXTRACCIÓN DE DATOS DESDE LA BASE
# ===========================================================

def obtener_contraindicaciones(cursor):
    """
    1) Lista de palabras/frases separadas por coma
    2) Diccionario de contraindicaciones con su peso
    """
    cursor.execute("""
        SELECT contraindicacion, peso
        FROM contraindicaciones
    """)
    resultados = cursor.fetchall()

    lista_texto = ", ".join([fila[0] for fila in resultados])
    diccionario_pesos = {fila[0]: float(fila[1]) for fila in resultados}

    return lista_texto, diccionario_pesos


def obtener_codigos_infimas(cursor):
    """
    3) Obtiene códigos de contratación con PAC > 0
    """
    cursor.execute("""
        SELECT codigo_necesidad, PAC
        FROM infimas
        WHERE PAC > 0
    """)
    return cursor.fetchall()

# ===========================================================
# SECCIÓN 5 — VARIABLE PARA RESULTADOS DE IA
# ===========================================================

Contraindicaciones_encontradas = {}

# ===========================================================
# SECCIÓN 6 — FUNCIÓN DE ANÁLISIS CON IA EN EL BUCKET
# ===========================================================

def analizar_documentos_codigo(codigo_necesidad, lista_contraindicaciones):
    """
    Accede a:
    gs://bucket/Documentos de contratación/{codigo_necesidad}/
    y analiza todos los documentos con Gemini.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)

    prefijo = f"Documentos de contratación/{codigo_necesidad}/"
    blobs = bucket.list_blobs(prefix=prefijo)

    contraindicaciones_detectadas = set()

    for blob in blobs:
        if blob.name.lower().endswith((".pdf", ".docx", ".txt")):

            document_part = Part.from_uri(
                uri=f"gs://{BUCKET_NAME}/{blob.name}",
                mime_type="application/pdf"
            )

            prompt = f"""
            Analiza el documento y detecta si contiene alguna de las siguientes
            palabras o frases (contraindicaciones):

            {lista_contraindicaciones}

            Devuelve únicamente las contraindicaciones encontradas,
            separadas por coma.
            """

            response = model.generate_content([document_part, prompt])

            if response.text:
                encontrados = [x.strip() for x in response.text.split(",")]
                contraindicaciones_detectadas.update(encontrados)

    return list(contraindicaciones_detectadas)

# ===========================================================
# SECCIÓN 7 — CÁLCULO MATEMÁTICO DEL PESO
# ===========================================================

def calcular_peso(contra_encontradas, pesos_individuales):
    """
    Peso = 1 - Π(1 - P(i))
    """
    valores = [
        pesos_individuales[c]
        for c in contra_encontradas
        if c in pesos_individuales
    ]

    if not valores:
        return 0.0

    producto = reduce(lambda x, y: x * (1 - y), valores, 1)
    return round(1 - producto, 6)

# ===========================================================
# SECCIÓN 8 — ACTUALIZACIÓN EN BASE DE DATOS
# ===========================================================

def actualizar_peso(cursor, conexion, codigo_necesidad, peso):
    """
    Actualiza la columna Peso en la tabla infimas.
    """
    cursor.execute("""
        UPDATE infimas
        SET Peso = %s
        WHERE codigo_necesidad = %s
    """, (peso, codigo_necesidad))
    conexion.commit()

# ===========================================================
# SECCIÓN 9 — FLUJO PRINCIPAL
# ===========================================================

def main():
    conexion = conectar_base_datos()
    cursor = conexion.cursor()

    # Obtener datos base
    lista_contra, pesos_contra = obtener_contraindicaciones(cursor)
    codigos = obtener_codigos_infimas(cursor)

    for codigo_necesidad, pac in codigos:
        encontrados = analizar_documentos_codigo(
            codigo_necesidad,
            lista_contra
        )

        Contraindicaciones_encontradas[codigo_necesidad] = encontrados

        peso_final = calcular_peso(encontrados, pesos_contra)

        actualizar_peso(
            cursor,
            conexion,
            codigo_necesidad,
            peso_final
        )

        print(f"Código {codigo_necesidad} → Peso calculado: {peso_final}")

    cursor.close()
    conexion.close()

# ===========================================================
# PUNTO DE ENTRADA
# ===========================================================

if __name__ == "__main__":
    main()
