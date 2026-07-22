"""
Script de clasificación de compras públicas (infimas) usando Gemini 2.5 Flash
Conecta a MySQL, obtiene datos, clasifica con IA y actualiza estados

ACTUALIZACIÓN: Migrado de gemini-2.0-flash (descontinuado) a gemini-2.5-flash
Modelo actualizado: gemini-2.5-flash - Mejor precio/rendimiento con capacidades de pensamiento
Región: us-central1 (soportada)

ALTERNATIVAS DISPONIBLES:
- gemini-2.5-pro: Para casos que requieran máximo razonamiento (más costoso)
- gemini-3.1-pro-preview: Modelo experimental más avanzado (preview, puede tener limitaciones)

NUEVAS ETAPAS AÑADIDAS (v2):
- Etapa Adicional 1: Revisión semántica de registros 'seleccionada' con PACdoc/PACweb >= 0.
  Si hay coincidencia con palabras clave → 'no seleccionada'. Sin coincidencia → sin cambios.
- Etapa Adicional 2: Verificación de documentos en Google Cloud Storage.
  Si la carpeta del código de necesidad no existe o está vacía → eliminar fila de BD.
  Si la carpeta existe con documentos → sin cambios.
"""

import os
import re
import json
import tempfile
import datetime
import pandas as pd
import mysql.connector
from google.oauth2 import service_account
from google.cloud import storage                      # ← NUEVO: cliente GCS
import vertexai
from vertexai.generative_models import GenerativeModel
import sys
from pathlib import Path

# Raíz del proyecto al path de Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from Config import Global

# =========================
# 1. CONFIGURACIÓN
# =========================

MYSQL_CONFIG = {
    "host": Global.DB_HOST,
    "user": Global.DB_USER,
    "password": Global.DB_PASSWORD,
    "database": Global.DATABASE,
}

# Modelo actualizado - Gemini 2.5 Flash
# Este modelo ofrece:
# - Mejor rendimiento que 2.0 Flash
# - Capacidades de "pensamiento" (thinking) para mayor precisión
# - Disponibilidad en us-central1
# - Precio competitivo
GEMINI_MODEL = "gemini-2.5-pro"

# ALTERNATIVAS:
# GEMINI_MODEL = "gemini-2.5-pro"  # Para máxima precisión (más costoso)
# GEMINI_MODEL = "gemini-3.1-pro-preview"  # Experimental (puede tener limitaciones regionales)


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

    if Global.CREDENTIALS_GEMINI:
        return Global.CREDENTIALS_GEMINI, False

    raise Exception("No se encontraron credenciales")


# =========================
# 2. INICIALIZACIÓN DE VERTEX AI
# =========================

def inicializar_vertex_ai():
    ruta_credenciales, es_temp = obtener_ruta_credenciales()
    try:
        credentials = service_account.Credentials.from_service_account_file(
            ruta_credenciales
        )
        with open(ruta_credenciales, 'r') as f:
            creds_data = json.load(f)
            project_id = creds_data.get("project_id")

        if not project_id:
            raise Exception("No se encontró project_id en las credenciales")

        vertexai.init(
            project=project_id,
            credentials=credentials,
            location="us-central1"
        )
        return GenerativeModel(GEMINI_MODEL)
    finally:
        if es_temp:
            try:
                os.remove(ruta_credenciales)
            except Exception:
                pass


# =========================
# 3. UTILIDADES
# =========================

def safe_value(val, default="SIN_VALOR"):
    """Convierte valores de manera segura a string"""
    if pd.isna(val) or val is None:
        return default
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, datetime.date):
        return val.strftime("%Y-%m-%d")
    return str(val)


def limpiar_texto(texto):
    """Limpia y normaliza texto"""
    if not texto:
        return ""
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def dividir_dict(data, size=40):
    """Divide un diccionario en bloques de tamaño específico"""
    items = list(data.items())
    for i in range(0, len(items), size):
        yield dict(items[i: i + size])


