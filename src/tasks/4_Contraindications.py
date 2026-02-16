"""
Script para gestión de ínfimas - Búsqueda de PAC y evaluación de contraindicaciones
Autor: Sistema Automatizado
Fecha: 2026
"""

import mysql.connector
from google.cloud import storage
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os
import json
from typing import List, Dict, Tuple
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GestorInfimas:
    """Clase principal para gestionar el procesamiento de ínfimas"""
    
<<<<<<< HEAD
    def __init__(self):
        """Inicializa las conexiones y configuraciones"""
        # Credenciales de base de datos
        self.db_config = {
            'host': '35.225.240.246',
            'user': 'root',
            'password': 'Admin123%',
            'database': 'gestorex'
        }
        
        # Configuración de Google Cloud
        self.credentials_path = 'src/Credentials/Clave_bucket_AIgemini.json'
        self.bucket_name = 'nexusbucket1'
        
        # Variables de clase
        self.connection = None
        self.storage_client = None
        self.bucket = None
        self.genai_model = None
        
        # Variables de datos
        self.lista_contraindicaciones = []  # Paso 1
        self.tabla_contraindicaciones_pesos = {}  # Paso 2
        self.codigos_preseleccionados = []  # Paso 3
        self.diccionario_pac = {}  # Paso 4
        self.infimas = []  # Paso 7.I
        self.diccionario_pac_mayor_cero = {}  # Paso 8
        self.contraindicaciones_encontradas = {}  # Paso 9
        
    def conectar_base_datos(self):
        """Establece conexión con la base de datos MySQL"""
        try:
            self.connection = mysql.connector.connect(**self.db_config)
            logger.info("Conexión a base de datos establecida exitosamente")
            return True
        except mysql.connector.Error as err:
            logger.error(f"Error al conectar a la base de datos: {err}")
            return False
    
    def conectar_google_cloud(self):
        """Establece conexión con Google Cloud Storage y configura Gemini AI"""
        try:
            # Configurar credenciales
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path
            
            # Inicializar Storage Client
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(self.bucket_name)
            
            # Configurar Gemini AI
            genai.configure(api_key=self._get_api_key_from_credentials())
            self.genai_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            logger.info("Conexión a Google Cloud y Gemini AI establecida exitosamente")
            return True
        except Exception as e:
            logger.error(f"Error al conectar con Google Cloud: {e}")
            return False
    
    def _get_api_key_from_credentials(self):
        """Obtiene la API key del archivo de credenciales"""
        try:
            with open(self.credentials_path, 'r') as f:
                creds = json.load(f)
                # Nota: Ajustar según la estructura real del archivo JSON
                # Si usa service account, puede necesitar configuración diferente
                return creds.get('api_key', '')
        except Exception as e:
            logger.warning(f"No se pudo obtener API key del archivo: {e}")
            # Alternativamente, configurar directamente si está en variable de entorno
            return os.environ.get('GEMINI_API_KEY', '')
    
    def paso_1_cargar_contraindicaciones(self):
        """
        Paso 1: Crear lista de contraindicaciones desde la base de datos
        """
        logger.info("Ejecutando Paso 1: Cargando contraindicaciones...")
        try:
            cursor = self.connection.cursor()
            query = "SELECT contraindicacion FROM contraindicaciones"
            cursor.execute(query)
            
            self.lista_contraindicaciones = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            logger.info(f"Paso 1 completado: {len(self.lista_contraindicaciones)} contraindicaciones cargadas")
            return True
        except Exception as e:
            logger.error(f"Error en Paso 1: {e}")
            return False
    
    def paso_2_cargar_contraindicaciones_pesos(self):
        """
        Paso 2: Crear tabla de contraindicaciones con pesos
        """
        logger.info("Ejecutando Paso 2: Cargando contraindicaciones con pesos...")
        try:
            cursor = self.connection.cursor()
            query = "SELECT contraindicacion, peso FROM contraindicaciones"
            cursor.execute(query)
            
            self.tabla_contraindicaciones_pesos = {row[0]: float(row[1]) for row in cursor.fetchall()}
            cursor.close()
            
            logger.info(f"Paso 2 completado: {len(self.tabla_contraindicaciones_pesos)} pesos cargados")
            return True
        except Exception as e:
            logger.error(f"Error en Paso 2: {e}")
            return False
    
    def paso_3_cargar_codigos_preseleccionados(self):
        """
        Paso 3: Obtener códigos de necesidad en etapa 'seleccionada'
        """
        logger.info("Ejecutando Paso 3: Cargando códigos seleccionados...")
        try:
            cursor = self.connection.cursor()
            query = "SELECT codigo_necesidad FROM infimas WHERE etapa = 'seleccionada'"
            cursor.execute(query)
            
            self.codigos_preseleccionados = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            logger.info(f"Paso 3 completado: {len(self.codigos_preseleccionados)} códigos seleccionados")
            return True
        except Exception as e:
            logger.error(f"Error en Paso 3: {e}")
            return False
    
    def paso_4_inicializar_diccionario_pac(self):
        """
        Paso 4: Inicializar diccionario de códigos de necesidad y PAC
        """
        logger.info("Ejecutando Paso 4: Inicializando diccionario PAC...")
        try:
            cursor = self.connection.cursor()
            query = "SELECT codigo_necesidad FROM infimas WHERE etapa = 'seleccionada'"
            cursor.execute(query)
            
            # Inicializar con PAC = 0.0
            self.diccionario_pac = {row[0]: 0.0 for row in cursor.fetchall()}
            cursor.close()
            
            logger.info(f"Paso 4 completado: {len(self.diccionario_pac)} códigos inicializados")
            return True
        except Exception as e:
            logger.error(f"Error en Paso 4: {e}")
            return False
    
    def paso_5_buscar_pac_con_ia(self, codigo_necesidad: str) -> float:
        """
        Paso 5: Buscar PAC en documentos usando Gemini AI
        
        Args:
            codigo_necesidad: Código de la necesidad a analizar
            
        Returns:
            float: Monto del PAC encontrado o 0.0 si no se encuentra
        """
        logger.info(f"Ejecutando Paso 5 para código: {codigo_necesidad}")
        try:
            # Obtener documentos de la carpeta
            prefix = f"Documentos de Contratación/{codigo_necesidad}/"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            
            if not blobs:
                logger.warning(f"No se encontraron documentos para {codigo_necesidad}")
                return 0.0
            
            # Procesar cada documento
            for blob in blobs:
                if blob.name.endswith('/'):  # Ignorar carpetas
                    continue
                
                try:
                    # Descargar contenido del documento
                    contenido = blob.download_as_text()
                    
                    # Preparar prompt para Gemini
                    prompt = f"""
                    Analiza el siguiente documento de contratación y busca información sobre:
                    - Plan Anual de Contratación (PAC)
                    - Partida presupuestaria
                    - Presupuesto asignado para esta necesidad específica
                    
                    Documento:
                    {contenido[:10000]}  # Limitar a primeros 10000 caracteres
                    
                    INSTRUCCIONES:
                    1. Busca cualquier mención al presupuesto, PAC, o partida presupuestaria
                    2. Extrae SOLO la cifra numérica del presupuesto total asignado
                    3. Responde ÚNICAMENTE con el número (sin símbolos de moneda, sin texto adicional)
                    4. Si no encuentras información presupuestaria, responde: "0"
                    
                    Respuesta (solo el número):
                    """
                    
                    # Consultar a Gemini
                    response = self.genai_model.generate_content(prompt)
                    pac_texto = response.text.strip()
                    
                    # Intentar convertir a float
                    try:
                        pac_valor = float(pac_texto.replace(',', '').replace('$', ''))
                        if pac_valor > 0:
                            logger.info(f"PAC encontrado para {codigo_necesidad}: {pac_valor}")
                            return pac_valor
                    except ValueError:
                        continue
                        
                except Exception as e:
                    logger.warning(f"Error procesando blob {blob.name}: {e}")
                    continue
            
            logger.info(f"No se encontró PAC para {codigo_necesidad}")
            return 0.0
            
        except Exception as e:
            logger.error(f"Error en Paso 5 para {codigo_necesidad}: {e}")
            return 0.0
    
    def paso_5_y_6_procesar_todos_pac(self):
        """
        Pasos 5 y 6: Procesar todos los códigos seleccionados y actualizar BD
        """
        logger.info("Ejecutando Pasos 5 y 6: Procesando todos los PAC...")
        
        for codigo in self.codigos_preseleccionados:
            pac = self.paso_5_buscar_pac_con_ia(codigo)
            self.diccionario_pac[codigo] = pac
        
        # Actualizar base de datos
        try:
            cursor = self.connection.cursor()
            for codigo, pac in self.diccionario_pac.items():
                query = "UPDATE infimas SET PAC = %s WHERE codigo_necesidad = %s"
                cursor.execute(query, (pac, codigo))
            
            self.connection.commit()
            cursor.close()
            logger.info("Paso 6 completado: PACs actualizados en la base de datos")
            return True
        except Exception as e:
            logger.error(f"Error actualizando PACs en BD: {e}")
            return False
    
    def paso_7_I_cargar_infimas_pac_valido(self):
        """
        Paso 7.I: Cargar ínfimas con PAC >= 0
        """
        logger.info("Ejecutando Paso 7.I: Cargando ínfimas con PAC válido...")
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = """
                SELECT codigo_necesidad, descripcion_objeto_compra, entidad_contratante, PAC
                FROM infimas 
                WHERE PAC >= 0
            """
            cursor.execute(query)
            
            self.infimas = []
            for row in cursor.fetchall():
                infima = {
                    'codigo_necesidad': row['codigo_necesidad'],
                    'descripcion_objeto_compra': row['descripcion_objeto_compra'],
                    'entidad_contratante': row['entidad_contratante'],
                    'PAC': row['PAC'],
                    'V_Total': 0.0
                }
                self.infimas.append(infima)
            
            cursor.close()
            logger.info(f"Paso 7.I completado: {len(self.infimas)} ínfimas cargadas")
            return True
        except Exception as e:
            logger.error(f"Error en Paso 7.I: {e}")
            return False
    
    def paso_7_II_buscar_en_compraspublicas(self, infima: Dict) -> float:
        """
        Paso 7.II: Buscar en portal de compras públicas
        
        Args:
            infima: Diccionario con datos de la ínfima
            
        Returns:
            float: V_Total encontrado o 0.0
        """
        logger.info(f"Buscando en compras públicas: {infima['entidad_contratante']}")
        
        driver = None
        try:
            # Configurar Selenium
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            driver = webdriver.Chrome(options=options)
            
            # a) Ir a la página principal
            url_principal = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/PC/buscarPACe.cpe#"
            driver.get(url_principal)
            time.sleep(2)
            
            # Buscar y hacer clic en botonBuscarEntidad
            wait = WebDriverWait(driver, 10)
            boton_buscar_entidad = wait.until(
                EC.element_to_be_clickable((By.ID, "botonBuscarEntidad()"))
            )
            boton_buscar_entidad.click()
            time.sleep(2)
            
            # Cambiar a la ventana emergente
            ventanas = driver.window_handles
            driver.switch_to.window(ventanas[-1])
            
            # b) Ingresar nombre de entidad
            input_empresa = wait.until(
                EC.presence_of_element_located((By.NAME, "txtEmpresa"))
            )
            input_empresa.clear()
            input_empresa.send_keys(infima['entidad_contratante'])
            time.sleep(1)
            
            # c) Buscar entidad
            boton_buscar = driver.find_element(By.ID, "botonBuscar()")
            boton_buscar.click()
            time.sleep(3)
            
            # d) Verificar si hay resultados y seleccionar
            opciones_encontradas = self._obtener_opciones_entidad(driver)
            
            if not opciones_encontradas:
                logger.warning(f"No se encontraron opciones para: {infima['entidad_contratante']}")
                return 0.0
            
            # Intentar con cada opción disponible
            for idx, opcion in enumerate(opciones_encontradas):
                try:
                    # Seleccionar opción
                    opcion.click()
                    time.sleep(1)
                    
                    # Volver a ventana principal
                    driver.switch_to.window(ventanas[0])
                    time.sleep(2)
                    
                    # e) Buscar PAC
                    boton_buscar_pac = wait.until(
                        EC.element_to_be_clickable((By.ID, "botonBuscar()"))
                    )
                    boton_buscar_pac.click()
                    time.sleep(3)
                    
                    # f) Verificar si aparece tabla con datos
                    v_total = self._paso_7_III_buscar_coincidencia(driver, infima)
                    
                    if v_total > 0:
                        logger.info(f"V_Total encontrado: {v_total}")
                        return v_total
                    
                    # Si no se encontró, intentar con siguiente opción
                    if idx < len(opciones_encontradas) - 1:
                        # Volver a abrir ventana de búsqueda
                        driver.get(url_principal)
                        time.sleep(2)
                        boton_buscar_entidad = wait.until(
                            EC.element_to_be_clickable((By.ID, "botonBuscarEntidad()"))
                        )
                        boton_buscar_entidad.click()
                        time.sleep(2)
                        driver.switch_to.window(driver.window_handles[-1])
                        
                        input_empresa = wait.until(
                            EC.presence_of_element_located((By.NAME, "txtEmpresa"))
                        )
                        input_empresa.clear()
                        input_empresa.send_keys(infima['entidad_contratante'])
                        time.sleep(1)
                        
                        boton_buscar = driver.find_element(By.ID, "botonBuscar()")
                        boton_buscar.click()
                        time.sleep(3)
                        
                        opciones_encontradas = self._obtener_opciones_entidad(driver)
                    
                except Exception as e:
                    logger.warning(f"Error con opción {idx}: {e}")
                    continue
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error en búsqueda de compras públicas: {e}")
            return 0.0
        finally:
            if driver:
                driver.quit()
    
    def _obtener_opciones_entidad(self, driver) -> List:
        """Obtiene las opciones de entidades de la tabla de resultados"""
        try:
            # Buscar tabla de resultados
            tabla = driver.find_element(By.TAG_NAME, "table")
            filas = tabla.find_elements(By.TAG_NAME, "tr")[1:]  # Saltar encabezado
            
            opciones = []
            for fila in filas:
                try:
                    link = fila.find_element(By.TAG_NAME, "a")
                    opciones.append(link)
                except:
                    continue
            
            return opciones
        except:
            return []
    
    def _paso_7_III_buscar_coincidencia(self, driver, infima: Dict) -> float:
        """
        Paso 7.III: Buscar coincidencia en tabla y obtener V_Total
        """
        try:
            # Buscar tabla de PAC
            tabla = driver.find_element(By.TAG_NAME, "table")
            filas = tabla.find_elements(By.TAG_NAME, "tr")[1:]  # Saltar encabezado
            
            if not filas:
                return 0.0
            
            descripcion_buscar = infima['descripcion_objeto_compra'].lower()
            
            for fila in filas:
                try:
                    columnas = fila.find_elements(By.TAG_NAME, "td")
                    if len(columnas) < 3:
                        continue
                    
                    descripcion_tabla = columnas[0].text.lower()  # Columna Descripción
                    v_total_texto = columnas[-1].text  # Columna V.Total
                    
                    # Comparar descripciones
                    if self._hay_coincidencia_significativa(descripcion_buscar, descripcion_tabla):
                        # Extraer valor numérico
                        v_total = float(v_total_texto.replace(',', '').replace('$', '').strip())
                        return v_total
                        
                except Exception as e:
                    continue
