#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de análisis de ínfimas - Compras Públicas Ecuador
- Extracción de PAC desde documentos con IA
- Web scraping del portal de compras públicas
- Análisis de contraindicaciones
- Cálculo de pesos
"""

import os
import re
import json
import time
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

# =========================
# 1. CONFIGURACIÓN
# =========================

MYSQL_CONFIG = {
    "host": "35.225.240.246",
    "user": "root",
    "password": "Admin123%",
    "database": "gestorex",
}

GEMINI_CREDENTIALS_PATH = "src/Credentials/Clave_bucket_AIgemini.json"
BUCKET_NAME = "nexusbucket1"
CARPETA_DOCUMENTOS = "Documentos de Contratación"

# =========================
# 2. INICIALIZACIÓN
# =========================

def inicializar_servicios():
    """Inicializa VertexAI y Google Cloud Storage"""
    global BUCKET_NAME
    
    credentials = service_account.Credentials.from_service_account_file(
        GEMINI_CREDENTIALS_PATH
    )
    
    with open(GEMINI_CREDENTIALS_PATH, 'r') as f:
        creds_data = json.load(f)
        project_id = creds_data.get('project_id')
    
    # Inicializar VertexAI
    vertexai.init(
        project=project_id,
        credentials=credentials,
        location="us-east4"  # CAMBIAR de us-central1 a us-east4
    )
    
    # Inicializar Storage
    storage_client = storage.Client(
        project=project_id,
        credentials=credentials
    )
    
    #model = GenerativeModel("gemini-2.0-flash-exp")
    model = GenerativeModel("gemini-2.5-pro") # Cambiar a modelo más rápido para pruebas, ajustar según necesidades
    bucket = storage_client.bucket(BUCKET_NAME)
    
    return model, bucket

# =========================
# 3. FUNCIONES BASE DE DATOS
# =========================

def obtener_contraindicaciones():
    """Obtiene lista de contraindicaciones desde la BD"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT contraindicacion FROM contraindicaciones")
    filas = cursor.fetchall()
    cursor.close()
    conn.close()
    
    contraindicaciones = [fila[0] for fila in filas if fila[0]]
    return contraindicaciones

def obtener_contraindicaciones_con_peso():
    """Obtiene contraindicaciones con sus pesos asociados"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT contraindicacion, peso FROM contraindicaciones")
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    df = pd.DataFrame(datos)
    return df

def obtener_codigos_preseleccionados():
    """Obtiene códigos de necesidad con etapa 'preseleccionada'"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT codigo_necesidad 
        FROM infimas 
        WHERE etapa = 'preseleccionada'
    """)
    filas = cursor.fetchall()
    cursor.close()
    conn.close()
    
    codigos = [fila[0] for fila in filas if fila[0]]
    return codigos

def obtener_infimas_con_pac():
    """Obtiene infimas con PAC >= 0 para validación"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT codigo_necesidad, descripcion_objeto_compra, entidad_contratante
        FROM infimas 
        WHERE PAC >= 1
    """)
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    df = pd.DataFrame(datos)
    if not df.empty:
        df['V_Total'] = 0.0
    return df

def actualizar_pac_en_bd(codigos_pac_dict):
    """Actualiza columna PAC en la base de datos"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    for codigo, pac in codigos_pac_dict.items():
        cursor.execute("""
            UPDATE infimas 
            SET PAC = %s,
                actualizado_en = NOW()
            WHERE codigo_necesidad = %s
        """, (pac, codigo))
    
    conn.commit()
    cursor.close()
    conn.close()

def actualizar_pac_desde_vtotal(df_infimas):
    """Actualiza PAC con valores de V_Total y cambia etapa a 'seleccionada'"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    for _, row in df_infimas.iterrows():
        if row['V_Total'] > 0:
            cursor.execute("""
                UPDATE infimas 
                SET PAC = %s,
                    actualizado_en = NOW()
                WHERE codigo_necesidad = %s
            """, (row['V_Total'], row['codigo_necesidad']))
    
    # Cambiar etapa a 'seleccionada' para PAC > 0
    cursor.execute("""
        UPDATE infimas 
        SET etapa = 'seleccionada',
            actualizado_en = NOW()
        WHERE PAC > 0
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