# =========================
# 4. FUNCIONES BASE DE DATOS (ORIGINALES)
# =========================

def obtener_infimas():
    """Obtiene registros de infimas con etapa 'ingresada'"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM infimas
        WHERE etapa = 'ingresada'
    """)
    datos = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(datos)

    if not df.empty and "descripcion_objeto_compra" in df.columns:
        df["descripcion_objeto_compra"] = df["descripcion_objeto_compra"].apply(
            lambda x: limpiar_texto(str(x))
        )
    return df


def obtener_palabras_clave():
    """Obtiene palabras clave de la base de datos"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT palabra_clave FROM palabras_clave")
    filas = cursor.fetchall()
    cursor.close()
    conn.close()

    palabras = [limpiar_texto(fila[0]) for fila in filas if fila[0]]
    return palabras


def actualizar_etapa(df, resultados):
    """Actualiza la etapa de los registros según resultados de clasificación"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    for idx, row in df.iterrows():
        if idx not in resultados:
            continue

        # Lógica: SI se encontró palabra clave -> NO seleccionada
        # NO se encontró palabra clave -> PRESELECCIONADA
        etapa = "no seleccionada" if resultados[idx] is True else "preseleccionada"

        cursor.execute(
            """
            UPDATE infimas
            SET etapa = %s,
                actualizado_en = NOW()
            WHERE id_infima = %s
        """,
            (etapa, row["id_infima"]),
        )

    conn.commit()
    cursor.close()
    conn.close()


# =========================
# 5. CLASIFICACIÓN CON IA (ORIGINAL)
# =========================

