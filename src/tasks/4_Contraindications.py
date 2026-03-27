"""
=================================================================================
SISTEMA DE ANÁLISIS DE ÍNFIMAS - COMPRAS PÚBLICAS ECUADOR
=================================================================================

Este script automatiza el análisis de procesos de "ínfima cuantía" mediante:
1. Extracción de PAC (Plan Anual de Contratación) desde documentos usando IA
2. Web scraping del portal oficial de compras públicas para validación
3. Análisis de contraindicaciones en documentos
4. Cálculo de pesos según fórmula: 1 - Π(1 - P(i))

=================================================================================
"""

import os
import re
import json
import tempfile
import time
import unicodedata  # Para normalizar texto y quitar acentos
import pandas as pd
import mysql.connector
from google.oauth2 import service_account
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import sys
from pathlib import Path
import platform
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

#raíz del proyecto al path de Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from Config import Global

# =========================
# 1. CONFIGURACIÓN
# =========================

# Configuración de conexión a base de datos MySQL
MYSQL_CONFIG = {
    "host": Global.DB_HOST,
    "user": Global.DB_USER,
    "password": Global.DB_PASSWORD,
    "database": Global.DATABASE,
}

# Rutas de archivos y buckets de Google Cloud
GEMINI_CREDENTIALS_PATH = Global.CREDENTIALS_GEMINI
BUCKET_NAME = Global.BUCKET_NAME
CARPETA_DOCUMENTOS = "Documentos de Contratación"

# =========================
# 2. INICIALIZACIÓN
# =========================

def obtener_ruta_credenciales():
    """
    Retorna una ruta válida al archivo de credenciales.
    Compatible con:
    - Render (JSON en variable)
    - Local (archivo físico)
    """

    # PRODUCCIÓN (Render)
    credentials_json = Global.RENDER_CRENDENTIALS_JSON

    if credentials_json:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as temp:
            temp.write(credentials_json)
            return temp.name

    # LOCAL
    if Global.CREDENTIALS_GEMINI:
        return Global.CREDENTIALS_GEMINI

    raise Exception("No se encontraron credenciales de Gemini")

def inicializar_servicios():
    """
    Inicializa los servicios de Google Cloud (VertexAI y Storage).
    
    Returns:
        tuple: (model, bucket)
            - model: Modelo generativo de VertexAI para análisis de documentos
            - bucket: Cliente de Google Cloud Storage para acceder a documentos
    
    Raises:
        Exception: Si falla la autenticación o inicialización de servicios
    """
    global BUCKET_NAME
    
    ruta_credencial = obtener_ruta_credenciales()

    # Cargar credenciales desde archivo JSON
    credentials = service_account.Credentials.from_service_account_file(
        ruta_credencial
    )
    
    # Extraer project_id del archivo de credenciales
    with open(ruta_credencial, 'r') as f:
        creds_data = json.load(f)
        project_id = creds_data.get('project_id')
    
    if not project_id:
        raise Exception("No se encontró project_id en credenciales")


    # Inicializar VertexAI en región us-east4 (mejor disponibilidad)
    vertexai.init(
        project=project_id,
        credentials=credentials,
        location="us-central1"
    )
    
    # Inicializar cliente de Cloud Storage
    storage_client = storage.Client(
        project=project_id,
        credentials=credentials
    )
    
    # Usar modelo Gemini 2.5 Pro (más potente para análisis de documentos)
    model = GenerativeModel("gemini-2.0-flash")
    bucket = storage_client.bucket(BUCKET_NAME)
    
    return model, bucket

# =========================
# 3. FUNCIONES BASE DE DATOS
# =========================

def obtener_contraindicaciones():
    """
    Obtiene la lista de contraindicaciones desde la base de datos.
    
    Returns:
        list: Lista de strings con nombres de contraindicaciones
    
    Ejemplo:
        ['Procesos que requieran soporte técnico', 'Adquisición de software', ...]
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT contraindicacion FROM contraindicaciones")
    filas = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Filtrar valores nulos y extraer solo el texto
    contraindicaciones = [fila[0] for fila in filas if fila[0]]
    return contraindicaciones

def obtener_contraindicaciones_con_peso():
    """
    Obtiene contraindicaciones con sus pesos asociados.
    
    Returns:
        DataFrame: Pandas DataFrame con columnas ['contraindicacion', 'peso']
        
    Nota:
        Los pesos son valores entre 0 y 1 que indican la severidad de cada contraindicación
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT contraindicacion, peso FROM contraindicaciones")
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    df = pd.DataFrame(datos)
    return df

def obtener_codigos_preseleccionados():
    """
    Obtiene códigos de necesidad con etapa 'seleccionada'.
    
    Returns:
        list: Lista de códigos de necesidad (ej: 'nic-1234567890001-2026-00001')
        
    Nota:
        Solo obtiene códigos que están en etapa 'seleccionada' para procesar
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT codigo_necesidad 
        FROM infimas 
        WHERE etapa = 'seleccionada' 
        AND (PACweb IS NULL AND PACdoc IS NULL)
    """)
    filas = cursor.fetchall()
    cursor.close()
    conn.close()
    
    codigos = [fila[0] for fila in filas if fila[0]]
    return codigos

def obtener_infimas_con_pac():
    """
    Obtiene ínfimas con PACdoc >= 0 para validación de PAC en portal web.
    
    Returns:
        DataFrame: DataFrame con columnas:
            - codigo_necesidad
            - descripcion_objeto_compra
            - entidad_contratante
            - V_Total (inicializado en 0.0)
    
    Nota:
        Solo obtiene registros con PACdoc >= 0 (No se encontró PAC en los documentos y en los que sí,
                                                se comparará el PAC de documentos con el PAC web)
        El campo V_Total se llenará después con web scraping
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT codigo_necesidad, descripcion_objeto_compra, entidad_contratante
        FROM infimas 
        WHERE PACdoc >= 0 AND PACweb IS NULL
    """)
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    df = pd.DataFrame(datos)
    if not df.empty:
        # Agregar columna V_Total para almacenar valor del portal
        df['V_Total'] = 0.0
    return df