def obtener_codigos_pac_mayores_cero():
    """Obtiene códigos de necesidad con PAC > 0"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT codigo_necesidad, PAC
        FROM infimas 
        WHERE PAC > 0
    """)
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    codigos_pac = {row['codigo_necesidad']: row['PAC'] for row in datos}
    return codigos_pac


def actualizar_peso_en_bd(codigo_necesidad, peso, contraindicaciones_encontradas):
    """
    Actualiza el peso calculado en la tabla EVALUACIONES (no en infimas)
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    # Convertir lista de contraindicaciones a string separado por comas
    justificacion = ", ".join(contraindicaciones_encontradas) if contraindicaciones_encontradas else ""
    
    #  INSERTAR O ACTUALIZAR en tabla EVALUACIONES
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

#funcion para buscar contraindicaciones
def buscar_pac_en_documentos(bucket, codigo_necesidad, model):
    """Busca el PAC en documentos del bucket usando IA"""
    carpeta_path = f"{CARPETA_DOCUMENTOS}/{codigo_necesidad}/"
    
    # Listar documentos en la carpeta
    blobs = list(bucket.list_blobs(prefix=carpeta_path))
    
    if not blobs:
        print(f"   ⚠ No se encontraron documentos para {codigo_necesidad}")
        return 0.0
    
    # Preparar prompt para IA
    documentos_contenido = []
    for blob in blobs:
        if blob.name.endswith('/'):  # Skip carpetas
            continue
        
        nombre_lower = blob.name.lower()

        if nombre_lower.endswith('.pdf'):
            blob_uri = f"gs://{BUCKET_NAME}/{blob.name}"
            documentos_contenido.append(Part.from_uri(blob_uri, mime_type="application/pdf"))
            print(f"      📄 PDF agregado: {blob.name.split('/')[-1]}")

        elif nombre_lower.endswith('.txt'):
            try:
                contenido = blob.download_as_text(encoding='utf-8')
                documentos_contenido.append(contenido)
                print(f"      📝 TXT agregado: {blob.name.split('/')[-1]}")
            except UnicodeDecodeError:
                print(f"      ⚠ TXT - No se pudo decodificar: {blob.name.split('/')[-1]}")
        
        elif nombre_lower.endswith(('.doc', '.docx')):
            print(f"      ⚠ Archivo .doc/.docx detectado (omitido): {blob.name.split('/')[-1]}") 

    if not documentos_contenido:
        print(f"   ⚠ No se pudo procesar ningún documento para {codigo_necesidad}")
        return 0.0
    
    #  PROMPT MEJORADO - Más específico y con ejemplos
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

    #  RETRY LOGIC CON EXPONENTIAL BACKOFF AUMENTADO
    max_intentos = 3
    for intento in range(max_intentos):
        try:
            contenido_completo = [prompt] + documentos_contenido
            
            print(f"      🤖 Enviando {len(documentos_contenido)} documento(s) a IA... (Intento {intento + 1}/{max_intentos})")
            
            #  AGREGAR PARÁMETROS DE CONFIGURACIÓN
            generation_config = {
                "temperature": 0.1,  # Más determinístico
                "top_p": 0.8,
                "top_k": 20,
                "max_output_tokens": 100,  # Solo necesitamos un número
            }
            
            response = model.generate_content(
                contenido_completo,
                generation_config=generation_config
            )
            response_text = response.text.strip()
            
            print(f"      💬 Respuesta IA: '{response_text}'")
            
            # Extraer solo el número
            # Limpiar respuesta (remover $, USD, comas)
            response_clean = response_text.replace('$', '').replace('USD', '').replace(',', '').strip()
            
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
            
            # Si es error 429, esperar y reintentar
            if "429" in error_msg or "Resource exhausted" in error_msg:
                if intento < max_intentos - 1:
                    tiempo_espera = (intento + 1) * 30
                    print(f"      ⏳ Error 429 - Esperando {tiempo_espera}s antes de reintentar...")
                    time.sleep(tiempo_espera)
                    continue
                else:
                    print(f"      ✗ Error 429 persiste después de {max_intentos} intentos")
                    print(f"      💡 Sugerencia: Verifica cuota en Google Cloud Console")
                    return 0.0
            else:
                # Otro tipo de error
                print(f"      ✗ Error al analizar documentos: {e}")
                return 0.0
    
    return 0.0

def buscar_contraindicaciones_en_documentos(bucket, codigo_necesidad, contraindicaciones_list, model):
    """Busca contraindicaciones en documentos del bucket usando IA"""
    carpeta_path = f"{CARPETA_DOCUMENTOS}/{codigo_necesidad}/"
    
    blobs = list(bucket.list_blobs(prefix=carpeta_path))
    
    if not blobs:
        return []
    
    documentos_contenido = []
    for blob in blobs:
        if blob.name.endswith('/'):
            continue
        
        if blob.name.lower().endswith('.pdf'):
            blob_uri = f"gs://{BUCKET_NAME}/{blob.name}"
            documentos_contenido.append(Part.from_uri(blob_uri, mime_type="application/pdf"))
        elif blob.name.lower().endswith(('.txt', '.doc', '.docx')):
            contenido = blob.download_as_text()
            documentos_contenido.append(contenido)
    
    if not documentos_contenido:
        return []
    
    # Crear prompt
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
        
        # Limpiar markdown
        if response_text.startswith("```"):
            response_text = re.sub(r"```json\n?|```\n?", "", response_text).strip()
        
        contraindicaciones_encontradas = json.loads(response_text)
        return contraindicaciones_encontradas
        
    except Exception as e:
        print(f"   ✗ Error al buscar contraindicaciones: {e}")
        return []

# =========================
# 5. WEB SCRAPING
# =========================

def configurar_driver():
    """Configura Selenium WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Modo sin interfaz
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def buscar_vtotal_en_portal(df_infimas):
    """Busca V_Total en el portal de compras públicas de Ecuador"""
    driver = configurar_driver()
    
    try:
        for idx, row in df_infimas.iterrows():
            entidad = row['entidad_contratante']
            descripcion = row['descripcion_objeto_compra']
            
            print(f"   Buscando: {row['codigo_necesidad']} - {entidad}")
            
            vtotal = buscar_para_entidad(driver, entidad, descripcion)
            
            if vtotal > 0:
                df_infimas.at[idx, 'V_Total'] = vtotal
                print(f"   ✓ V_Total encontrado: {vtotal}")
            else:
                print(f"   ⚠ No se encontró V_Total")
            
            time.sleep(2)  # Pausa para evitar saturar el servidor
            
    finally:
        driver.quit()
    
    return df_infimas