=======
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
>>>>>>> f3ebe4d5fdd9bd8cd6ecdf6cc3a9cbb276ab35ff
            
        except TimeoutException:
            print(f"         ✗ No se encontró botón 'Buscar Entidad'")
            return 0.0
<<<<<<< HEAD
            
        except Exception as e:
            logger.warning(f"Error buscando coincidencia: {e}")
            return 0.0
    
    def _hay_coincidencia_significativa(self, desc1: str, desc2: str) -> bool:
        """
        Determina si hay coincidencia significativa entre dos descripciones
        """
        # Dividir en palabras
        palabras1 = set(desc1.split())
        palabras2 = set(desc2.split())
        
        # Eliminar palabras comunes
        palabras_comunes = {'de', 'del', 'la', 'el', 'los', 'las', 'para', 'por', 'con', 'y', 'en'}
        palabras1 = palabras1 - palabras_comunes
        palabras2 = palabras2 - palabras_comunes
        
        # Calcular intersección
        interseccion = palabras1.intersection(palabras2)
        
        # Considerar significativa si al menos 60% de palabras coinciden
        if len(palabras1) == 0:
            return False
        
        porcentaje = len(interseccion) / len(palabras1)
        return porcentaje >= 0.6
    
    def paso_7_IV_procesar_todas_infimas(self):
        """
        Paso 7.IV: Procesar todas las ínfimas y actualizar BD
        """
        logger.info("Ejecutando Paso 7.IV: Procesando todas las ínfimas...")
        
        for infima in self.infimas:
            v_total = self.paso_7_II_buscar_en_compraspublicas(infima)
            infima['V_Total'] = v_total
        
        # Actualizar base de datos
        try:
            cursor = self.connection.cursor()
            
            for infima in self.infimas:
                if infima['V_Total'] > 0:
                    # Actualizar PAC con V_Total
                    query_pac = """
                        UPDATE infimas 
                        SET PAC = %s 
                        WHERE codigo_necesidad = %s
                    """
                    cursor.execute(query_pac, (infima['V_Total'], infima['codigo_necesidad']))
                    
                    # Cambiar etapa a 'seleccionada' si PAC > 0
                    query_etapa = """
                        UPDATE infimas 
                        SET etapa = 'seleccionada' 
                        WHERE codigo_necesidad = %s AND PAC > 0
                    """
                    cursor.execute(query_etapa, (infima['codigo_necesidad'],))
            
            self.connection.commit()
            cursor.close()
            logger.info("Paso 7.IV completado: Base de datos actualizada")
            return True
        except Exception as e:
            logger.error(f"Error en Paso 7.IV: {e}")
            return False
    
    def paso_8_crear_diccionario_pac_mayor_cero(self):
        """
        Paso 8: Crear diccionario de códigos con PAC > 0
        """
        logger.info("Ejecutando Paso 8: Creando diccionario PAC > 0...")
        try:
            cursor = self.connection.cursor()
            query = """
                SELECT codigo_necesidad, PAC 
                FROM infimas 
                WHERE PAC > 0
            """
            cursor.execute(query)
            
            self.diccionario_pac_mayor_cero = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.close()
            
            logger.info(f"Paso 8 completado: {len(self.diccionario_pac_mayor_cero)} códigos con PAC > 0")
            return True
        except Exception as e:
            logger.error(f"Error en Paso 8: {e}")
            return False