def actualizar_pac_en_bd(codigos_pac_dict):
    """
    Actualiza la columna PACdoc en la base de datos con valores extraídos por IA.
    
    Args:
        codigos_pac_dict (dict): Diccionario {codigo_necesidad: pac_value}
    
    Ejemplo:
        {'nic-123-2026-00001': 15000.50, 'nic-456-2026-00002': 0.0}
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    for codigo, pac in codigos_pac_dict.items():
        cursor.execute("""
            UPDATE infimas 
            SET PACdoc = %s,
                actualizado_en = NOW()
            WHERE codigo_necesidad = %s
        """, (pac, codigo))
    
    conn.commit()
    cursor.close()
    conn.close()

def actualizar_pac_desde_vtotal(df_infimas):
    """
    Actualiza PACweb con valores de V_Total obtenidos del portal web.
    También cambia la etapa a 'seleccionada' para códigos con PACweb > 0.
    
    Args:
        df_infimas (DataFrame): DataFrame con columnas codigo_necesidad y V_Total
    
    Lógica:
        1. Actualiza PACweb = V_Total donde V_Total > 0
        2. Cambia etapa = 'recomendada' para todos los PAC > 0 como paso intermedio
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    # Actualizar PAC con valores V_Total del portal
    for _, row in df_infimas.iterrows():
        if row['V_Total'] > 0:
            cursor.execute("""
                UPDATE infimas 
                SET PACweb = %s,
                    actualizado_en = NOW()
                WHERE codigo_necesidad = %s
            """, (row['V_Total'], row['codigo_necesidad']))
    
    # Cambiar etapa a 'recomendada' para todos los códigos con PAC > 0
    cursor.execute("""
        UPDATE infimas 
        SET etapa = 'recomendada',
            actualizado_en = NOW()
        WHERE PACdoc > 0 OR PACweb >0
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

def obtener_codigos_pac_mayores_cero():
    """
    Obtiene códigos de necesidad con PAC > 0 para análisis de contraindicaciones.
    
    Returns:
        dict: Diccionario {codigo_necesidad: PAC}
    
    Nota:
        Solo códigos con PAC > 0 pasan al análisis de contraindicaciones
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT codigo_necesidad, PACdoc, PACweb
        FROM infimas 
        WHERE etapa = 'recomendada' AND (PACdoc > 0 OR PACweb > 0)   
    """)
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    codigos_pac = {row['codigo_necesidad']: row['PACdoc'] or row ['PACweb'] for row in datos}
    return codigos_pac

def actualizar_peso_en_bd(codigo_necesidad, peso, contraindicaciones_encontradas):
    """
    Guarda el peso calculado en la tabla EVALUACIONES.
    
    Args:
        codigo_necesidad (str): Código de la ínfima
        peso (float): Peso calculado (0.0 a 1.0)
        contraindicaciones_encontradas (list): Lista de contraindicaciones detectadas
    
    Lógica:
        - Inserta nuevo registro o actualiza existente (UPSERT)
        - Guarda justificación como string separado por comas
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    # Convertir lista a string separado por comas
    justificacion = ", ".join(contraindicaciones_encontradas) if contraindicaciones_encontradas else ""
    
    # UPSERT: Inserta o actualiza según si existe el registro
    cursor.execute("""
        INSERT INTO evaluaciones (codigo_necesidad, Peso_total, justificacion, fecha)
        VALUES (%s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            Peso_total = %s,
            justificacion = %s,
            fecha = NOW()
    """, (codigo_necesidad, peso, justificacion, peso, justificacion))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"      ✓ Peso guardado en evaluaciones: {codigo_necesidad} → {peso:.4f}")

# =========================
# 4. FUNCIONES DE BUCKET/IA
# =========================

def buscar_pac_en_documentos(bucket, codigo_necesidad, model):
    """
    Busca el PAC (presupuesto) en documentos del bucket usando IA de Google Gemini.
    
    Args:
        bucket: Cliente de Google Cloud Storage
        codigo_necesidad (str): Código de la ínfima
        model: Modelo generativo de VertexAI
    
    Returns:
        float: Valor del PAC encontrado, o 0.0 si no se encuentra
    
    Proceso:
        1. Lista archivos PDF/TXT en carpeta del código
        2. Crea prompt específico para extraer presupuesto
        3. Envía documentos a IA con retry logic (3 intentos)
        4. Extrae valor numérico de la respuesta
    
    Nota:
        - PDFs se envían por URI (gs://bucket/path)
        - TXTs se descargan y envían como texto
        - Implementa exponential backoff para errores 429 (rate limit)
    """
    carpeta_path = f"{CARPETA_DOCUMENTOS}/{codigo_necesidad}/"
    
    # Listar todos los archivos en la carpeta del código
    blobs = list(bucket.list_blobs(prefix=carpeta_path))
    
    if not blobs:
        print(f"   ⚠ No se encontraron documentos para {codigo_necesidad}")
        return 0.0
    
    # Preparar documentos para enviar a IA
    documentos_contenido = []
    for blob in blobs:
        # Ignorar carpetas (terminan en /)
        if blob.name.endswith('/'):
            continue
        
        nombre_lower = blob.name.lower()

        # Procesar PDFs (enviar por URI)
        if nombre_lower.endswith('.pdf'):
            blob_uri = f"gs://{BUCKET_NAME}/{blob.name}"
            documentos_contenido.append(Part.from_uri(blob_uri, mime_type="application/pdf"))
            print(f"      📄 PDF agregado: {blob.name.split('/')[-1]}")

        # Procesar TXTs (descargar y enviar contenido)
        elif nombre_lower.endswith('.txt'):
            try:
                contenido = blob.download_as_text(encoding='utf-8')
                documentos_contenido.append(contenido)
                print(f"      📝 TXT agregado: {blob.name.split('/')[-1]}")
            except UnicodeDecodeError:
                print(f"      ⚠ TXT - No se pudo decodificar: {blob.name.split('/')[-1]}")
        
        # .doc/.docx no soportados (omitir)
        elif nombre_lower.endswith(('.doc', '.docx')):
            print(f"      ⚠ Archivo .doc/.docx detectado (omitido): {blob.name.split('/')[-1]}") 

    if not documentos_contenido:
        print(f"   ⚠ No se pudo procesar ningún documento para {codigo_necesidad}")
        return 0.0
    
    # Prompt optimizado para extracción de presupuesto
    prompt = f"""Eres un asistente experto en analizar documentos de compras públicas ecuatorianas.

Analiza CUIDADOSAMENTE los documentos del código de necesidad: {codigo_necesidad}

Busca el PRESUPUESTO o MONTO TOTAL asignado. Puede aparecer como:
- "Plan Anual de Contratación" o "PAC"
- "Partida presupuestaria"
- "Presupuesto referencial"
- "Monto total"
- "Valor total"
- "Presupuesto asignado"
- "Cuantía"
- Cualquier cifra monetaria importante

INSTRUCCIONES CRÍTICAS:
1. Busca números con formato: $1,234.56 o 1234.56 o USD 1,234.56
2. El monto suele estar en tablas, junto a palabras como "presupuesto", "valor", "total"
3. Ignora valores pequeños (menos de $100)
4. Si encuentras varios montos, selecciona el MAYOR

FORMATO DE RESPUESTA:
- Si encuentras un monto: Responde SOLO el número sin símbolos (ejemplo: 15000.50)
- Si NO encuentras ningún monto: Responde SOLO: 0.0

NO incluyas:
- Símbolos de moneda ($, USD)
- Texto explicativo
- Comas separadoras de miles

Ejemplos de respuestas CORRECTAS:
15000.50
234567.89
0.0

Tu respuesta (solo el número):"""

    # Retry logic con exponential backoff (manejo de errores 429)
    max_intentos = 3
    for intento in range(max_intentos):
        try:
            contenido_completo = [prompt] + documentos_contenido
            
            print(f"      🤖 Enviando {len(documentos_contenido)} documento(s) a IA... (Intento {intento + 1}/{max_intentos})")
            
            # Configuración para respuestas determinísticas
            generation_config = {
                "temperature": 0.1,  # Baja temperatura = más determinístico
                "top_p": 0.8,
                "top_k": 20,
                "max_output_tokens": 100,  # Solo necesitamos un número
            }
            
            # Llamada a IA
            response = model.generate_content(
                contenido_completo,
                generation_config=generation_config
            )
            response_text = response.text.strip()
            
            print(f"      💬 Respuesta IA: '{response_text}'")
            
            # Limpiar respuesta (remover símbolos de moneda)
            response_clean = response_text.replace('$', '').replace('USD', '').replace(',', '').strip()
            
            # Extraer primer número encontrado
            match = re.search(r'[\d.]+', response_clean)
            if match:
                pac = float(match.group())
                if pac > 0:
                    print(f"      ✅ PAC encontrado: {pac}")
                else:
                    print(f"      ⚠ IA respondió 0.0 - No encontró monto en los documentos")
                return pac
            
            print(f"      ⚠ No se encontró número en respuesta")
            return 0.0
            
        except Exception as e:
            error_msg = str(e)
            
            # Manejo específico de error 429 (rate limit)
            if "429" in error_msg or "Resource exhausted" in error_msg:
                if intento < max_intentos - 1:
                    # Exponential backoff: 30s, 60s, 90s
                    tiempo_espera = (intento + 1) * 30
                    print(f"      ⏳ Error 429 - Esperando {tiempo_espera}s antes de reintentar...")
                    time.sleep(tiempo_espera)
                    continue
                else:
                    print(f"      ✗ Error 429 persiste después de {max_intentos} intentos")
                    print(f"      💡 Sugerencia: Verifica cuota en Google Cloud Console")
                    return 0.0
            else:
                # Otros errores
                print(f"      ✗ Error al analizar documentos: {e}")
                return 0.0
    
    return 0.0