#================== Version propuesta =======================================

def buscar_para_entidad(driver, entidad_contratante, descripcion_objetivo):
    """
    Busca V_Total en portal de compras públicas
    Sigue el flujo: Buscar Entidad → Popup → Seleccionar → Buscar PAC → Extraer V_Total
    """
    url_base = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/PC/buscarPACe.cpe#"
    
    try:
        print(f"      🌐 Cargando portal de compras públicas...")
        driver.get(url_base)
        wait = WebDriverWait(driver, 20)
        time.sleep(3)  # Esperar carga completa
        
        # ========================================================
        # PASO 1: Click "Buscar Entidad" en página principal
        # ========================================================
        print(f"      🔍 [Paso 1/5] Abriendo búsqueda de entidad...")
        try:
            # Buscar botón por onclick (más confiable)
            boton_buscar_entidad = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[@onclick='botonBuscarEntidad()']")
                )
            )
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
        
        driver.switch_to.window(ventanas[-1])
        print(f"         ✓ Enfocado en ventana emergente")
        
        # ========================================================
        # PASO 2: Ingresar entidad y buscar en popup
        # ========================================================
        print(f"      ⌨️ [Paso 2/5] Buscando entidad: '{entidad_contratante[:35]}'...")
        
        # 2a) Ingresar nombre de entidad
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
            # Usar XPath específico para el botón en el popup
            boton_buscar_popup = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[@onclick='botonBuscar()']/img[@id='btnBuscar']")
                )
            )
            driver.execute_script("arguments[0].click();", boton_buscar_popup)
            print(f"         ✓ Búsqueda ejecutada")
        except TimeoutException:
            # Alternativa: ejecutar función directamente
            driver.execute_script("botonBuscar();")
        
        time.sleep(3)
        
        # ========================================================
        # PASO 3: Verificar resultados y seleccionar entidad
        # ========================================================
        print(f"      📋 [Paso 3/5] Procesando resultados...")
        
        try:
            # Buscar tabla con resultados (clase específica del header)
            tabla_resultados = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//table[.//td[@class='filaTitulo']]")
                )
            )
            
            # Filtrar solo filas con datos (tienen clase 'filaElemento')
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
                # Si no es la primera iteración, reabrir todo
                if idx > 0:
                    print(f"         ↻ Reabriendo búsqueda...")
                    
                    # ⭐ VERIFICAR QUE ESTAMOS EN UNA VENTANA VÁLIDA
                    try:
                        # Intentar volver a ventana principal
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
                
                # Obtener el onclick attribute
                onclick_attr = link_entidad.get_attribute("onclick")
                # Ejemplo: "javascript:SetSelectedItem(1118627,'MANPANOR', 0);"
                
                # Ejecutar el JavaScript directamente
                driver.execute_script(onclick_attr)
                print(f"         ✓ Entidad seleccionada")
                
                # Esperar que popup se cierre automáticamente
                time.sleep(2)
                
                # Verificar si popup se cerró
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
                    # Buscar botón "Buscar" en página principal
                    # IMPORTANTE: No confundir con el botón del popup
                    boton_buscar_pac = wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//form[@id='frmDatos']//a[@onclick='botonBuscar()' or @onclick='buscarPACe()']")
                        )
                    )
                    driver.execute_script("arguments[0].click();", boton_buscar_pac)
                    print(f"         ✓ Búsqueda PAC ejecutada")
                    
                except TimeoutException:
                    # Alternativa: ejecutar función directamente
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
                    # Buscar todas las tablas
                    tablas = driver.find_elements(By.TAG_NAME, "table")
                    print(f"         🔍 Encontradas {len(tablas)} tablas en la página")
                    
                    tabla_pac = None
                    
                    for idx_tabla, tabla in enumerate(tablas, 1):
                        try:
                            if not tabla.is_displayed():
                                continue
                            
                            # ⭐ BUSCAR FILAS CON CLASE filaElemento1 O filaElemento2
                            filas_elementos = tabla.find_elements(
                                By.XPATH, 
                                ".//tr[@class='filaElemento1' or @class='filaElemento2']"
                            )
                            
                            if not filas_elementos:
                                continue
                            
                            print(f"         📋 Tabla {idx_tabla}: {len(filas_elementos)} registros PAC encontrados")
                            
                            # ⭐ VERIFICAR HEADER BUSCANDO DIRECTAMENTE EN LAS CELDAS <td>
                            try:
                                # Buscar celdas con clase 'filaTitulo' directamente
                                celdas_titulo = tabla.find_elements(By.XPATH, ".//td[@class='filaTitulo']")
                                
                                if celdas_titulo:
                                    # Obtener texto de TODAS las celdas del header
                                    import unicodedata
                                    header_completo = ' '.join([cell.text for cell in celdas_titulo])
                                    
                                    # Normalizar (quitar acentos)
                                    header_sin_acentos = ''.join(
                                        c for c in unicodedata.normalize('NFD', header_completo)
                                        if unicodedata.category(c) != 'Mn'
                                    )
                                    header_text = header_sin_acentos.lower()
                                    
                                    print(f"            🔍 Header completo ({len(celdas_titulo)} columnas)")
                                    print(f"               Texto: '{header_text[:100]}...'")
                                    
                                    # Verificar columnas esperadas
                                    tiene_descripcion = 'descripcion' in header_text
                                    tiene_total = 'total' in header_text or 'v. total' in header_text or 'v.total' in header_text
                                    
                                    if tiene_descripcion and tiene_total:
                                        tabla_pac = tabla
                                        print(f"         ✅ Tabla PAC identificada: Tabla {idx_tabla}")
                                        break
                                    else:
                                        print(f"            ⚠ Falta: Descripción={tiene_descripcion}, Total={tiene_total}")
                                        
                            except Exception as e:
                                print(f"            ⚠ Error verificando header: {str(e)[:40]}")
                                # Si no hay header claro pero hay filas de datos, aceptar la tabla
                                if len(filas_elementos) >= 5:  # Al menos 5 registros
                                    tabla_pac = tabla
                                    print(f"         ✅ Tabla PAC identificada: Tabla {idx_tabla} (por cantidad de registros)")
                                    break
                                    
                        except Exception as e:
                            continue
                    
                    if not tabla_pac:
                        print(f"         ⚠ No se encontró tabla PAC con filas 'filaElemento1/filaElemento2'")
                        continue
                    
                    # Obtener filas de datos
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
    Busca coincidencia en tabla PAC usando filaElemento1/filaElemento2.
    """
    try:
        # ⭐ XPATH CORREGIDO - Buscar clases exactas
        filas_datos = tabla.find_elements(
            By.XPATH, 
            ".//tr[@class='filaElemento1' or @class='filaElemento2']"
        )
        
        print(f"            📊 Analizando {len(filas_datos)} filas de datos")
        
        if len(filas_datos) == 0:
            print(f"            ⚠ No se encontraron filas con clase filaElemento1/filaElemento2")
            return 0.0
        
        # Preparar descripción objetivo
        desc_limpia = descripcion_objetivo.lower().strip()
        palabras_ignorar = {'de', 'del', 'la', 'el', 'los', 'las', 'para', 'con', 'en', 'y', 'a', 'un', 'una', 'por', 'sobre', 'que'}
        palabras_objetivo = [p for p in desc_limpia.split() if p not in palabras_ignorar and len(p) > 2]
        
        print(f"            🔍 Palabras clave: {' '.join(palabras_objetivo[:7])}")
        
        mejor_coincidencia = 0
        mejor_vtotal = 0.0
        mejor_desc = ""
        mejor_fila_num = 0
        
        # Analizar cada fila
        for idx, fila in enumerate(filas_datos, 1):
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                
                # Debug primera fila
                if idx == 1:
                    print(f"            📊 Fila tiene {len(celdas)} columnas")
                
                # Verificar estructura
                if len(celdas) < 15:
                    if idx == 1:
                        print(f"            ⚠ Estructura inesperada ({len(celdas)} columnas)")
                    continue
                
                # ÍNDICES PARA 17 COLUMNAS
                desc_fila = celdas[10].text.lower().strip()  # Columna Descripción
                vtotal_texto = celdas[14].text.strip()       # Columna V. Total
                
                # Debug primera fila
                if idx == 1:
                    print(f"            📝 Ejemplo fila 1:")
                    print(f"               Desc[10]: '{desc_fila[:70]}'")
                    print(f"               V.Total[14]: '{vtotal_texto}'")
                
                # Extraer palabras clave
                palabras_fila = [p for p in desc_fila.split() if p not in palabras_ignorar and len(p) > 2]
                
                # Calcular coincidencias
                if not palabras_objetivo or not palabras_fila:
                    continue
                
                coincidencias = sum(1 for p_obj in palabras_objetivo 
                                    if any(p_obj in p_fila or p_fila in p_obj 
                                        for p_fila in palabras_fila))
                
                porcentaje = (coincidencias / len(palabras_objetivo)) * 100
                
                # Guardar mejor coincidencia
                if porcentaje > mejor_coincidencia:
                    mejor_coincidencia = porcentaje
                    mejor_desc = desc_fila[:60]
                    mejor_fila_num = idx
                    
                    # Extraer V_Total
                    try:
                        vtotal_limpio = vtotal_texto.replace(',', '').replace('$', '').replace('USD', '').strip()
                        if vtotal_limpio and vtotal_limpio != '0.0000':
                            vtotal = float(vtotal_limpio)
                            if vtotal > 0:
                                mejor_vtotal = vtotal
                                if porcentaje >= 30:
                                    print(f"            💡 Fila {idx}: {porcentaje:.0f}% coincidencia - ${vtotal:,.2f}")
                    except ValueError as e:
                        if idx == 1:
                            print(f"            ⚠ Error convirtiendo '{vtotal_texto}': {e}")
                        continue
                
                # Si encontramos >= 30%, retornar
                if porcentaje >= 30 and mejor_vtotal > 0:
                    print(f"            ✅ Coincidencia aceptada: {porcentaje:.0f}%")
                    print(f"            ✅ V_Total: ${mejor_vtotal:,.2f}")
                    return mejor_vtotal
            
            except Exception as e:
                if idx <= 2:
                    print(f"            ⚠ Error fila {idx}: {str(e)[:50]}")
                continue
        
        # Reportar mejor resultado
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

def buscar_coincidencia_descripcion(tabla, descripcion_objetivo):
    """
    Busca coincidencia en tabla PAC de 17 columnas.
    Estructura: [0]=Nro, [1]=Partida, ..., [10]=Descripción, ..., [14]=V.Total
    """
    try:
        filas = tabla.find_elements(By.TAG_NAME, "tr")
        
        # Preparar descripción objetivo
        desc_limpia = descripcion_objetivo.lower().strip()
        palabras_ignorar = {'de', 'del', 'la', 'el', 'los', 'las', 'para', 'con', 'en', 'y', 'a', 'un', 'una', 'por', 'sobre'}
        palabras_objetivo = [p for p in desc_limpia.split() if p not in palabras_ignorar and len(p) > 2]
        
        print(f"            🔍 Palabras clave: {' '.join(palabras_objetivo[:7])}")
        
        mejor_coincidencia = 0
        mejor_vtotal = 0.0
        mejor_desc = ""
        
        # Analizar cada fila (saltar header)
        for idx, fila in enumerate(filas[1:], 1):
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                
                # Debug primera fila
                if idx == 1:
                    print(f"            📊 Fila tiene {len(celdas)} columnas")
                
                # Verificar que sea tabla PAC (17 columnas)
                if len(celdas) < 15:
                    if idx == 1:
                        print(f"            ⚠ Tabla incorrecta (solo {len(celdas)} columnas)")
                    continue
                
                #  ÍNDICES CORRECTOS SEGÚN HTML
                # [10] = Descripción
                # [14] = V. Total
                desc_fila = celdas[10].text.lower().strip()
                vtotal_texto = celdas[14].text.strip()
                
                # Debug primera fila
                if idx == 1:
                    print(f"            📝 Ejemplo:")
                    print(f"               Desc[10]: '{desc_fila[:70]}...'")
                    print(f"               V.Total[14]: '{vtotal_texto}'")
                
                # Extraer palabras clave
                palabras_fila = [p for p in desc_fila.split() if p not in palabras_ignorar and len(p) > 2]
                
                # Calcular coincidencias (substring matching)
                if not palabras_objetivo:
                    continue
                
                coincidencias = sum(1 for p_obj in palabras_objetivo 
                                if any(p_obj in p_fila or p_fila in p_obj 
                                        for p_fila in palabras_fila))
                
                porcentaje = (coincidencias / len(palabras_objetivo)) * 100
                
                # Guardar mejor coincidencia
                if porcentaje > mejor_coincidencia:
                    mejor_coincidencia = porcentaje
                    mejor_desc = desc_fila[:60]
                    
                    # Extraer V_Total
                    try:
                        vtotal_limpio = vtotal_texto.replace(',', '').replace('$', '').replace('USD', '').strip()
                        if vtotal_limpio:
                            vtotal = float(vtotal_limpio)
                            if vtotal > 0:
                                mejor_vtotal = vtotal
                                if porcentaje >= 40:
                                    print(f"            ✅ Fila {idx}: {porcentaje:.0f}% - ${vtotal:,.2f}")
                    except ValueError:
                        continue
                
                # Si encontramos >= 40%, retornar
                if porcentaje >= 40 and mejor_vtotal > 0:
                    print(f"            ✅ Coincidencia aceptada: {porcentaje:.0f}%")
                    return mejor_vtotal
            
            except Exception as e:
                if idx == 1:
                    print(f"            ⚠ Error fila: {str(e)[:50]}")
                continue
        
        # Reportar mejor resultado
        if mejor_coincidencia > 0:
            print(f"            💡 Mejor: {mejor_coincidencia:.0f}% - '{mejor_desc}...'")
            if mejor_vtotal > 0:
                print(f"            ✅ Usando: ${mejor_vtotal:,.2f}")
                return mejor_vtotal
        else:
            print(f"            ❌ Sin coincidencias")
        
        return 0.0
        
    except Exception as e:
        print(f"            ✗ Error: {str(e)[:80]}")
        return 0.0

# =========================
# 6. CÁLCULO DE PESO
# =========================

def calcular_peso(contraindicaciones_encontradas, df_contraindicaciones):
    """Calcula el peso usando la fórmula: 1 - Π(1 - P(i))"""
    if not contraindicaciones_encontradas:
        return 0.0
    
    producto = 1.0
    
    for contraind in contraindicaciones_encontradas:
        peso_row = df_contraindicaciones[
            df_contraindicaciones['contraindicacion'] == contraind
        ]
        
        if not peso_row.empty:
            peso_individual = float(peso_row.iloc[0]['peso'])
            producto *= (1 - peso_individual)
    
    peso_final = 1 - producto
    return peso_final

# =========================
# 7. ORQUESTADOR PRINCIPAL
# =========================

def main():
    print("=" * 80)
    print("SISTEMA DE ANÁLISIS DE ÍNFIMAS - COMPRAS PÚBLICAS ECUADOR")
    print("=" * 80)
    
    # Paso 1-2: Cargar contraindicaciones
    print("\n[1] Cargando contraindicaciones...")
    contraindicaciones_list = obtener_contraindicaciones()
    df_contraindicaciones = obtener_contraindicaciones_con_peso()
    print(f"   ✓ {len(contraindicaciones_list)} contraindicaciones cargadas")
    
    # Paso 3: Códigos preseleccionados
    print("\n[2] Obteniendo códigos preseleccionados...")
    codigos_preseleccionados = obtener_codigos_preseleccionados()
    print(f"   ✓ {len(codigos_preseleccionados)} códigos encontrados")
    
    # Paso 4-6: Buscar PAC en documentos con IA
    print("\n[3] Inicializando servicios Google Cloud...")
    model, bucket = inicializar_servicios()
    print("   ✓ Servicios inicializados")
    
    #Original 
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
        
        #  CAMBIO: Delay mucho más largo (60 segundos)
        if i < len(codigos_preseleccionados):
            tiempo_espera = 60
            print(f"      ⏸ Esperando {tiempo_espera}s antes del siguiente código...")
            time.sleep(tiempo_espera)
    
    print("\n[5] Actualizando PAC en base de datos...")
    actualizar_pac_en_bd(codigos_pac_dict)
    print("   ✓ Base de datos actualizada")
    
    # Paso 7: Comprobación de PAC con web scraping
    print("\n[6] Obteniendo ínfimas para comprobación...")
    df_infimas = obtener_infimas_con_pac()
    print(f"   ✓ {len(df_infimas)} registros obtenidos")
    
    print("\n[7] Buscando V_Total en portal de compras públicas...")
    print("   (Este proceso puede tomar varios minutos)")
    df_infimas = buscar_vtotal_en_portal(df_infimas)
    
    print("\n[8] Actualizando PAC desde V_Total...")
    actualizar_pac_desde_vtotal(df_infimas)
    print("   ✓ Base de datos actualizada")
    
    # Paso 8-11: Buscar contraindicaciones
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
    
        if i < len(codigos_pac_positivos):
            tiempo_espera = 60
            print(f"      ⏸ Esperando {tiempo_espera}s antes del siguiente código...")
            time.sleep(tiempo_espera)

    # Paso 12: Calcular pesos
    print("\n[11] Calculando pesos...")
    for codigo, contraindicaciones_encontradas in contraindicaciones_por_codigo.items():
        peso = calcular_peso(contraindicaciones_encontradas, df_contraindicaciones)
    #  PASAR TAMBIÉN LAS CONTRAINDICACIONES
        actualizar_peso_en_bd(codigo, peso, contraindicaciones_encontradas)
        print(f"   {codigo}: Peso = {peso:.4f}")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("PROCESO COMPLETADO")
    print("=" * 80)
    print(f"Códigos preseleccionados:      {len(codigos_preseleccionados)}")
    print(f"Códigos con PAC > 0:           {len(codigos_pac_positivos)}")
    print(f"Códigos con contraindicaciones: {sum(1 for c in contraindicaciones_por_codigo.values() if c)}")
    print("=" * 80)

if __name__ == "__main__":
    main()