=======
        
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
>>>>>>> f3ebe4d5fdd9bd8cd6ecdf6cc3a9cbb276ab35ff
    
    def paso_9_inicializar_contraindicaciones_encontradas(self):
        """
        Paso 9: Inicializar variable para contraindicaciones encontradas
        """
        logger.info("Ejecutando Paso 9: Inicializando contraindicaciones encontradas...")
        self.contraindicaciones_encontradas = {}
        logger.info("Paso 9 completado")
        return True
    
    def paso_10_buscar_contraindicaciones_con_ia(self, codigo_necesidad: str) -> List[str]:
        """
        Paso 10: Buscar contraindicaciones en documentos usando Gemini AI
        
        Args:
            codigo_necesidad: Código de la necesidad a analizar
            
        Returns:
            List[str]: Lista de contraindicaciones encontradas
        """
        logger.info(f"Ejecutando Paso 10 para código: {codigo_necesidad}")
        try:
            # Obtener documentos de la carpeta
            prefix = f"Documentos de Contratación/{codigo_necesidad}/"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            
            if not blobs:
                logger.warning(f"No se encontraron documentos para {codigo_necesidad}")
                return []
            
            contraindicaciones_encontradas = set()
            
            # Procesar cada documento
            for blob in blobs:
                if blob.name.endswith('/'):  # Ignorar carpetas
                    continue
                
                try:
                    # Descargar contenido del documento
                    contenido = blob.download_as_text()
                    
                    # Crear lista de contraindicaciones para el prompt
                    lista_contraindicaciones_texto = ", ".join(self.lista_contraindicaciones)
                    
                    # Preparar prompt para Gemini
                    prompt = f"""
                    Analiza el siguiente documento de contratación y busca menciones de contraindicaciones.
                    
                    Lista de contraindicaciones a buscar:
                    {lista_contraindicaciones_texto}
                    
                    Documento:
                    {contenido[:15000]}  # Limitar para no exceder tokens
                    
                    INSTRUCCIONES:
                    1. Busca en el documento cualquier mención, referencia o descripción de las contraindicaciones listadas
                    2. Puede haber sinónimos o descripciones similares
                    3. Responde ÚNICAMENTE con las contraindicaciones encontradas, separadas por comas
                    4. Si no encuentras ninguna, responde: "ninguna"
                    5. No incluyas texto adicional, solo las contraindicaciones encontradas
                    
                    Contraindicaciones encontradas:
                    """
                    
                    # Consultar a Gemini
                    response = self.genai_model.generate_content(prompt)
                    respuesta = response.text.strip().lower()
                    
                    if respuesta != "ninguna" and respuesta:
                        # Procesar respuesta
                        contraindicaciones = [c.strip() for c in respuesta.split(',')]
                        for contra in contraindicaciones:
                            # Verificar que esté en la lista oficial
                            for contra_oficial in self.lista_contraindicaciones:
                                if contra_oficial.lower() in contra or contra in contra_oficial.lower():
                                    contraindicaciones_encontradas.add(contra_oficial)
                                    
                except Exception as e:
                    logger.warning(f"Error procesando blob {blob.name}: {e}")
                    continue
            
            resultado = list(contraindicaciones_encontradas)
            logger.info(f"Contraindicaciones encontradas para {codigo_necesidad}: {resultado}")
            return resultado
            
        except Exception as e:
            logger.error(f"Error en Paso 10 para {codigo_necesidad}: {e}")
            return []
    
    def paso_11_procesar_todas_contraindicaciones(self):
        """
        Paso 11: Procesar contraindicaciones para todos los códigos con PAC > 0
        """
        logger.info("Ejecutando Paso 11: Procesando contraindicaciones para todos los códigos...")
        
        for codigo in self.diccionario_pac_mayor_cero.keys():
            contraindicaciones = self.paso_10_buscar_contraindicaciones_con_ia(codigo)
            self.contraindicaciones_encontradas[codigo] = contraindicaciones
        
        logger.info("Paso 11 completado")
        return True
    
    def paso_12_calcular_pesos_y_actualizar(self):
        """
        Paso 12: Calcular peso de cada ínfima y actualizar tabla evaluaciones
        """
        logger.info("Ejecutando Paso 12: Calculando pesos...")
        
        try:
            cursor = self.connection.cursor()
            
            for codigo, contraindicaciones in self.contraindicaciones_encontradas.items():
                # a) Obtener pesos individuales
                pesos_individuales = []
                for contra in contraindicaciones:
                    if contra in self.tabla_contraindicaciones_pesos:
                        pesos_individuales.append(self.tabla_contraindicaciones_pesos[contra])
                
                # b) Calcular peso total
                if not pesos_individuales:
                    peso_total = 0.0
                else:
                    # Peso_total = 1 - Π(1 - P(i))
                    producto = 1.0
                    for p in pesos_individuales:
                        producto *= (1 - p)
                    peso_total = 1 - producto
                
                # c) Actualizar tabla evaluaciones
                justificacion = ", ".join(contraindicaciones) if contraindicaciones else ""
                
                # Verificar si ya existe el registro
                query_check = """
                    SELECT COUNT(*) FROM evaluaciones 
                    WHERE codigo_necesidad = %s
                """
                cursor.execute(query_check, (codigo,))
                existe = cursor.fetchone()[0] > 0
                
                if existe:
                    query_update = """
                        UPDATE evaluaciones 
                        SET Peso_total = %s, justificacion = %s
                        WHERE codigo_necesidad = %s
                    """
                    cursor.execute(query_update, (peso_total, justificacion, codigo))
                else:
                    query_insert = """
                        INSERT INTO evaluaciones (codigo_necesidad, Peso_total, justificacion)
                        VALUES (%s, %s, %s)
                    """
                    cursor.execute(query_insert, (codigo, peso_total, justificacion))
                
                logger.info(f"Código {codigo}: Peso = {peso_total:.4f}, Contraindicaciones: {len(contraindicaciones)}")
            
            self.connection.commit()
            cursor.close()
            logger.info("Paso 12 completado: Pesos calculados y guardados")
            return True
            
        except Exception as e:
            logger.error(f"Error en Paso 12: {e}")
            return False
    
    def ejecutar_proceso_completo(self):
        """
        Ejecuta el proceso completo en orden
        """
        logger.info("=" * 80)
        logger.info("INICIANDO PROCESO COMPLETO DE GESTIÓN DE ÍNFIMAS")
        logger.info("=" * 80)
        
        # Conectar
        if not self.conectar_base_datos():
            logger.error("No se pudo conectar a la base de datos. Abortando.")
            return False
        
        if not self.conectar_google_cloud():
            logger.error("No se pudo conectar a Google Cloud. Abortando.")
            return False
        
        # Ejecutar pasos secuencialmente
        pasos = [
            (self.paso_1_cargar_contraindicaciones, "Paso 1"),
            (self.paso_2_cargar_contraindicaciones_pesos, "Paso 2"),
            (self.paso_3_cargar_codigos_preseleccionados, "Paso 3"),
            (self.paso_4_inicializar_diccionario_pac, "Paso 4"),
            (self.paso_5_y_6_procesar_todos_pac, "Pasos 5 y 6"),
            (self.paso_7_I_cargar_infimas_pac_valido, "Paso 7.I"),
            (self.paso_7_IV_procesar_todas_infimas, "Paso 7.II-IV"),
            (self.paso_8_crear_diccionario_pac_mayor_cero, "Paso 8"),
            (self.paso_9_inicializar_contraindicaciones_encontradas, "Paso 9"),
            (self.paso_11_procesar_todas_contraindicaciones, "Pasos 10 y 11"),
            (self.paso_12_calcular_pesos_y_actualizar, "Paso 12"),
        ]
        
        for func, nombre in pasos:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Ejecutando: {nombre}")
            logger.info(f"{'=' * 60}")
            
            if not func():
                logger.error(f"Error en {nombre}. Abortando proceso.")
                return False
        
        logger.info("\n" + "=" * 80)
        logger.info("PROCESO COMPLETADO EXITOSAMENTE")
        logger.info("=" * 80)
        
        # Cerrar conexiones
        if self.connection:
            self.connection.close()
        
        return True
    
    def __del__(self):
        """Destructor para cerrar conexiones"""
        if self.connection and self.connection.is_connected():
            self.connection.close()


def main():
    """Función principal"""
    gestor = GestorInfimas()
    exito = gestor.ejecutar_proceso_completo()
    
<<<<<<< HEAD
    if exito:
        logger.info("✓ Proceso finalizado exitosamente")
        return 0
    else:
        logger.error("✗ Proceso finalizado con errores")
        return 1

=======
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
>>>>>>> f3ebe4d5fdd9bd8cd6ecdf6cc3a9cbb276ab35ff

if __name__ == "__main__":
    exit(main())