def buscar_contraindicaciones_en_documentos(bucket, codigo_necesidad, contraindicaciones_list, model):
    """
    Busca contraindicaciones mencionadas en documentos usando IA.
    
    Args:
        bucket: Cliente de Google Cloud Storage
        codigo_necesidad (str): Código de la ínfima
        contraindicaciones_list (list): Lista de contraindicaciones a buscar
        model: Modelo generativo de VertexAI
    
    Returns:
        list: Lista de contraindicaciones encontradas en los documentos
    
    Ejemplo:
        Input: ['Soporte técnico', 'Software', 'Capacitación']
        Output: ['Soporte técnico', 'Capacitación']
    
    Nota:
        - La IA devuelve un array JSON con las contraindicaciones encontradas
        - Maneja respuestas con o sin markdown ```json
    """
    carpeta_path = f"{CARPETA_DOCUMENTOS}/{codigo_necesidad}/"
    
    blobs = list(bucket.list_blobs(prefix=carpeta_path))
    
    if not blobs:
        return []
    
    # Preparar documentos
    documentos_contenido = []
    for blob in blobs:
        if blob.name.endswith('/'):
            continue
        
        if blob.name.lower().endswith('.pdf'):
            blob_uri = f"gs://{BUCKET_NAME}/{blob.name}"
            documentos_contenido.append(Part.from_uri(blob_uri, mime_type="application/pdf"))

        # ── CORRECCIÓN: manejo robusto de encoding para TXT/DOC/DOCX ──────────
        elif blob.name.lower().endswith(('.txt', '.doc', '.docx')):
            try:
                contenido = blob.download_as_text(encoding='utf-8')
                documentos_contenido.append(contenido)
            except UnicodeDecodeError:
                try:
                    # Fallback: latin-1 decodifica cualquier byte sin lanzar error
                    contenido = blob.download_as_text(encoding='latin-1')
                    documentos_contenido.append(contenido)
                    print(f"      ⚠ Archivo decodificado con latin-1: {blob.name.split('/')[-1]}")
                except Exception as e:
                    print(f"      ✗ No se pudo decodificar archivo: {blob.name.split('/')[-1]} - {e}")
        # ──────────────────────────────────────────────────────────────────────
    
    if not documentos_contenido:
        return []
    
    # Prompt para búsqueda de contraindicaciones
    contraindicaciones_str = ", ".join(contraindicaciones_list)
    prompt = f"""
Analiza los documentos proporcionados del código de necesidad {codigo_necesidad}.

Busca si aparecen mencionadas alguna de estas contraindicaciones:
{contraindicaciones_str}

Responde ÚNICAMENTE con un array JSON de las contraindicaciones que SÍ encontraste mencionadas.
Si no encuentras ninguna, responde: []

Ejemplo de respuesta:
["contraindicacion1", "contraindicacion2"]

NO incluyas explicaciones, solo el array JSON.
"""

    try:
        contenido_completo = [prompt] + documentos_contenido
        response = model.generate_content(contenido_completo)
        response_text = response.text.strip()
        
        # Limpiar markdown (```json ... ```)
        if response_text.startswith("```"):
            response_text = re.sub(r"```json\n?|```\n?", "", response_text).strip()
        
        # Parsear JSON
        contraindicaciones_encontradas = json.loads(response_text)
        return contraindicaciones_encontradas
        
    except Exception as e:
        print(f"   ✗ Error al buscar contraindicaciones: {e}")
        return []

# =========================
# 5. WEB SCRAPING
# =========================


