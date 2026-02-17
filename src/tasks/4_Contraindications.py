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
            
            return 0.0
            
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
    
    if exito:
        logger.info("✓ Proceso finalizado exitosamente")
        return 0
    else:
        logger.error("✗ Proceso finalizado con errores")
        return 1


if __name__ == "__main__":
    exit(main())
