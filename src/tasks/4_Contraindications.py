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
        location="us-central1"
    )
    
    # Inicializar Storage
    storage_client = storage.Client(
        project=project_id,
        credentials=credentials
    )
    
    model = GenerativeModel("gemini-2.0-flash-exp")
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
        WHERE PAC >= 0
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

def actualizar_peso_en_bd(codigo_necesidad, peso):
    """Actualiza el peso calculado en la BD"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE infimas 
        SET Peso = %s,
            actualizado_en = NOW()
        WHERE codigo_necesidad = %s
    """, (peso, codigo_necesidad))
    
    conn.commit()
    cursor.close()
    conn.close()

# =========================
# 4. FUNCIONES DE BUCKET/IA
# =========================

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
        
        # Descargar y procesar según tipo
        if blob.name.lower().endswith('.pdf'):
            # Para PDFs, usar Part de Gemini
            blob_uri = f"gs://{BUCKET_NAME}/{blob.name}"
            documentos_contenido.append(Part.from_uri(blob_uri, mime_type="application/pdf"))
        elif blob.name.lower().endswith(('.txt', '.doc', '.docx')):
            contenido = blob.download_as_text()
            documentos_contenido.append(contenido)
    
    if not documentos_contenido:
        return 0.0
    
    # Crear prompt
    prompt = f"""
Analiza los documentos proporcionados del código de necesidad {codigo_necesidad}.

Busca información sobre:
- Plan Anual de Contratación (PAC)
- Partida presupuestaria
- Cantidad total asignada para esta necesidad específica
- Presupuesto referencial
- Monto total

Responde ÚNICAMENTE con un número decimal que represente el monto encontrado.
Si no encuentras ningún monto o presupuesto, responde solo: 0.0

Ejemplos de respuesta válida:
15000.50
1234567.89
0.0

NO incluyas símbolos de moneda, texto adicional ni explicaciones.
"""

    try:
        # Combinar prompt con documentos
        contenido_completo = [prompt] + documentos_contenido
        
        response = model.generate_content(contenido_completo)
        response_text = response.text.strip()
        
        # Extraer solo el número
        match = re.search(r'[\d.]+', response_text)
        if match:
            pac = float(match.group())
            return pac
        return 0.0
        
    except Exception as e:
        print(f"   ✗ Error al analizar documentos: {e}")
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

def buscar_para_entidad(driver, entidad_contratante, descripcion_objetivo):
    """Busca V_Total para una entidad específica"""
    url_base = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/PC/buscarPACe.cpe#"
    
    try:
        driver.get(url_base)
        wait = WebDriverWait(driver, 10)
        
        # Paso a) Click en botón buscar entidad
        boton_buscar_entidad = wait.until(
            EC.element_to_be_clickable((By.ID, "botonBuscarEntidad"))
        )
        boton_buscar_entidad.click()
        
        # Cambiar a la ventana emergente
        time.sleep(1)
        ventanas = driver.window_handles
        if len(ventanas) > 1:
            driver.switch_to.window(ventanas[-1])
        
        # Paso b) Ingresar nombre de entidad
        input_empresa = wait.until(
            EC.presence_of_element_located((By.NAME, "txtEmpresa"))
        )
        input_empresa.clear()
        input_empresa.send_keys(entidad_contratante)
        
        # Paso c) Click en buscar
        boton_buscar = driver.find_element(By.ID, "botonBuscar")
        boton_buscar.click()
        
        time.sleep(2)
        
        # Paso d) Seleccionar primera opción de entidad
        try:
            tabla_resultados = driver.find_element(By.TAG_NAME, "table")
            filas = tabla_resultados.find_elements(By.TAG_NAME, "tr")
            
            if len(filas) <= 1:  # Solo header
                driver.switch_to.window(ventanas[0])
                return 0.0
            
            # Intentar con cada opción
            for i in range(1, min(len(filas), 4)):  # Hasta 3 opciones
                try:
                    # Volver a abrir ventana emergente
                    if i > 1:
                        driver.switch_to.window(ventanas[0])
                        boton_buscar_entidad = wait.until(
                            EC.element_to_be_clickable((By.ID, "botonBuscarEntidad"))
                        )
                        boton_buscar_entidad.click()
                        time.sleep(1)
                        driver.switch_to.window(ventanas[-1])
                        input_empresa = wait.until(
                            EC.presence_of_element_located((By.NAME, "txtEmpresa"))
                        )
                        input_empresa.clear()
                        input_empresa.send_keys(entidad_contratante)
                        boton_buscar = driver.find_element(By.ID, "botonBuscar")
                        boton_buscar.click()
                        time.sleep(2)
                        tabla_resultados = driver.find_element(By.TAG_NAME, "table")
                        filas = tabla_resultados.find_elements(By.TAG_NAME, "tr")
                    
                    # Seleccionar opción i
                    fila_entidad = filas[i]
                    link_seleccionar = fila_entidad.find_element(By.TAG_NAME, "a")
                    link_seleccionar.click()
                    
                    # Volver a ventana principal
                    time.sleep(1)
                    driver.switch_to.window(ventanas[0])
                    
                    # Paso e) Buscar PAC
                    boton_buscar_pac = wait.until(
                        EC.element_to_be_clickable((By.ID, "botonBuscar"))
                    )
                    boton_buscar_pac.click()
                    
                    time.sleep(2)
                    
                    # Paso f) Verificar si hay resultados
                    tabla_pac = driver.find_element(By.ID, "tablaPAC")  # Ajustar ID según página real
                    filas_pac = tabla_pac.find_elements(By.TAG_NAME, "tr")
                    
                    if len(filas_pac) > 1:  # Hay datos
                        # Paso III) Buscar coincidencia de descripción
                        vtotal = buscar_coincidencia_descripcion(tabla_pac, descripcion_objetivo)
                        if vtotal > 0:
                            return vtotal
                    
                except Exception as e:
                    continue
            
            return 0.0
            
        except NoSuchElementException:
            driver.switch_to.window(ventanas[0])
            return 0.0
        
    except TimeoutException:
        print(f"   ✗ Timeout al buscar entidad")
        return 0.0
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return 0.0

def buscar_coincidencia_descripcion(tabla, descripcion_objetivo):
    """Busca coincidencia en descripciones y retorna V_Total"""
    filas = tabla.find_elements(By.TAG_NAME, "tr")
    
    descripcion_limpia = descripcion_objetivo.lower().strip()
    
    for fila in filas[1:]:  # Saltar header
        celdas = fila.find_elements(By.TAG_NAME, "td")
        
        if len(celdas) < 3:
            continue
        
        desc_fila = celdas[0].text.lower().strip()  # Columna Descripción
        vtotal_texto = celdas[2].text.strip()  # Columna V.Total
        
        # Calcular similitud simple
        palabras_objetivo = set(descripcion_limpia.split())
        palabras_fila = set(desc_fila.split())
        
        coincidencias = len(palabras_objetivo.intersection(palabras_fila))
        
        if coincidencias >= len(palabras_objetivo) * 0.6:  # 60% coincidencia
            try:
                vtotal = float(vtotal_texto.replace(',', '').replace('$', ''))
                return vtotal
            except:
                continue
    
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
    
    # Paso 12: Calcular pesos
    print("\n[11] Calculando pesos...")
    for codigo, contraindicaciones_encontradas in contraindicaciones_por_codigo.items():
        peso = calcular_peso(contraindicaciones_encontradas, df_contraindicaciones)
        actualizar_peso_en_bd(codigo, peso)
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