def configurar_driver():
    """
    Configura Chrome adaptándose automáticamente al sistema operativo.
    - Linux (Render): usa ChromeDriver del sistema en /usr/bin/chromedriver
    - Windows (local): descarga ChromeDriver automáticamente
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,800")

    if platform.system() == "Linux":
        # Render / servidor Linux
        driver = webdriver.Chrome(
            service=Service("/usr/bin/chromedriver"),
            options=chrome_options
        )
    else:
        # Windows / Mac local
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    return driver

def buscar_vtotal_en_portal(df_infimas):
    """
    Busca V_Total para cada ínfima en el portal oficial de compras públicas.
    
    Args:
        df_infimas (DataFrame): DataFrame con columnas:
            - codigo_necesidad
            - entidad_contratante
            - descripcion_objeto_compra
            - V_Total (se actualizará)
    
    Returns:
        DataFrame: Mismo DataFrame con columna V_Total actualizada
    
    Proceso:
        1. Configura driver de Selenium
        2. Para cada fila, busca entidad y descripción en portal
        3. Actualiza V_Total si se encuentra coincidencia
        4. Cierra driver al finalizar
    """
    driver = configurar_driver()
    
    try:
        for idx, row in df_infimas.iterrows():
            entidad = row['entidad_contratante']
            descripcion = row['descripcion_objeto_compra']
            
            print(f"   Buscando: {row['codigo_necesidad']} - {entidad}")
            
            # Buscar V_Total en portal
            vtotal = buscar_para_entidad(driver, entidad, descripcion)
            
            if vtotal > 0:
                df_infimas.at[idx, 'V_Total'] = vtotal
                print(f"   ✓ V_Total encontrado: {vtotal}")
            else:
                print(f"   ⚠ No se encontró V_Total")
            
            # Pausa entre búsquedas para no saturar servidor
            time.sleep(2)
            
    finally:
        driver.quit()
    
    return df_infimas

def buscar_para_entidad(driver, entidad_contratante, descripcion_objetivo):
    """
    Busca V_Total en portal de compras públicas para una entidad específica.
    
    Args:
        driver: WebDriver de Selenium
        entidad_contratante (str): Nombre de la entidad
        descripcion_objetivo (str): Descripción del objeto de compra
    
    Returns:
        float: V_Total encontrado, o 0.0 si no se encuentra
    
    Flujo del proceso (5 pasos):
        1. Abrir ventana emergente de búsqueda de entidad
        2. Ingresar nombre de entidad y buscar
        3. Seleccionar primera opción de entidad (hasta 3 opciones)
        4. Buscar PAC en página principal
        5. Analizar tabla PAC y extraer V_Total
    
    Notas técnicas:
        - Usa JavaScript para clicks (evita "click intercepted")
        - Maneja múltiples ventanas (popup + principal)
        - Intenta hasta 3 opciones de entidad si la primera no tiene datos
        - Busca tabla con clases específicas: filaElemento1/filaElemento2
    """
    url_base = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/PC/buscarPACe.cpe#"
    
    try:
        print(f"      🌐 Cargando portal de compras públicas...")
        driver.get(url_base)
        wait = WebDriverWait(driver, 20)
        time.sleep(3)  # Esperar carga completa de página
        
        # ========================================================
        # PASO 1: Click "Buscar Entidad" en página principal
        # ========================================================
        print(f"      🔍 [Paso 1/5] Abriendo búsqueda de entidad...")
        try:
            # Buscar botón por atributo onclick (más confiable que por ID)
            boton_buscar_entidad = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[@onclick='botonBuscarEntidad()']")
                )
            )
            # Usar JavaScript para hacer click (evita problemas de superposición)
            driver.execute_script("arguments[0].click();", boton_buscar_entidad)
            print(f"         ✓ Ventana emergente abierta")
            
        except TimeoutException:
            print(f"         ✗ No se encontró botón 'Buscar Entidad'")
            return 0.0
        
        # ========================================================
        # Cambiar a ventana emergente
        # ========================================================
        time.sleep(2)
        ventanas = driver.window_handles
        
        if len(ventanas) < 2:
            print(f"         ✗ No se abrió ventana emergente")
            return 0.0
        
        # Cambiar foco a última ventana (la popup)
        driver.switch_to.window(ventanas[-1])
        print(f"         ✓ Enfocado en ventana emergente")
        
        # ========================================================
        # PASO 2: Ingresar entidad y buscar en popup
        # ========================================================
        print(f"      ⌨️ [Paso 2/5] Buscando entidad: '{entidad_contratante[:35]}'...")
        
        # 2a) Ingresar nombre de entidad en campo de texto
        try:
            input_empresa = wait.until(
                EC.presence_of_element_located((By.ID, "txtEmpresa"))
            )
            input_empresa.clear()
            input_empresa.send_keys(entidad_contratante)
            print(f"         ✓ Entidad ingresada")
        except TimeoutException:
            print(f"         ✗ No se encontró campo txtEmpresa")
            driver.switch_to.window(ventanas[0])
            return 0.0
        
        # 2b) Click "Buscar" en popup
        try:
            # XPath específico para botón en popup (no confundir con botón principal)
            boton_buscar_popup = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[@onclick='botonBuscar()']/img[@id='btnBuscar']")
                )
            )
            driver.execute_script("arguments[0].click();", boton_buscar_popup)
            print(f"         ✓ Búsqueda ejecutada")
        except TimeoutException:
            # Alternativa: ejecutar función JavaScript directamente
            driver.execute_script("botonBuscar();")
        
        time.sleep(3)
        
        # ========================================================
        # PASO 3: Verificar resultados y seleccionar entidad
        # ========================================================
        print(f"      📋 [Paso 3/5] Procesando resultados...")
        
        try:
            # Buscar tabla con resultados (identificada por clase filaTitulo)
            tabla_resultados = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//table[.//td[@class='filaTitulo']]")
                )
            )
            
            # Filtrar solo filas con datos (clases filaElemento1 o filaElemento2)
            filas_datos = tabla_resultados.find_elements(
                By.XPATH, ".//tr[contains(@class, 'filaElemento')]"
            )
            
            print(f"         ✓ Encontradas {len(filas_datos)} coincidencia(s)")
            
            if len(filas_datos) == 0:
                print(f"         ⚠ Sin resultados para '{entidad_contratante}'")
                driver.switch_to.window(ventanas[0])
                return 0.0
            
        except TimeoutException:
            print(f"         ✗ No se encontró tabla de resultados")
            driver.switch_to.window(ventanas[0])
            return 0.0
        
        # ========================================================
        # Probar con cada opción de entidad (hasta 3)
        # ========================================================
        max_opciones = min(len(filas_datos), 3)
        
        for idx in range(max_opciones):
            print(f"      🎯 [Opción {idx+1}/{max_opciones}] Probando entidad...")
            
            try:
                # Si no es la primera iteración, reabrir popup y repetir búsqueda
                if idx > 0:
                    print(f"         ↻ Reabriendo búsqueda...")
                    
                    # Verificar que estamos en ventana válida
                    try:
                        if len(driver.window_handles) > 0:
                            driver.switch_to.window(driver.window_handles[0])
                        else:
                            print(f"         ✗ No hay ventanas disponibles")
                            continue
                    except Exception as e:
                        print(f"         ✗ Error al cambiar ventana: {str(e)[:50]}")
                        continue
                    
                # ========================================================
                # Seleccionar la entidad (opción idx)
                # ========================================================
                fila_actual = filas_datos[idx]
                link_entidad = fila_actual.find_element(By.TAG_NAME, "a")
                nombre_entidad = link_entidad.text.strip()
                
                print(f"         → Seleccionando: {nombre_entidad[:45]}...")
                
                # Obtener atributo onclick del enlace
                # Ejemplo: "javascript:SetSelectedItem(1118627,'MANPANOR', 0);"
                onclick_attr = link_entidad.get_attribute("onclick")
                
                # Ejecutar JavaScript del onclick (cierra popup y carga datos en principal)
                driver.execute_script(onclick_attr)
                print(f"         ✓ Entidad seleccionada")
                
                # Esperar que popup se cierre automáticamente
                time.sleep(2)
                
                # Volver a ventana principal
                if len(driver.window_handles) == 1:
                    driver.switch_to.window(driver.window_handles[0])
                else:
                    driver.switch_to.window(ventanas[0])
                
                # ========================================================
                # PASO 4: Buscar PAC en página principal
                # ========================================================
                print(f"      🔍 [Paso 4/5] Buscando PAC en página principal...")
                time.sleep(2)
                
                try:
                    # Buscar botón "Buscar" en form principal (NO confundir con popup)
                    boton_buscar_pac = wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//form[@id='frmDatos']//a[@onclick='botonBuscar()' or @onclick='buscarPACe()']")
                        )
                    )
                    driver.execute_script("arguments[0].click();", boton_buscar_pac)
                    print(f"         ✓ Búsqueda PAC ejecutada")
                    
                except TimeoutException:
                    # Alternativas: ejecutar funciones JavaScript directamente
                    try:
                        driver.execute_script("botonBuscar();")
                    except:
                        try:
                            driver.execute_script("buscarPACe();")
                        except:
                            print(f"         ✗ No se pudo ejecutar búsqueda PAC")
                            continue
                
                time.sleep(3)
                
                # ========================================================
                # PASO 5: Verificar tabla PAC y extraer V_Total
                # ========================================================
                print(f"      📊 [Paso 5/5] Analizando tabla PAC...")

                try:
                    # Buscar todas las tablas en la página
                    tablas = driver.find_elements(By.TAG_NAME, "table")
                    print(f"         🔍 Encontradas {len(tablas)} tablas en la página")
                    
                    tabla_pac = None
                    
                    # Iterar sobre tablas para encontrar la de PAC
                    for tabla_num, tabla in enumerate(tablas, 1):
                        try:
                            if not tabla.is_displayed():
                                continue
                            
                            # Buscar filas con clases específicas de datos PAC
                            # (filaElemento1 y filaElemento2 se alternan en la tabla)
                            filas_elementos = tabla.find_elements(
                                By.XPATH, 
                                ".//tr[@class='filaElemento1' or @class='filaElemento2']"
                            )
                            
                            if not filas_elementos:
                                continue
                            
                            print(f"         📋 Tabla {tabla_num}: {len(filas_elementos)} registros PAC encontrados")
                            
                            # Verificar header de la tabla
                            try:
                                # Buscar celdas de título directamente
                                celdas_titulo = tabla.find_elements(By.XPATH, ".//td[@class='filaTitulo']")
                                
                                if celdas_titulo:
                                    # Concatenar texto de TODAS las celdas del header
                                    header_completo = ' '.join([cell.text for cell in celdas_titulo])
                                    
                                    # Normalizar texto (quitar acentos para comparación)
                                    header_sin_acentos = ''.join(
                                        c for c in unicodedata.normalize('NFD', header_completo)
                                        if unicodedata.category(c) != 'Mn'
                                    )
                                    header_text = header_sin_acentos.lower()
                                    
                                    print(f"            🔍 Header completo ({len(celdas_titulo)} columnas)")
                                    print(f"               Texto: '{header_text[:100]}...'")
                                    
                                    # Verificar que header contenga columnas esperadas
                                    tiene_descripcion = 'descripcion' in header_text
                                    tiene_total = 'total' in header_text or 'v. total' in header_text or 'v.total' in header_text
                                    
                                    if tiene_descripcion and tiene_total:
                                        tabla_pac = tabla
                                        print(f"         ✅ Tabla PAC identificada: Tabla {tabla_num}")
                                        break
                                    else:
                                        print(f"            ⚠ Falta: Descripción={tiene_descripcion}, Total={tiene_total}")
                                        
                            except Exception as e:
                                print(f"            ⚠ Error verificando header: {str(e)[:40]}")
                                # Fallback: Si tiene >= 5 filas, aceptar tabla
                                if len(filas_elementos) >= 5:
                                    tabla_pac = tabla
                                    print(f"         ✅ Tabla PAC identificada: Tabla {tabla_num} (por cantidad de registros)")
                                    break
                                    
                        except Exception as e:
                            continue
                    
                    if not tabla_pac:
                        print(f"         ⚠ No se encontró tabla PAC válida")
                        continue
                    
                    # Obtener filas de datos nuevamente (por si acaso)
                    filas_pac = tabla_pac.find_elements(
                        By.XPATH, 
                        ".//tr[@class='filaElemento1' or @class='filaElemento2']"
                    )
                    num_registros = len(filas_pac)
                    
                    print(f"         ✓ {num_registros} registro(s) en tabla PAC")
                    
                    if num_registros == 0:
                        print(f"         ⚠ Tabla vacía, probando siguiente opción...")
                        continue
                    
                    # ========================================================
                    # Buscar coincidencia de descripción y extraer V_Total
                    # ========================================================
                    print(f"         🔎 Buscando coincidencia de descripción...")
                    vtotal = buscar_coincidencia_descripcion_por_clase(tabla_pac, descripcion_objetivo)
                    
                    if vtotal > 0:
                        print(f"      ✅ V_Total encontrado: ${vtotal:,.2f}")
                        return vtotal
                    else:
                        print(f"         ⚠ Sin coincidencia, probando siguiente opción...")
                    
                except Exception as e:
                    print(f"         ✗ Error al analizar tabla: {str(e)[:60]}")
                    import traceback
                    traceback.print_exc()
                    continue
                
            except Exception as e:
                print(f"         ✗ Error en opción {idx+1}: {str(e)[:70]}")
                continue
        
        # Si llegamos aquí, ninguna opción funcionó
        print(f"      ⚠ Ninguna opción tuvo resultados válidos")
        return 0.0
        
    except Exception as e:
        print(f"      ✗ Error general: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return 0.0

def buscar_coincidencia_descripcion_por_clase(tabla, descripcion_objetivo):
    """
    Busca coincidencia de descripción en tabla PAC y extrae V_Total.
    
    Args:
        tabla: Elemento WebElement de Selenium (tabla PAC)
        descripcion_objetivo (str): Descripción a buscar
    
    Returns:
        float: V_Total de la fila con mejor coincidencia, o 0.0 si no hay match
    
    Algoritmo:
        1. Extrae palabras clave de descripción objetivo (ignora artículos)
        2. Para cada fila de la tabla:
           - Extrae descripción (columna 10) y V_Total (columna 14)
           - Calcula % de coincidencia de palabras
           - Guarda mejor coincidencia
        3. Si encuentra >= 30% coincidencia con V_Total > 0, retorna
        4. Si no, retorna mejor coincidencia encontrada
    
    Estructura de tabla:
        [0]=Nro, [1]=Partida, [2]=CPC, ..., [10]=Descripción, ..., [14]=V.Total
        (Total: 17 columnas)
    
    Umbrales:
        - 30%: Umbral mínimo de aceptación (flexible para textos cortos)
        - Retorna inmediatamente si encuentra >= 30% con valor > 0
    """
    try:
        # Buscar solo filas con clases de datos (filaElemento1 o filaElemento2)
        filas_datos = tabla.find_elements(
            By.XPATH, 
            ".//tr[@class='filaElemento1' or @class='filaElemento2']"
        )
        
        print(f"            📊 Analizando {len(filas_datos)} filas de datos")
        
        if len(filas_datos) == 0:
            print(f"            ⚠ No se encontraron filas con clase filaElemento1/filaElemento2")
            return 0.0
        
        # Preparar descripción objetivo (limpiar y extraer palabras clave)
        desc_limpia = descripcion_objetivo.lower().strip()
        # Palabras a ignorar (artículos, preposiciones)
        palabras_ignorar = {'de', 'del', 'la', 'el', 'los', 'las', 'para', 'con', 'en', 'y', 'a', 'un', 'una', 'por', 'sobre', 'que'}
        # Filtrar palabras > 2 caracteres y no ignoradas
        palabras_objetivo = [p for p in desc_limpia.split() if p not in palabras_ignorar and len(p) > 2]
        
        print(f"            🔍 Palabras clave: {' '.join(palabras_objetivo[:7])}")
        
        # Variables para tracking de mejor coincidencia
        mejor_coincidencia = 0
        mejor_vtotal = 0.0
        mejor_desc = ""
        mejor_fila_num = 0
        
        # Analizar cada fila de datos
        for idx, fila in enumerate(filas_datos, 1):
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                
                # Debug: mostrar columnas de primera fila
                if idx == 1:
                    print(f"            📊 Fila tiene {len(celdas)} columnas")
                
                # Verificar que tenga estructura de 17 columnas
                if len(celdas) < 15:
                    if idx == 1:
                        print(f"            ⚠ Estructura inesperada ({len(celdas)} columnas)")
                    continue
                
                # Extraer datos de columnas específicas
                # [10] = Descripción del objeto de compra
                # [14] = V. Total (valor total)
                desc_fila = celdas[10].text.lower().strip()
                vtotal_texto = celdas[14].text.strip()
                
                # Debug: mostrar primera fila como ejemplo
                if idx == 1:
                    print(f"            📝 Ejemplo fila 1:")
                    print(f"               Desc[10]: '{desc_fila[:70]}'")
                    print(f"               V.Total[14]: '{vtotal_texto}'")
                
                # Extraer palabras clave de descripción de la fila
                palabras_fila = [p for p in desc_fila.split() if p not in palabras_ignorar and len(p) > 2]
                
                # Calcular coincidencias (substring matching)
                if not palabras_objetivo or not palabras_fila:
                    continue
                
                # Contar cuántas palabras objetivo están en palabras de fila
                # (usa substring matching: "adquisicion" match "adquisiciones")
                coincidencias = sum(1 for p_obj in palabras_objetivo 
                                    if any(p_obj in p_fila or p_fila in p_obj
                                    for p_fila in palabras_fila))
                
                # Calcular porcentaje de coincidencia
                porcentaje = (coincidencias / len(palabras_objetivo)) * 100
                
                # Guardar mejor coincidencia
                if porcentaje > mejor_coincidencia:
                    mejor_coincidencia = porcentaje
                    mejor_desc = desc_fila[:60]
                    mejor_fila_num = idx
                    
                    # Intentar extraer V_Total
                    try:
                        # Limpiar formato ($, comas, USD)
                        vtotal_limpio = vtotal_texto.replace(',', '').replace('$', '').replace('USD', '').strip()
                        # Ignorar valores 0.0000
                        if vtotal_limpio and vtotal_limpio != '0.0000':
                            vtotal = float(vtotal_limpio)
                            if vtotal > 0:
                                mejor_vtotal = vtotal
                                # Mostrar coincidencias >= 30%
                                if porcentaje >= 30:
                                    print(f"            💡 Fila {idx}: {porcentaje:.0f}% coincidencia - ${vtotal:,.2f}")
                    except ValueError as e:
                        if idx == 1:
                            print(f"            ⚠ Error convirtiendo '{vtotal_texto}': {e}")
                        continue
                
                # Si encontramos >= 30% con valor válido, retornar inmediatamente
                if porcentaje >= 30 and mejor_vtotal > 0:
                    print(f"            ✅ Coincidencia aceptada: {porcentaje:.0f}%")
                    print(f"            ✅ V_Total: ${mejor_vtotal:,.2f}")
                    return mejor_vtotal
            
            except Exception as e:
                # Solo mostrar errores en primeras filas (evitar spam)
                if idx <= 2:
                    print(f"            ⚠ Error fila {idx}: {str(e)[:50]}")
                continue
        
        # Si no encontró >= 30%, reportar mejor resultado
        if mejor_coincidencia > 0:
            print(f"            💡 Mejor coincidencia: Fila {mejor_fila_num} - {mejor_coincidencia:.0f}%")
            print(f"               '{mejor_desc}'")
            if mejor_vtotal > 0:
                print(f"            ✅ Usando V_Total: ${mejor_vtotal:,.2f}")
                return mejor_vtotal
            else:
                print(f"            ⚠ Mejor coincidencia no tiene V_Total válido")
        else:
            print(f"            ❌ Sin coincidencias encontradas")
        
        return 0.0
        
    except Exception as e:
        print(f"            ✗ Error general: {str(e)[:80]}")
        import traceback
        traceback.print_exc()
        return 0.0

# =========================
# 6. CÁLCULO DE PESO
# =========================

def calcular_peso(contraindicaciones_encontradas, df_contraindicaciones):
    """
    Calcula el peso total usando la fórmula: 1 - Π(1 - P(i))
    
    Args:
        contraindicaciones_encontradas (list): Lista de contraindicaciones detectadas
        df_contraindicaciones (DataFrame): DataFrame con pesos de cada contraindicación
    
    Returns:
        float: Peso total calculado (0.0 a 1.0)
    
    Fórmula:
        Peso_total = 1 - Π(1 - P(i))
        
        Donde:
        - P(i) = peso individual de contraindicación i
        - Π = producto de todos los (1 - P(i))
    
    Ejemplo:
        Contraindicaciones: ['Soporte técnico' (0.3), 'Capacitación' (0.4)]
        Peso = 1 - (1-0.3)*(1-0.4) = 1 - 0.7*0.6 = 1 - 0.42 = 0.58 (58%)
    
    Nota:
        Si no hay contraindicaciones, retorna 0.0
    """
    if not contraindicaciones_encontradas:
        return 0.0
    
    # Inicializar producto en 1.0
    producto = 1.0
    
    # Para cada contraindicación encontrada
    for contraind in contraindicaciones_encontradas:
        # Buscar peso individual en DataFrame
        peso_row = df_contraindicaciones[
            df_contraindicaciones['contraindicacion'] == contraind
        ]
        
        if not peso_row.empty:
            peso_individual = float(peso_row.iloc[0]['peso'])
            # Multiplicar por (1 - peso_individual)
            producto *= (1 - peso_individual)
    
    # Aplicar fórmula final: 1 - producto
    peso_final = 1 - producto
    return peso_final

# =========================
# 7. PASOS 12 Y 13
# =========================

def actualizar_etapa_y_nivel_de_oportunidad():
    """
    Ejecuta los pasos 12 y 13 en una sola transacción de base de datos:

    Paso 12: Revierte la etapa a 'seleccionada' para todas las ínfimas con PAC > 0,
             garantizando que los cambios de pasos anteriores están confirmados.

    Paso 13: Asigna nivel_de_oportunidad en la tabla infimas para los códigos
             presentes en la tabla evaluaciones, según su Peso_total:
               - Nivel 1: Peso_total entre 0.00 y 0.20  (inclusive)
               - Nivel 2: Peso_total entre 0.21 y 0.50  (inclusive)
               - Nivel 3: Peso_total entre 0.51 y 1.00  (inclusive)

    Returns:
        dict: Resumen de cambios realizados con claves:
            - 'filas_etapa_actualizadas'   (int)  → registros afectados en paso 12
            - 'filas_nivel_1'              (int)  → registros asignados como nivel 1
            - 'filas_nivel_2'              (int)  → registros asignados como nivel 2
            - 'filas_nivel_3'              (int)  → registros asignados como nivel 3
            - 'total_niveles_asignados'    (int)  → total de registros con nivel asignado

    Raises:
        Exception: Hace rollback completo si ocurre cualquier error,
                   evitando estados inconsistentes en la base de datos.
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    try:
        # ── PASO 12: Revertir etapa a 'seleccionada' ──────────────────────────
        cursor.execute("""
            UPDATE infimas
            SET etapa = 'seleccionada',
                actualizado_en = NOW()
            WHERE PACdoc > 0 OR PACweb > 0
        """)
        filas_etapa = cursor.rowcount

        # ── PASO 13: Asignar nivel_de_oportunidad desde evaluaciones ──────────

        # Nivel 1 → Peso_total entre 0.00 y 0.20
        cursor.execute("""
            UPDATE infimas i
            INNER JOIN evaluaciones e ON i.codigo_necesidad = e.codigo_necesidad
            SET i.nivel_de_oportunidad = 'nivel 1',
                i.actualizado_en = NOW()
            WHERE e.Peso_total >= 0 AND e.Peso_total <= 0.20
        """)
        filas_nivel_1 = cursor.rowcount

        # Nivel 2 → Peso_total entre 0.21 y 0.50
        cursor.execute("""
            UPDATE infimas i
            INNER JOIN evaluaciones e ON i.codigo_necesidad = e.codigo_necesidad
            SET i.nivel_de_oportunidad = 'nivel 2',
                i.actualizado_en = NOW()
            WHERE e.Peso_total > 0.20 AND e.Peso_total <= 0.50
        """)
        filas_nivel_2 = cursor.rowcount

        # Nivel 3 → Peso_total entre 0.51 y 1.00
        cursor.execute("""
            UPDATE infimas i
            INNER JOIN evaluaciones e ON i.codigo_necesidad = e.codigo_necesidad
            SET i.nivel_de_oportunidad = 'nivel 3',
                i.actualizado_en = NOW()
            WHERE e.Peso_total > 0.50 AND e.Peso_total <= 1.00
        """)
        filas_nivel_3 = cursor.rowcount

        # ── Confirmar toda la transacción de una sola vez ─────────────────────
        conn.commit()

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise RuntimeError(f"Error en pasos 12/13 — se hizo rollback: {e}")

    cursor.close()
    conn.close()

    return {
        'filas_etapa_actualizadas': filas_etapa,
        'filas_nivel_1':            filas_nivel_1,
        'filas_nivel_2':            filas_nivel_2,
        'filas_nivel_3':            filas_nivel_3,
        'total_niveles_asignados':  filas_nivel_1 + filas_nivel_2 + filas_nivel_3,
    }