def clasificar_descripcion_lote(batch_data, palabras_clave, model):
    """
    Clasifica un lote de descripciones usando Gemini 2.5 Flash

    Gemini 2.5 Flash incluye capacidades de pensamiento que mejoran
    la precisión en tareas de clasificación complejas.
    """
    prompt = f"""
Eres un analista experto de compras públicas especializado en clasificación de contenido.

TAREA:
Analiza si en las siguientes descripciones se mencionan estas palabras o frases clave:
{", ".join(palabras_clave)}

INSTRUCCIONES:
1. Lee cuidadosamente cada descripción
2. Busca coincidencias exactas o variaciones semánticas de las palabras/frases clave
3. Si encuentras AL MENOS UNA palabra o frase clave en la descripción, responde "SI"
4. Si NO encuentras NINGUNA palabra o frase clave, responde "NO"
5. Sé preciso: las palabras deben estar realmente presentes o tener clara relación semántica

FORMATO DE RESPUESTA:
Responde ESTRICTAMENTE con un objeto JSON donde:
- La clave es el número de fila
- El valor es "SI" (se encontró al menos una palabra clave) o "NO" (no se encontró ninguna)

DATOS A ANALIZAR:
{json.dumps(batch_data, ensure_ascii=False, indent=2)}

RESPONDE SOLO CON EL JSON, SIN TEXTO ADICIONAL.
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Limpiar markdown si viene con ```json```
        if response_text.startswith("```"):
            response_text = re.sub(r"```json\n?|```\n?", "", response_text).strip()

        resultado_json = json.loads(response_text)

        # Convertir "SI"/"NO" a True/False
        resultado_bool = {}
        for idx, valor in resultado_json.items():
            idx_int = int(idx)
            resultado_bool[idx_int] = (valor.upper() == "SI")

        return resultado_bool

    except Exception as e:
        print(f"Error al clasificar lote: {e}")
        # Retornar todos como False (preseleccionados) en caso de error
        return {int(idx): False for idx in batch_data.keys()}


# ==============================================================
# 6. NUEVA ETAPA ADICIONAL 1 — REVISIÓN DE SELECCIONADAS CON IA
# ==============================================================

def obtener_seleccionadas_para_revision():
    """
    Obtiene registros de la tabla infimas con:
      - etapa = 'seleccionada'
      - PACdoc >= 0  (excluye NULL automáticamente en MySQL)
      - PACweb >= 0  (excluye NULL automáticamente en MySQL)

    Retorna un DataFrame con columnas: codigo_necesidad, descripcion_objeto_compra
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT codigo_necesidad, descripcion_objeto_compra
        FROM infimas
        WHERE etapa = 'seleccionada'
          AND PACdoc >= 0
          AND PACweb >= 0
    """)
    datos = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(datos)

    if not df.empty and "descripcion_objeto_compra" in df.columns:
        df["descripcion_objeto_compra"] = df["descripcion_objeto_compra"].apply(
            lambda x: limpiar_texto(str(x))
        )
    return df


def marcar_no_seleccionada_por_codigo(codigo_necesidad):
    """
    Actualiza etapa a 'no seleccionada' identificando el registro
    por su codigo_necesidad (clave de negocio).
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE infimas
        SET etapa = %s,
            actualizado_en = NOW()
        WHERE codigo_necesidad = %s
        """,
        ("no seleccionada", codigo_necesidad),
    )
    conn.commit()
    cursor.close()
    conn.close()


def etapa_adicional_1_revision_seleccionadas(model):
    """
    ETAPA ADICIONAL 1: Revisión semántica de registros 'seleccionada'.

    Flujo:
    1. Consulta registros con etapa='seleccionada' AND PACdoc>=0 AND PACweb>=0.
    2. Reutiliza obtener_palabras_clave() para cargar las palabras de referencia.
    3. Reutiliza clasificar_descripcion_lote() para enviar las descripciones a Gemini.
    4. Si el modelo detecta coincidencia semántica → actualiza etapa a 'no seleccionada'.
    5. Si no hay coincidencia → no modifica la fila.

    Retorna la lista completa de codigos_necesidad consultados al inicio,
    que será reutilizada por la Etapa Adicional 2.
    """
    print("\n" + "=" * 60)
    print("ETAPA ADICIONAL 1: REVISIÓN SEMÁNTICA DE SELECCIONADAS")
    print("=" * 60)

    # --- 1. Obtener registros ---
    print("\n   Consultando registros seleccionados con PACdoc/PACweb >= 0...")
    df = obtener_seleccionadas_para_revision()

    if df.empty:
        print("   ⚠  No hay registros con las condiciones requeridas. "
              "Se omite esta etapa.")
        return []

    print(f"   ✓ {len(df)} registro(s) encontrado(s)")

    # Guardar lista de códigos ANTES de cualquier modificación
    # Esta lista es la que retornará la función para uso en Etapa Adicional 2
    lista_codigos = df["codigo_necesidad"].tolist()

    # --- 2. Cargar palabras clave (función reutilizada) ---
    print("\n   Cargando palabras clave...")
    palabras_clave = obtener_palabras_clave()

    if not palabras_clave:
        print("   ⚠  No hay palabras clave en la base de datos. "
              "Se omite la clasificación IA.")
        return lista_codigos

    print(f"   ✓ {len(palabras_clave)} palabra(s) clave cargada(s)")

    # --- 3. Preparar datos para el modelo ---
    # Mapa: índice_dataframe → descripción
    # Mapa auxiliar: índice_dataframe → codigo_necesidad
    data_por_indice = {}
    indice_a_codigo = {}

    for idx, row in df.iterrows():
        desc = str(row["descripcion_objeto_compra"]).strip()
        if desc and desc != "nan":
            data_por_indice[idx] = desc
            indice_a_codigo[idx] = row["codigo_necesidad"]

    if not data_por_indice:
        print("   ⚠  Sin descripciones válidas para clasificar.")
        return lista_codigos

    # --- 4. Clasificar en lotes (función reutilizada) ---
    total_lotes = (len(data_por_indice) + 39) // 40
    print(f"\n   Clasificando {len(data_por_indice)} descripción(es) "
          f"en {total_lotes} lote(s)...")

    resultados_finales = {}
    lote_actual = 0

    for bloque in dividir_dict(data_por_indice, size=40):
        lote_actual += 1
        print(f"   Procesando lote {lote_actual}/{total_lotes}...")
        resultados = clasificar_descripcion_lote(bloque, palabras_clave, model)
        resultados_finales.update(resultados)

    # --- 5. Aplicar cambios a la base de datos ---
    print("\n   Aplicando resultados a la base de datos...")
    no_seleccionadas = 0
    sin_cambios = 0

    for idx, tiene_coincidencia in resultados_finales.items():
        codigo = indice_a_codigo.get(idx)
        if not codigo:
            continue

        if tiene_coincidencia:
            # Coincidencia semántica encontrada → cambiar etapa
            marcar_no_seleccionada_por_codigo(codigo)
            print(f"   ✗ [{codigo}] Coincidencia detectada → 'no seleccionada'")
            no_seleccionadas += 1
        else:
            # Sin coincidencia → no se toca el registro
            print(f"   ✓ [{codigo}] Sin coincidencia → sin cambios")
            sin_cambios += 1

    # --- Resumen ---
    print(f"\n{'=' * 60}")
    print("   RESUMEN ETAPA ADICIONAL 1")
    print(f"{'=' * 60}")
    print(f"   Registros analizados:             {len(resultados_finales)}")
    print(f"   Actualizados a 'no seleccionada': {no_seleccionadas}")
    print(f"   Sin modificaciones:               {sin_cambios}")
    print(f"{'=' * 60}")

    return lista_codigos


# ==============================================================
# 7. NUEVA ETAPA ADICIONAL 2 — VERIFICACIÓN EN GOOGLE CLOUD STORAGE
# ==============================================================

def inicializar_gcs():
    """
    Inicializa el cliente de Google Cloud Storage usando las mismas
    credenciales que el resto del script (obtener_ruta_credenciales).

    Retorna: (bucket_object, ruta_credenciales, es_temporal)
    El llamador es responsable de eliminar el archivo temporal si es_temporal=True.
    """
    ruta_creds, es_temp = obtener_ruta_credenciales()
    # La variable de entorno es la forma estándar de autenticar el cliente GCS
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ruta_creds
    gcs_client = storage.Client()
    bucket = gcs_client.bucket(Global.BUCKET_NAME)
    return bucket, ruta_creds, es_temp


def verificar_documentos_en_gcs(bucket, codigo_necesidad):
    """
    Comprueba si existe al menos un archivo bajo la ruta:
      'Documentos de Contratación/<codigo_necesidad>/'

    Retorna True si existe la carpeta y contiene documentos,
    False si la carpeta no existe o está vacía.
    """
    try:
        prefijo = f"Documentos de Contratación/{codigo_necesidad}/"
        # max_results=1 es suficiente para saber si hay al menos un objeto
        blobs = list(bucket.list_blobs(prefix=prefijo, max_results=1))
        return len(blobs) > 0
    except Exception as e:
        print(f"   [GCS] Error verificando carpeta '{codigo_necesidad}': {e}")
        return False


def eliminar_fila_infima(codigo_necesidad):
    """
    Elimina completamente la fila de la tabla infimas cuyo
    codigo_necesidad coincide con el valor indicado.

    Primero elimina los registros hijo en 'evaluaciones' para evitar
    el error de clave foránea (evaluaciones_ibfk_1).

    Retorna True si la operación fue exitosa, False en caso contrario.
    """
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        # 1. Eliminar registros dependientes en evaluaciones
        cursor.execute(
            "DELETE FROM evaluaciones WHERE codigo_necesidad = %s",
            (codigo_necesidad,),
        )
        # 2. Eliminar la fila padre en infimas
        cursor.execute(
            "DELETE FROM infimas WHERE codigo_necesidad = %s",
            (codigo_necesidad,),
        )
        filas_afectadas = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return filas_afectadas > 0
    except Exception as e:
        print(f"   [DB] Error eliminando '{codigo_necesidad}': {e}")
        return False


def etapa_adicional_2_verificacion_gcs(lista_codigos):
    """
    ETAPA ADICIONAL 2: Verificación de documentos en Google Cloud Storage.

    Flujo:
    1. Inicializa el cliente GCS con las credenciales de las variables globales.
    2. Itera sobre la lista de códigos obtenida en la Etapa Adicional 1.
    3. Por cada código comprueba si existe la carpeta
       'Documentos de Contratación/<codigo_necesidad>/' con al menos un archivo.
    4. Si la carpeta existe y tiene archivos → no se realiza ninguna acción.
    5. Si la carpeta no existe o está vacía → se elimina la fila de la BD.
    """
    print("\n" + "=" * 60)
    print("ETAPA ADICIONAL 2: VERIFICACIÓN DE DOCUMENTOS EN GCS")
    print("=" * 60)

    if not lista_codigos:
        print("   ⚠  Lista de códigos vacía. Se omite esta etapa.")
        return

    # --- 1. Inicializar GCS ---
    print(f"\n   Conectando a Google Cloud Storage (bucket: {Global.BUCKET_NAME})...")
    try:
        bucket, ruta_creds, es_temp = inicializar_gcs()
        print("   ✓ Conexión a GCS establecida")
    except Exception as e:
        print(f"   ✗ No se pudo conectar a GCS: {e}")
        print("   Se omite la Etapa Adicional 2.")
        return

    try:
        # --- 2. Verificar cada código ---
        print(f"\n   Verificando {len(lista_codigos)} código(s) de necesidad...\n")

        con_documentos = 0
        eliminados = 0
        errores = 0

        for i, codigo in enumerate(lista_codigos, 1):
            print(f"   [{i}/{len(lista_codigos)}] {codigo}")

            existe = verificar_documentos_en_gcs(bucket, codigo)

            if existe:
                # Carpeta con documentos → sin modificaciones
                print(f"   ✓ Documentos encontrados en GCS → sin cambios en BD")
                con_documentos += 1
            else:
                # Sin carpeta o vacía → eliminar fila
                print(f"   ✗ Sin carpeta o sin documentos en GCS → eliminando fila de BD")
                if eliminar_fila_infima(codigo):
                    print(f"   ✓ Fila eliminada correctamente")
                    eliminados += 1
                else:
                    print(f"   ⚠  No se encontró la fila o hubo un error al eliminar")
                    errores += 1

        # --- Resumen ---
        print(f"\n{'=' * 60}")
        print("   RESUMEN ETAPA ADICIONAL 2")
        print(f"{'=' * 60}")
        print(f"   Códigos verificados:           {len(lista_codigos)}")
        print(f"   Con documentos en GCS:         {con_documentos}")
        print(f"   Filas eliminadas de BD:        {eliminados}")
        print(f"   Errores:                       {errores}")
        print(f"{'=' * 60}")

    finally:
        # Limpiar archivo temporal de credenciales si aplica
        if es_temp:
            try:
                os.remove(ruta_creds)
            except Exception:
                pass


# =========================
# 8. ORQUESTADOR PRINCIPAL
# =========================

def main():
    """
    Función principal que orquesta todo el proceso en cuatro pasos:

    PROCESO ORIGINAL
    ─────────────────────────────────────────────────────────────
    1. Inicializa el modelo Gemini 2.5 Flash.
    2. Obtiene registros con etapa='ingresada' y los clasifica:
       - Con palabra clave  → 'no seleccionada'
       - Sin palabra clave  → 'preseleccionada'

    NUEVAS ETAPAS AÑADIDAS
    ─────────────────────────────────────────────────────────────
    3. Etapa Adicional 1: Revisión semántica de registros
       'seleccionada' con PACdoc>=0 y PACweb>=0.
       - Coincidencia IA  → 'no seleccionada'
       - Sin coincidencia → sin cambios
       Retorna la lista de códigos para la siguiente etapa.

    4. Etapa Adicional 2: Verificación de documentos en GCS.
       - Carpeta con docs → sin cambios en BD
       - Sin carpeta/docs → eliminar fila de BD
    """
    print("=" * 60)
    print("CLASIFICADOR DE COMPRAS PÚBLICAS")
    print(f"Modelo: {GEMINI_MODEL}")
    print("=" * 60)

    # Inicializar modelo Gemini
    print(f"\n1. Inicializando modelo {GEMINI_MODEL}...")
    try:
        model = inicializar_vertex_ai()
        print("   ✓ Modelo inicializado correctamente")
    except Exception as e:
        print(f"   ✗ Error al inicializar modelo: {e}")
        return

    # Obtener datos (etapa original: 'ingresada')
    print("\n2. Obteniendo registros de la base de datos...")
    df = obtener_infimas()
    if df.empty:
        print("   ⚠ No hay datos en la tabla infimas con etapa 'ingresada'.")
    else:
        print(f"   ✓ {len(df)} registros encontrados")

        # Obtener palabras clave
        print("\n3. Obteniendo palabras clave...")
        palabras_clave = obtener_palabras_clave()
        if not palabras_clave:
            print("   ⚠ No hay palabras clave en la tabla palabras_clave.")
        else:
            print(f"   ✓ {len(palabras_clave)} palabras clave cargadas")

            # Preparar datos
            data = {
                idx: str(row["descripcion_objeto_compra"]).strip()
                for idx, row in df.iterrows()
                if row.get("descripcion_objeto_compra")
            }

            if not data:
                print("   ⚠ No hay descripciones válidas para analizar.")
            else:
                # Clasificar por lotes
                print(f"\n4. Clasificando {len(data)} registros en lotes de 40...")
                resultados_finales = {}
                total_lotes = (len(data) + 39) // 40
                lote_actual = 0

                for bloque in dividir_dict(data, size=40):
                    lote_actual += 1
                    print(f"   Procesando lote {lote_actual}/{total_lotes}...")
                    resultados = clasificar_descripcion_lote(bloque, palabras_clave, model)
                    resultados_finales.update(resultados)

                # Actualizar base de datos
                print("\n5. Actualizando estados en la base de datos...")
                actualizar_etapa(df, resultados_finales)

                # Resumen del proceso original
                preseleccionadas = sum(1 for v in resultados_finales.values() if not v)
                no_seleccionadas = sum(1 for v in resultados_finales.values() if v)

                print("\n" + "=" * 60)
                print("PROCESO ORIGINAL FINALIZADO")
                print("=" * 60)
                print(f"Registros procesados:     {len(resultados_finales)}")
                print(f"Preseleccionadas:         {preseleccionadas}")
                print(f"No seleccionadas:         {no_seleccionadas}")
                print("=" * 60)

    # ──────────────────────────────────────────────────────────
    # ETAPA ADICIONAL 1: Revisión semántica de 'seleccionadas'
    # ──────────────────────────────────────────────────────────
    # Se ejecuta independientemente del resultado del proceso original,
    # porque puede haber registros 'seleccionada' de ejecuciones anteriores.
    lista_codigos_para_gcs = etapa_adicional_1_revision_seleccionadas(model)

    # ──────────────────────────────────────────────────────────
    # ETAPA ADICIONAL 2: Verificación de documentos en GCS
    # ──────────────────────────────────────────────────────────
    # Usa la lista devuelta por la Etapa Adicional 1 (códigos tal como
    # estaban ANTES de cualquier cambio de etapa en esa misma ejecución).
    etapa_adicional_2_verificacion_gcs(lista_codigos_para_gcs)

    print("\n" + "=" * 60)
    print("PROCESO COMPLETO FINALIZADO CORRECTAMENTE")
    print("=" * 60)


# =========================
# 9. EJECUCIÓN
# =========================

if __name__ == "__main__":
    main()