# =========================
# 8. ORQUESTADOR PRINCIPAL
# =========================

def main():
    """
    Función principal que orquesta todo el proceso de análisis.
    
    Flujo completo:
        [1-2]  Cargar contraindicaciones
        [3]    Obtener códigos seleccionados
        [4-6]  Buscar PAC en documentos con IA
        [7]    Validar PAC con web scraping del portal
        [8-9]  Actualizar base de datos
        [10]   Analizar contraindicaciones
        [11]   Calcular y guardar pesos
        [12]   Revertir etapa a 'seleccionada' para ínfimas con PAC > 0
        [13]   Asignar nivel_de_oportunidad según Peso_total en evaluaciones
    
    Notas:
        - Implementa delays de 60s entre códigos para evitar rate limits
        - Los pasos 8-13 se ejecutan UNA SOLA VEZ al final (no en loop)
        - Manejo robusto de errores en cada paso
    """
    # ── CONTADOR DE TIEMPO: inicio ────────────────────────────────────────────
    tiempo_inicio = time.time()
    # ─────────────────────────────────────────────────────────────────────────

    print("=" * 80)
    print("SISTEMA DE ANÁLISIS DE ÍNFIMAS - COMPRAS PÚBLICAS ECUADOR")
    print("=" * 80)
    
    # ========================================================
    # PASO 1-2: Cargar contraindicaciones
    # ========================================================
    print("\n[1] Cargando contraindicaciones...")
    contraindicaciones_list = obtener_contraindicaciones()
    df_contraindicaciones = obtener_contraindicaciones_con_peso()
    print(f"   ✓ {len(contraindicaciones_list)} contraindicaciones cargadas")
    
    # ========================================================
    # PASO 3: Códigos seleccionados
    # ========================================================
    print("\n[2] Obteniendo códigos seleccionados...")
    codigos_preseleccionados = obtener_codigos_preseleccionados()
    print(f"   ✓ {len(codigos_preseleccionados)} códigos encontrados")
    
    # ========================================================
    # PASO 4-6: Buscar PAC en documentos con IA
    # ========================================================
    print("\n[3] Inicializando servicios Google Cloud...")
    model, bucket = inicializar_servicios()
    print("   ✓ Servicios inicializados")
    
    print("\n[4] Buscando PAC en documentos...")
    codigos_pac_dict = {}

    for i, codigo in enumerate(codigos_preseleccionados, 1):
        print(f"   [{i}/{len(codigos_preseleccionados)}] {codigo}")
        pac = buscar_pac_en_documentos(bucket, codigo, model)
        codigos_pac_dict[codigo] = pac

        if pac > 0:
            print(f"   ✓ PAC encontrado: {pac}")
        else:
            print(f"   ⚠ PAC no encontrado (se asignará 0.0)")
        
        # Delay entre códigos para evitar rate limits de Google Cloud
        if i < len(codigos_preseleccionados):
            tiempo_espera = 60
            print(f"      ⏸ Esperando {tiempo_espera}s antes del siguiente código...")
            time.sleep(tiempo_espera)
    
    print("\n[5] Actualizando PAC en base de datos...")
    actualizar_pac_en_bd(codigos_pac_dict)
    print("   ✓ Base de datos actualizada")
    
    # ========================================================
    # PASO 7: Comprobación de PAC con web scraping
    # ========================================================
    print("\n[6] Obteniendo ínfimas para comprobación...")
    df_infimas = obtener_infimas_con_pac()
    print(f"   ✓ {len(df_infimas)} registros obtenidos")
    
    print("\n[7] Buscando V_Total en portal de compras públicas...")
    print("   (Este proceso puede tomar varios minutos)")
    df_infimas = buscar_vtotal_en_portal(df_infimas)
    
    # ========================================================
    # PASO 8: Actualizar PAC desde V_Total
    # ========================================================
    print("\n[8] Actualizando PAC desde V_Total...")
    actualizar_pac_desde_vtotal(df_infimas)
    print("   ✓ Base de datos actualizada")
    
    # ========================================================
    # PASO 9-10: Buscar contraindicaciones
    # ========================================================
    print("\n[9] Obteniendo códigos con PAC > 0...")
    codigos_pac_positivos = obtener_codigos_pac_mayores_cero()
    print(f"   ✓ {len(codigos_pac_positivos)} códigos con PAC > 0")
    
    print("\n[10] Analizando contraindicaciones en documentos...")
    contraindicaciones_por_codigo = {}
    
    for i, codigo in enumerate(codigos_pac_positivos.keys(), 1):
        print(f"   [{i}/{len(codigos_pac_positivos)}] {codigo}")
        contraindicaciones_encontradas = buscar_contraindicaciones_en_documentos(
            bucket, codigo, contraindicaciones_list, model
        )
        contraindicaciones_por_codigo[codigo] = contraindicaciones_encontradas
        
        if contraindicaciones_encontradas:
            print(f"   ✓ Encontradas: {', '.join(contraindicaciones_encontradas)}")
        else:
            print(f"   ⚠ No se encontraron contraindicaciones")
    
        # Delay entre códigos
        if i < len(codigos_pac_positivos):
            tiempo_espera = 60
            print(f"      ⏸ Esperando {tiempo_espera}s antes del siguiente código...")
            time.sleep(tiempo_espera)

    # ========================================================
    # PASO 11: Calcular pesos (UNA SOLA VEZ)
    # ========================================================
    print("\n[11] Calculando pesos...")
    for codigo, contraindicaciones_encontradas in contraindicaciones_por_codigo.items():
        peso = calcular_peso(contraindicaciones_encontradas, df_contraindicaciones)
        actualizar_peso_en_bd(codigo, peso, contraindicaciones_encontradas)
        print(f"   {codigo}: Peso = {peso:.4f}")

    # ========================================================
    # PASOS 12 y 13: Etapa 'seleccionada' + Nivel de oportunidad
    # ========================================================
    print("\n[12-13] Actualizando etapa y asignando niveles de oportunidad...")
    try:
        resumen = actualizar_etapa_y_nivel_de_oportunidad()

        # ── Verificación de cambios confirmados en BD ─────────────────────────
        print(f"\n   ✅ Cambios confirmados en base de datos:")
        print(f"      Paso 12 → Registros con etapa='seleccionada' actualizados : {resumen['filas_etapa_actualizadas']}")
        print(f"      Paso 13 → Nivel 1 asignado (peso  0.00 – 0.20)            : {resumen['filas_nivel_1']}")
        print(f"      Paso 13 → Nivel 2 asignado (peso  0.21 – 0.50)            : {resumen['filas_nivel_2']}")
        print(f"      Paso 13 → Nivel 3 asignado (peso  0.51 – 1.00)            : {resumen['filas_nivel_3']}")
        print(f"      ─────────────────────────────────────────────────────────")
        print(f"      Total de niveles asignados                                : {resumen['total_niveles_asignados']}")

        if resumen['filas_etapa_actualizadas'] == 0:
            print(f"\n   ⚠ Advertencia: Paso 12 no actualizó ningún registro.")
            print(f"      Verifique que existan ínfimas con PACdoc > 0 o PACweb > 0.")

        if resumen['total_niveles_asignados'] == 0:
            print(f"\n   ⚠ Advertencia: Paso 13 no asignó ningún nivel.")
            print(f"      Verifique que la tabla 'evaluaciones' tenga registros con Peso_total válido.")

    except RuntimeError as e:
        print(f"\n   ✗ {e}")
        print(f"   ⚠ Los pasos 12 y 13 NO se completaron. Revise la base de datos.")

    # ========================================================
    # Resumen final
    # ========================================================

    # ── CONTADOR DE TIEMPO: cálculo y formato ─────────────────────────────────
    tiempo_total = time.time() - tiempo_inicio
    horas   = int(tiempo_total // 3600)
    minutos = int((tiempo_total % 3600) // 60)
    segundos = int(tiempo_total % 60)
    # ─────────────────────────────────────────────────────────────────────────

    print("\n" + "=" * 80)
    print("PROCESO COMPLETADO")
    print("=" * 80)
    print(f"Códigos seleccionados:          {len(codigos_preseleccionados)}")
    print(f"Códigos con PAC > 0:            {len(codigos_pac_positivos)}")
    print(f"Códigos con contraindicaciones: {sum(1 for c in contraindicaciones_por_codigo.values() if c)}")
    print(f"Tiempo total de ejecución:      {horas:02d}h {minutos:02d}m {segundos:02d}s")
    print("=" * 80)

if __name__ == "__main__":
    main()