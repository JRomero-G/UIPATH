"""
=============================================================================
  GENERADOR AUTOMÁTICO DE FICHAS TÉCNICAS - GestorEx
  Versión: 2.0
  Descripción:
    Script de automatización para generación de fichas técnicas a partir
    de documentos de contratación almacenados en Google Cloud Storage,
    con análisis de IA (Vertex AI / Gemini), búsqueda de proveedores y
    generación de documentos Word (.docx) con formato institucional.

  Dependencias requeridas (instalar con pip):
    pip install mysql-connector-python
    pip install google-cloud-storage
    pip install google-auth
    pip install vertexai
    pip install PyPDF2
    pip install python-docx
    pip install requests
    pip install beautifulsoup4
    pip install lxml
    pip install Pillow
    pip install tqdm
    pip install python-docx
    pip install openpyxl
=============================================================================
"""

# ─── IMPORTS ESTÁNDAR ────────────────────────────────────────────────────────
import os
import io
import re
import sys
import json
import time
import shutil
import logging
import zipfile
import tempfile
import platform
import traceback
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── IMPORTS DE TERCEROS ─────────────────────────────────────────────────────
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    sys.exit("❌ Instala: pip install mysql-connector-python")

try:
    from google.cloud import storage
    from google.oauth2 import service_account
except ImportError:
    sys.exit("❌ Instala: pip install google-cloud-storage google-auth")

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part
except ImportError:
    sys.exit("❌ Instala: pip install vertexai")

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    sys.exit("❌ Instala: pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("❌ Instala: pip install beautifulsoup4 lxml")

try:
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import copy
except ImportError:
    sys.exit("❌ Instala: pip install python-docx")

try:
    import PyPDF2
except ImportError:
    sys.exit("❌ Instala: pip install PyPDF2")

try:
    from tqdm import tqdm
except ImportError:
    # Si no está tqdm, usar una versión mínima
    def tqdm(iterable=None, *args, **kwargs):
        return iterable if iterable is not None else iter([])

# ─── CONFIGURACIÓN GLOBAL ────────────────────────────────────────────────────

# Base de datos MySQL
MYSQL_CONFIG = {
    "host": "35.225.240.246",
    "user": "root",
    "password": "Admin123%",
    "database": "gestorex",
    "connection_timeout": 30,
    "autocommit": True,
}

# Google Cloud Storage
GEMINI_CREDENTIALS_PATH = "src/Credentials/Clave_bucket_AIgemini.json"
BUCKET_NAME = "nexusbucket1"
BUCKET_FOLDER = "Documentos de Contratación"

# Modelo de IA (Gemini 2.0 Flash es el más eficiente para documentos largos)
# Alternativa: "gemini-1.5-pro-002" para mayor precisión en documentos complejos
AI_MODEL = "gemini-2.0-flash-001"

# Archivo de plantilla DOCX (debe estar en la misma carpeta que este script)
TEMPLATE_DOCX = "FICHA_TECNICA_MICROFONO_Y_MEMORIA.docx"

# Archivo XLSX de proforma (se copia en cada carpeta NIC)
PROFORMA_XLSX = "FORMATO_DE_PROFORMA_RECREADO_VACÍO.xlsx"

# Reintentos para peticiones web
MAX_RETRIES = 3
REQUEST_TIMEOUT = 20

# Número de hilos para búsqueda paralela en proveedores
MAX_WORKERS_SEARCH = 5

# ─── PROVEEDORES ─────────────────────────────────────────────────────────────

PROVEEDORES_NACIONALES = {
    "Mi Bodega":              "https://mibodega.ec",
    "Bodeguita del Ahorro":   "https://bodeguitadelahorro.com",
    "Kissu":                  "https://kissu.com.ec",
    "Almacén Altaten":        "https://altatenalmacen.com.ec",
    "TVentas":                "https://www.tventas.com",
    "La Victoria":            "https://lavictoria.ec",
    "Marcimex":               "https://www.marcimex.com",
    "Almacenes España":       "https://almacenesespana.ec",
    "Novicompu":              "https://www.novicompu.com",
    "Techno Prime":           "https://technoprimec.com",
    "Point":                  "https://point.com.ec",
    "Computron":              "https://www.computron.com.ec",
    "Nomadaware":             "https://nomadaware.com.ec",
    "IDC Mayoristas":         "https://www.idcmayoristas.com",
    "Tecnit":                 "https://tecnit.com.ec",
    "TecnoMega":              "https://tecnomegastore.ec",
    "Artefacta":              "https://www.artefacta.com",
    "Mundo Tek":              "https://mundotek.com.ec",
    "Almacenes Juan Eljuri":  "https://eljuri.store",
    "Kywi":                   "https://www.kywi.com.ec",
    "Tecnocosto":             "https://tecnocostoec.com",
    "Almacenes Japón":        "https://www.almacenesjapon.com",
    "Electromega":            "https://electromegaecuador.com",
    "Compra Ecuador":         "https://www.compraecuador.com",
    "Gran Hogar":             "https://granhogar.com.ec",
    "Miami Home EC":          "https://miamihome-ec.com",
}

PROVEEDORES_EXTRANJEROS = {
    "Amazon":        "https://www.amazon.com",
    "Mercado Libre": "https://www.mercadolibre.com",
    "eBay":          "https://www.ebay.com",
}

# Buscadores de productos por proveedor (URLs de búsqueda)
SEARCH_URLS = {
    "Amazon":        "https://www.amazon.com/s?k={query}",
    "Mercado Libre": "https://listado.mercadolibre.com.ec/{query}",
    "eBay":          "https://www.ebay.com/sch/i.html?_nkw={query}",
    "Novicompu":     "https://www.novicompu.com/search?q={query}",
    "Computron":     "https://www.computron.com.ec/search?q={query}",
    "Marcimex":      "https://www.marcimex.com/search?q={query}",
    "TecnoMega":     "https://tecnomegastore.ec/?s={query}",
    "Kywi":          "https://www.kywi.com.ec/search?q={query}",
    "Artefacta":     "https://www.artefacta.com/?s={query}",
    "Almacenes Japón": "https://www.almacenesjapon.com/search?q={query}",
    "TVentas":       "https://www.tventas.com/search?term={query}",
}

# ─── LOGGING ─────────────────────────────────────────────────────────────────

def configurar_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"fichas_tecnicas_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)

logger = configurar_logging()


# ─── SESIÓN HTTP ROBUSTA ─────────────────────────────────────────────────────

def crear_sesion_http() -> requests.Session:
    """Crea una sesión HTTP con reintentos automáticos y headers de navegador."""
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-EC,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return session

HTTP_SESSION = crear_sesion_http()


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 1 — BASE DE DATOS MySQL
# ═══════════════════════════════════════════════════════════════════════════════

def conectar_mysql() -> mysql.connector.MySQLConnection:
    """Establece conexión con la base de datos MySQL con reintentos."""
    for intento in range(1, MAX_RETRIES + 1):
        try:
            conn = mysql.connector.connect(**MYSQL_CONFIG)
            if conn.is_connected():
                logger.info("✅ Conexión a MySQL establecida correctamente.")
                return conn
        except MySQLError as e:
            logger.warning(f"⚠️  Intento {intento}/{MAX_RETRIES} — Error MySQL: {e}")
            if intento < MAX_RETRIES:
                time.sleep(2 ** intento)
    raise ConnectionError("❌ No se pudo conectar a MySQL después de varios intentos.")


def obtener_data_table_1(conn: mysql.connector.MySQLConnection) -> list[dict]:
    """
    Obtiene de la tabla 'ínfimas' los registros con etapa='en generacion'
    y retorna las columnas requeridas como lista de diccionarios.
    """
    query = """
        SELECT
            codigo_necesidad,
            entidad_contratante,
            entidad_contratante_url,
            direccion_entrega,
            contacto
        FROM infimas
        WHERE etapa = 'en generacion'
    """
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        data_table_1 = cursor.fetchall()
        cursor.close()
        logger.info(f"📋 Registros encontrados en 'ínfimas' (en generacion): {len(data_table_1)}")
        for row in data_table_1:
            logger.debug(f"   → NIC: {row.get('codigo_necesidad')}")
        return data_table_1
    except MySQLError as e:
        logger.error(f"❌ Error al ejecutar la consulta MySQL: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 2 — GOOGLE CLOUD STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

def crear_cliente_gcs() -> storage.Client:
    """Crea el cliente de Google Cloud Storage con las credenciales de servicio."""
    if not Path(GEMINI_CREDENTIALS_PATH).exists():
        raise FileNotFoundError(
            f"❌ No se encontró el archivo de credenciales: {GEMINI_CREDENTIALS_PATH}"
        )
    credentials = service_account.Credentials.from_service_account_file(
        GEMINI_CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client = storage.Client(credentials=credentials, project=credentials.project_id)
    logger.info(f"✅ Cliente GCS creado. Proyecto: {credentials.project_id}")
    return client


def listar_archivos_nic(gcs_client: storage.Client, codigo_necesidad: str) -> list[storage.Blob]:
    """
    Lista los archivos (doc, docx, pdf) en la carpeta del bucket
    que corresponde al código de necesidad dado.
    """
    bucket = gcs_client.bucket(BUCKET_NAME)
    prefijo = f"{BUCKET_FOLDER}/{codigo_necesidad}/"
    blobs = list(bucket.list_blobs(prefix=prefijo))

    archivos_validos = [
        b for b in blobs
        if b.name.lower().endswith((".pdf", ".docx", ".doc"))
        and not b.name.endswith("/")
    ]
    logger.info(
        f"   📂 NIC {codigo_necesidad}: {len(archivos_validos)} archivos encontrados."
    )
    return archivos_validos


def descargar_blob_a_bytes(blob: storage.Blob) -> bytes:
    """Descarga un blob de GCS y retorna su contenido en bytes."""
    return blob.download_as_bytes()


def extraer_texto_pdf(pdf_bytes: bytes) -> str:
    """Extrae el texto de un PDF dado como bytes."""
    texto = []
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texto.append(t)
    except Exception as e:
        logger.warning(f"   ⚠️  No se pudo extraer texto del PDF: {e}")
    return "\n".join(texto)


def extraer_texto_docx(docx_bytes: bytes) -> str:
    """Extrae el texto de un DOCX dado como bytes."""
    texto = []
    try:
        doc = Document(io.BytesIO(docx_bytes))
        for para in doc.paragraphs:
            if para.text.strip():
                texto.append(para.text.strip())
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        texto.append(cell.text.strip())
    except Exception as e:
        logger.warning(f"   ⚠️  No se pudo extraer texto del DOCX: {e}")
    return "\n".join(texto)


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 3 — VERTEX AI / GEMINI
# ═══════════════════════════════════════════════════════════════════════════════

def inicializar_vertex_ai() -> GenerativeModel:
    """
    Inicializa Vertex AI con las credenciales de servicio y retorna
    el modelo Gemini configurado para análisis de documentos.

    Se usa gemini-2.0-flash-001 por su excelente balance entre:
    - Velocidad de respuesta
    - Capacidad de análisis multimodal (texto + imágenes)
    - Ventana de contexto de 1M tokens (ideal para documentos largos)
    - Menor costo por token vs Gemini 1.5 Pro

    Alternativa de mayor precisión: "gemini-1.5-pro-002"
    """
    if not Path(GEMINI_CREDENTIALS_PATH).exists():
        raise FileNotFoundError(
            f"❌ Credenciales no encontradas: {GEMINI_CREDENTIALS_PATH}"
        )

    credentials = service_account.Credentials.from_service_account_file(
        GEMINI_CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    with open(GEMINI_CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        creds_data = json.load(f)
        project_id = creds_data.get("project_id")

    vertexai.init(
        project=project_id,
        credentials=credentials,
        location="us-central1",
    )

    model = GenerativeModel(
        model_name=AI_MODEL,
        generation_config={
            "temperature": 0.2,       # Baja temperatura = respuestas más deterministas
            "top_p": 0.8,
            "max_output_tokens": 8192,
        },
        system_instruction=(
            "Eres un asistente experto en análisis de documentos de contratación "
            "pública del Ecuador. Extraes información técnica precisa de los "
            "documentos y respondes siempre en español, con formato JSON estructurado."
        ),
    )

    logger.info(f"✅ Vertex AI inicializado. Modelo: {AI_MODEL}")
    return model


PROMPT_ANALISIS_DOCUMENTOS = """
Analiza el siguiente contenido extraído de documentos de contratación pública
y extrae la información del artículo o producto de compra solicitado.

TEXTO DE LOS DOCUMENTOS:
---
{texto_documentos}
---

Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura
(sin markdown, sin texto adicional antes o después del JSON):

{{
  "nombre_articulo": "Nombre completo del artículo solicitado",
  "marca": "Marca del artículo (si se especifica, si no: null)",
  "modelo": "Modelo del artículo (si se especifica, si no: null)",
  "caracteristicas_generales": [
    "Característica 1",
    "Característica 2",
    "... (al menos 7, máximo 10)"
  ],
  "especificaciones_tecnicas": [
    "Especificación técnica 1: valor",
    "Especificación técnica 2: valor",
    "... (al menos 10)"
  ],
  "especificaciones_electricas": [
    "Especificación eléctrica 1: valor",
    "... (lista vacía [] si no aplica)"
  ],
  "incluye": [
    "Accesorio o ítem incluido 1",
    "... (lista vacía [] si no se menciona)"
  ],
  "otra_informacion": "Cualquier información relevante adicional del producto",
  "cantidad_solicitada": "Cantidad de unidades solicitadas (número o null)",
  "descripcion_busqueda": "Términos de búsqueda cortos y precisos para encontrar el producto en tiendas en línea"
}}
"""


def analizar_documentos_con_ia(
    modelo: GenerativeModel,
    blobs: list[storage.Blob],
    gcs_client: storage.Client,
) -> dict:
    """
    Descarga los documentos del bucket, extrae su texto y los envía
    a Gemini para análisis estructurado.

    Estrategia de envío:
    - PDFs pequeños (<10MB): se envían como Part.from_data (multimodal nativo)
    - DOCX y PDFs grandes: se extrae el texto y se envía como texto plano
    """
    partes = []
    textos_extraidos = []

    for blob in blobs:
        nombre = blob.name
        extension = Path(nombre).suffix.lower()
        logger.info(f"   📄 Procesando: {nombre}")

        try:
            contenido_bytes = descargar_blob_a_bytes(blob)
            tamaño_mb = len(contenido_bytes) / (1024 * 1024)

            if extension == ".pdf" and tamaño_mb < 10:
                # Enviar PDF directamente como dato binario (mejor análisis)
                partes.append(
                    Part.from_data(
                        data=contenido_bytes,
                        mime_type="application/pdf",
                    )
                )
                logger.debug(f"      ✅ PDF enviado como dato multimodal ({tamaño_mb:.1f} MB)")

            elif extension in (".docx", ".doc"):
                # Extraer texto del DOCX
                texto = extraer_texto_docx(contenido_bytes)
                if texto.strip():
                    textos_extraidos.append(
                        f"=== DOCUMENTO: {Path(nombre).name} ===\n{texto}"
                    )
                    logger.debug(f"      ✅ DOCX procesado ({len(texto)} caracteres)")

            else:
                # PDF grande: extraer texto
                texto = extraer_texto_pdf(contenido_bytes)
                if texto.strip():
                    textos_extraidos.append(
                        f"=== DOCUMENTO: {Path(nombre).name} ===\n{texto}"
                    )
                    logger.debug(f"      ✅ PDF grande → texto extraído ({len(texto)} chars)")

        except Exception as e:
            logger.warning(f"   ⚠️  Error al procesar {nombre}: {e}")
            continue

    # Construir el prompt con el texto extraído
    texto_combinado = "\n\n".join(textos_extraidos) if textos_extraidos else "(sin texto adicional)"
    prompt_final = PROMPT_ANALISIS_DOCUMENTOS.format(texto_documentos=texto_combinado)

    # Construir lista de partes para Gemini
    prompt_part = Part.from_text(prompt_final)
    contenido_envio = partes + [prompt_part]

    # Enviar a Gemini con reintentos
    for intento in range(1, MAX_RETRIES + 1):
        try:
            respuesta = modelo.generate_content(contenido_envio)
            texto_respuesta = respuesta.text.strip()

            # Limpiar posibles bloques de código markdown
            texto_respuesta = re.sub(r"^```(?:json)?\s*", "", texto_respuesta)
            texto_respuesta = re.sub(r"\s*```$", "", texto_respuesta)

            datos = json.loads(texto_respuesta)
            logger.info("   🤖 Análisis IA completado exitosamente.")
            return datos

        except json.JSONDecodeError as e:
            logger.warning(
                f"   ⚠️  Intento {intento}: Respuesta IA no es JSON válido. "
                f"Error: {e}\nRespuesta: {texto_respuesta[:300]}..."
            )
            if intento == MAX_RETRIES:
                # Retornar estructura vacía como fallback
                return {
                    "nombre_articulo": "Artículo no identificado",
                    "marca": None, "modelo": None,
                    "caracteristicas_generales": [],
                    "especificaciones_tecnicas": [],
                    "especificaciones_electricas": [],
                    "incluye": [], "otra_informacion": "",
                    "cantidad_solicitada": None,
                    "descripcion_busqueda": "",
                    "_error": str(e),
                }
            time.sleep(2 ** intento)

        except Exception as e:
            logger.warning(f"   ⚠️  Intento {intento}: Error en Gemini: {e}")
            if intento == MAX_RETRIES:
                raise
            time.sleep(2 ** intento)


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 4 — BÚSQUEDA EN PROVEEDORES
# ═══════════════════════════════════════════════════════════════════════════════

def construir_query_busqueda(datos_ia: dict) -> str:
    """Construye un término de búsqueda efectivo a partir de los datos de IA."""
    partes = []
    if datos_ia.get("marca"):
        partes.append(datos_ia["marca"])
    if datos_ia.get("modelo"):
        partes.append(datos_ia["modelo"])
    if datos_ia.get("descripcion_busqueda"):
        partes.append(datos_ia["descripcion_busqueda"])
    elif datos_ia.get("nombre_articulo"):
        partes.append(datos_ia["nombre_articulo"])
    return " ".join(partes)[:100]


def buscar_en_proveedor(nombre_proveedor: str, url_base: str, query: str) -> dict | None:
    """
    Realiza una búsqueda en un proveedor específico y retorna
    el primer resultado relevante con nombre, precio y URL.
    """
    # Construir URL de búsqueda
    url_busqueda = None

    if nombre_proveedor in SEARCH_URLS:
        url_busqueda = SEARCH_URLS[nombre_proveedor].format(
            query=requests.utils.quote(query)
        )
    else:
        # Fallback: Google site search
        url_busqueda = (
            f"https://www.google.com/search?q=site:{url_base.replace('https://', '').replace('http://', '')} "
            f"{requests.utils.quote(query)}"
        )

    try:
        resp = HTTP_SESSION.get(url_busqueda, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Estrategias de extracción de precio (comunes en e-commerce Ecuador)
        precio = None
        nombre_producto = None
        url_producto = url_busqueda

        # Buscar precios con selectores comunes
        selectores_precio = [
            "[class*='price']", "[class*='precio']", "[class*='Price']",
            "[id*='price']", "[id*='precio']", ".amount", ".woocommerce-Price-amount",
            "[data-price]", ".product-price", ".entry-price", "span.price",
        ]
        for selector in selectores_precio:
            elementos = soup.select(selector)
            for elem in elementos:
                texto = elem.get_text(strip=True)
                # Buscar patrón de precio en USD ($XX.XX o XX.XX)
                match = re.search(r"\$?\s*(\d{1,6}[.,]\d{2})", texto)
                if match:
                    precio_str = match.group(1).replace(",", ".")
                    try:
                        precio = float(precio_str)
                        break
                    except ValueError:
                        continue
            if precio:
                break

        # Buscar nombre del producto
        selectores_nombre = [
            "h1.product-title", "h1.product_title", ".product-name h1",
            "h2.product-title", ".entry-title", "h1", "h2",
        ]
        for selector in selectores_nombre:
            elem = soup.select_one(selector)
            if elem:
                nombre_producto = elem.get_text(strip=True)[:200]
                break

        # Buscar URL del producto
        enlaces = soup.select("a[href*='product'], a[href*='producto'], a[href*='item']")
        if enlaces:
            href = enlaces[0].get("href", "")
            if href.startswith("http"):
                url_producto = href
            elif href.startswith("/"):
                url_producto = url_base.rstrip("/") + href

        if precio and precio > 0:
            return {
                "proveedor": nombre_proveedor,
                "nombre_producto": nombre_producto or query,
                "precio": precio,
                "url": url_producto,
                "url_busqueda": url_busqueda,
            }

    except requests.exceptions.Timeout:
        logger.debug(f"   ⏱️  Timeout en {nombre_proveedor}")
    except requests.exceptions.ConnectionError:
        logger.debug(f"   🔌 Sin conexión a {nombre_proveedor}")
    except Exception as e:
        logger.debug(f"   ⚠️  Error en {nombre_proveedor}: {type(e).__name__}: {e}")

    return None


def buscar_en_todos_proveedores(datos_ia: dict) -> dict | None:
    """
    Busca el producto en todos los proveedores (nacionales y extranjeros)
    en paralelo y retorna la mejor opción (precio más bajo).
    """
    query = construir_query_busqueda(datos_ia)
    if not query:
        logger.warning("   ⚠️  No hay términos de búsqueda para el producto.")
        return None

    logger.info(f"   🔍 Buscando: '{query}' en {len(PROVEEDORES_NACIONALES) + len(PROVEEDORES_EXTRANJEROS)} proveedores...")

    todos_proveedores = {**PROVEEDORES_NACIONALES, **PROVEEDORES_EXTRANJEROS}
    resultados = []

    # Búsqueda paralela con límite de hilos
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_SEARCH) as executor:
        futuros = {
            executor.submit(buscar_en_proveedor, nombre, url, query): nombre
            for nombre, url in todos_proveedores.items()
        }
        for futuro in as_completed(futuros):
            try:
                resultado = futuro.result(timeout=REQUEST_TIMEOUT + 5)
                if resultado:
                    resultados.append(resultado)
                    logger.debug(
                        f"   💰 {resultado['proveedor']}: ${resultado['precio']:.2f} — {resultado['nombre_producto'][:50]}"
                    )
            except Exception:
                pass

    if not resultados:
        logger.warning("   ⚠️  No se encontraron precios en ningún proveedor.")
        return None

    # Ordenar por precio (menor primero) y retornar el mejor
    resultados.sort(key=lambda x: x["precio"])
    mejor = resultados[0]
    logger.info(
        f"   🏆 Mejor opción: {mejor['proveedor']} — ${mejor['precio']:.2f} — {mejor['nombre_producto'][:60]}"
    )
    return mejor


def obtener_descripcion_fabricante(datos_ia: dict, mejor_proveedor: dict | None) -> str:
    """
    Intenta obtener una descripción del producto desde la página del proveedor
    o la genera a partir de los datos de IA.
    """
    if mejor_proveedor and mejor_proveedor.get("url"):
        try:
            resp = HTTP_SESSION.get(mejor_proveedor["url"], timeout=REQUEST_TIMEOUT)
            soup = BeautifulSoup(resp.text, "lxml")

            # Selectores comunes de descripción en tiendas
            selectores = [
                ".product-description", ".woocommerce-product-details__short-description",
                "#product-description", ".description", ".product-details",
                "[class*='description']", "div.tab-content p",
            ]
            for selector in selectores:
                elem = soup.select_one(selector)
                if elem:
                    texto = elem.get_text(separator=" ", strip=True)
                    if len(texto) > 50:
                        # Limitar a ~80 palabras
                        palabras = texto.split()[:80]
                        return " ".join(palabras)
        except Exception as e:
            logger.debug(f"   No se pudo obtener descripción web: {e}")

    # Generar descripción desde los datos de IA
    nombre = datos_ia.get("nombre_articulo", "el producto")
    marca = datos_ia.get("marca", "")
    caracteristicas = datos_ia.get("caracteristicas_generales", [])
    desc_base = f"{nombre}"
    if marca:
        desc_base += f" de la marca {marca}"
    if caracteristicas:
        desc_base += f". {caracteristicas[0]}"
    if len(caracteristicas) > 1:
        desc_base += f" {caracteristicas[1]}."
    return desc_base


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 5 — GENERACIÓN DE FICHA TÉCNICA (.docx)
# ═══════════════════════════════════════════════════════════════════════════════

def copiar_formato_parrafo(parrafo_origen, parrafo_destino):
    """Copia el formato XML de un párrafo origen a uno destino."""
    if parrafo_origen.paragraph_format:
        pf_orig = parrafo_origen._p.get_or_add_pPr()
        pf_dest = parrafo_destino._p.get_or_add_pPr()
        # Copiar los elementos de formato
        for child in list(pf_orig):
            tag = child.tag
            # Eliminar el elemento equivalente en destino si existe
            existing = pf_dest.find(tag)
            if existing is not None:
                pf_dest.remove(existing)
            pf_dest.append(copy.deepcopy(child))


def agregar_parrafo_con_estilo(
    doc: Document,
    texto: str,
    negrita: bool = False,
    tamaño_pt: float = 12,
    centrado: bool = False,
    fuente: str = "Century Gothic",
    color: RGBColor | None = None,
    espaciado_anterior: int = 0,
    espaciado_posterior: int = 0,
) -> None:
    """Agrega un párrafo formateado al documento con el estilo de la plantilla."""
    para = doc.add_paragraph()
    run = para.add_run(texto)
    run.font.name = fuente
    run.font.size = Pt(tamaño_pt)
    run.font.bold = negrita
    if color:
        run.font.color.rgb = color

    if centrado:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    else:
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Espaciado
    para.paragraph_format.space_before = Pt(espaciado_anterior)
    para.paragraph_format.space_after = Pt(espaciado_posterior)

    # Asegurar fuente en XML para compatibilidad
    rPr = run._r.get_or_add_rPr()
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), fuente)
    rFonts.set(qn("w:hAnsi"), fuente)
    existing = rPr.find(qn("w:rFonts"))
    if existing is not None:
        rPr.remove(existing)
    rPr.insert(0, rFonts)

    return para


def generar_ficha_tecnica_docx(
    datos_ia: dict,
    mejor_proveedor: dict | None,
    descripcion: str,
    ruta_destino: Path,
    plantilla_path: str,
) -> Path:
    """
    Genera la ficha técnica en formato .docx usando la plantilla institucional.
    Preserva encabezado, pie de página, fuente y estilos originales.
    """
    # ── Cargar la plantilla original (preserva header/footer/estilos) ──────
    if Path(plantilla_path).exists():
        doc = Document(plantilla_path)
        # Limpiar el cuerpo del documento manteniendo header/footer
        for para in doc.paragraphs:
            p = para._element
            p.getparent().remove(p)
        for table in doc.tables:
            t = table._element
            t.getparent().remove(t)
    else:
        logger.warning(f"   ⚠️  Plantilla no encontrada: {plantilla_path}. Usando documento vacío.")
        doc = Document()
        # Configurar márgenes
        section = doc.sections[0]
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)

    nombre_articulo = datos_ia.get("nombre_articulo", "Artículo sin nombre")
    marca = datos_ia.get("marca", "")
    modelo_art = datos_ia.get("modelo", "")

    # Título completo del artículo
    titulo_completo = nombre_articulo
    if marca and marca not in titulo_completo:
        titulo_completo += f" {marca}"
    if modelo_art and modelo_art not in titulo_completo:
        titulo_completo += f" {modelo_art}"

    # ── TÍTULO (negrita, centrado, 12pt Century Gothic) ─────────────────────
    agregar_parrafo_con_estilo(
        doc, titulo_completo,
        negrita=True, tamaño_pt=12, centrado=True,
        espaciado_anterior=0, espaciado_posterior=6,
    )

    # ── DESCRIPCIÓN (50-80 palabras, justificado) ────────────────────────────
    agregar_parrafo_con_estilo(
        doc, descripcion,
        negrita=False, tamaño_pt=12, centrado=False,
        espaciado_anterior=6, espaciado_posterior=6,
    )

    # ── CARACTERÍSTICAS GENERALES ────────────────────────────────────────────
    caracteristicas = datos_ia.get("caracteristicas_generales", [])
    if caracteristicas:
        agregar_parrafo_con_estilo(
            doc, "Características:",
            negrita=True, tamaño_pt=12,
            espaciado_anterior=6, espaciado_posterior=2,
        )
        for item in caracteristicas:
            agregar_parrafo_con_estilo(
                doc, item,
                negrita=False, tamaño_pt=12,
                espaciado_anterior=0, espaciado_posterior=0,
            )

    # ── ESPECIFICACIONES TÉCNICAS ────────────────────────────────────────────
    specs_tec = datos_ia.get("especificaciones_tecnicas", [])
    if specs_tec:
        agregar_parrafo_con_estilo(
            doc, "Especificaciones técnicas:",
            negrita=True, tamaño_pt=12,
            espaciado_anterior=6, espaciado_posterior=2,
        )
        for spec in specs_tec:
            agregar_parrafo_con_estilo(
                doc, spec,
                negrita=False, tamaño_pt=12,
                espaciado_anterior=0, espaciado_posterior=0,
            )

    # ── ESPECIFICACIONES ELÉCTRICAS ──────────────────────────────────────────
    specs_elec = datos_ia.get("especificaciones_electricas", [])
    if specs_elec:
        agregar_parrafo_con_estilo(
            doc, "Especificaciones eléctricas:",
            negrita=True, tamaño_pt=12,
            espaciado_anterior=6, espaciado_posterior=2,
        )
        for spec in specs_elec:
            agregar_parrafo_con_estilo(
                doc, spec,
                negrita=False, tamaño_pt=12,
                espaciado_anterior=0, espaciado_posterior=0,
            )

    # ── OTRA INFORMACIÓN ─────────────────────────────────────────────────────
    otra_info = datos_ia.get("otra_informacion", "")
    if otra_info and otra_info.strip():
        agregar_parrafo_con_estilo(
            doc, "Información adicional:",
            negrita=True, tamaño_pt=12,
            espaciado_anterior=6, espaciado_posterior=2,
        )
        agregar_parrafo_con_estilo(
            doc, otra_info,
            negrita=False, tamaño_pt=12,
            espaciado_anterior=0, espaciado_posterior=4,
        )

    # ── INCLUYE ──────────────────────────────────────────────────────────────
    incluye = datos_ia.get("incluye", [])
    if incluye:
        agregar_parrafo_con_estilo(
            doc, "Incluye:",
            negrita=True, tamaño_pt=12,
            espaciado_anterior=6, espaciado_posterior=2,
        )
        for item in incluye:
            agregar_parrafo_con_estilo(
                doc, item,
                negrita=False, tamaño_pt=12,
                espaciado_anterior=0, espaciado_posterior=0,
            )

    # ── INFORMACIÓN DEL PROVEEDOR ─────────────────────────────────────────────
    if mejor_proveedor:
        agregar_parrafo_con_estilo(
            doc, "",  # Línea en blanco
            negrita=False, tamaño_pt=6,
            espaciado_anterior=4, espaciado_posterior=0,
        )
        info_precio = (
            f"Precio referencial: ${mejor_proveedor['precio']:.2f} USD  |  "
            f"Proveedor: {mejor_proveedor['proveedor']}  |  "
            f"URL: {mejor_proveedor['url']}"
        )
        agregar_parrafo_con_estilo(
            doc, info_precio,
            negrita=False, tamaño_pt=9, centrado=False,
            color=RGBColor(0x70, 0x70, 0x70),
            espaciado_anterior=0, espaciado_posterior=0,
        )

    # ── GUARDAR ──────────────────────────────────────────────────────────────
    nombre_archivo = re.sub(r'[\\/*?:"<>|]', "_", titulo_completo[:80])
    nombre_archivo = f"Ficha_Tecnica_{nombre_archivo}.docx"
    ruta_archivo = ruta_destino / nombre_archivo

    doc.save(str(ruta_archivo))
    logger.info(f"   💾 Ficha técnica guardada: {ruta_archivo}")
    return ruta_archivo


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 6 — GUARDAR ARCHIVOS LOCALMENTE
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_carpeta_documentos_usuario() -> Path:
    """
    Obtiene la ruta de Documentos del usuario actual en Windows.
    Compatible con rutas personalizadas (OneDrive, etc.).
    """
    if platform.system() == "Windows":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            ) as key:
                docs_path = winreg.QueryValueEx(key, "Personal")[0]
                return Path(docs_path)
        except Exception:
            pass
        # Fallback
        return Path(os.environ.get("USERPROFILE", "C:/Users/Default")) / "Documents"
    else:
        # En Linux/Mac (para desarrollo y pruebas)
        return Path.home() / "Documents"


def crear_carpeta_nic(nic: str) -> Path:
    """
    Crea la carpeta local para el NIC dado:
    C:\\Users\\{user}\\Documents\\Documentos de Contratación\\{NIC}
    """
    base_docs = obtener_carpeta_documentos_usuario()
    carpeta_nic = base_docs / "Documentos de Contratación" / nic
    carpeta_nic.mkdir(parents=True, exist_ok=True)
    logger.info(f"   📁 Carpeta creada: {carpeta_nic}")
    return carpeta_nic


def guardar_archivos_bucket_localmente(
    blobs: list[storage.Blob],
    carpeta_destino: Path,
) -> None:
    """Descarga y guarda localmente todos los archivos del bucket del NIC."""
    for blob in blobs:
        nombre_archivo = Path(blob.name).name
        ruta_local = carpeta_destino / nombre_archivo
        try:
            contenido = descargar_blob_a_bytes(blob)
            ruta_local.write_bytes(contenido)
            logger.info(f"   💾 Documento descargado: {nombre_archivo}")
        except Exception as e:
            logger.warning(f"   ⚠️  Error al descargar {nombre_archivo}: {e}")


def copiar_proforma_xlsx(carpeta_destino: Path) -> None:
    """Copia el archivo XLSX de proforma a la carpeta del NIC."""
    ruta_origen = Path(PROFORMA_XLSX)
    if not ruta_origen.exists():
        # Buscar en el directorio del script
        ruta_origen = Path(__file__).parent / PROFORMA_XLSX

    if ruta_origen.exists():
        ruta_destino_xlsx = carpeta_destino / ruta_origen.name
        shutil.copy2(str(ruta_origen), str(ruta_destino_xlsx))
        logger.info(f"   📊 Proforma copiada: {ruta_destino_xlsx.name}")
    else:
        logger.warning(f"   ⚠️  Archivo de proforma no encontrado: {PROFORMA_XLSX}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ORQUESTADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def procesar_nic(
    fila: dict,
    gcs_client: storage.Client,
    modelo_ia: GenerativeModel,
    plantilla_path: str,
) -> dict:
    """
    Procesa un NIC completo:
    1. Lista archivos en el bucket
    2. Analiza con IA
    3. Busca en proveedores
    4. Genera ficha técnica
    5. Guarda archivos localmente
    """
    nic = str(fila.get("codigo_necesidad", "SIN_NIC")).strip()
    resultado = {
        "nic": nic,
        "estado": "pendiente",
        "ficha_generada": None,
        "proveedor_seleccionado": None,
        "error": None,
    }

    logger.info(f"\n{'='*60}")
    logger.info(f"  🔄 Procesando NIC: {nic}")
    logger.info(f"  🏛️  Entidad: {fila.get('entidad_contratante', 'N/A')}")
    logger.info(f"{'='*60}")

    try:
        # ── 1. Listar archivos en el bucket ──────────────────────────────────
        blobs = listar_archivos_nic(gcs_client, nic)
        if not blobs:
            logger.warning(f"   ⚠️  No se encontraron archivos en el bucket para NIC: {nic}")
            resultado["estado"] = "sin_archivos"
            return resultado

        # ── 2. Analizar con IA ───────────────────────────────────────────────
        datos_ia = analizar_documentos_con_ia(modelo_ia, blobs, gcs_client)
        logger.info(f"   📦 Artículo identificado: {datos_ia.get('nombre_articulo')}")

        # ── 3. Buscar en proveedores ─────────────────────────────────────────
        mejor_proveedor = buscar_en_todos_proveedores(datos_ia)
        resultado["proveedor_seleccionado"] = mejor_proveedor

        # ── 4. Obtener descripción ───────────────────────────────────────────
        descripcion = obtener_descripcion_fabricante(datos_ia, mejor_proveedor)

        # ── 5. Crear carpeta local para el NIC ───────────────────────────────
        carpeta_nic = crear_carpeta_nic(nic)

        # ── 6. Generar ficha técnica .docx ───────────────────────────────────
        ruta_ficha = generar_ficha_tecnica_docx(
            datos_ia, mejor_proveedor, descripcion, carpeta_nic, plantilla_path
        )
        resultado["ficha_generada"] = str(ruta_ficha)

        # ── 7. Guardar documentos del bucket ─────────────────────────────────
        guardar_archivos_bucket_localmente(blobs, carpeta_nic)

        # ── 8. Copiar proforma XLSX ───────────────────────────────────────────
        copiar_proforma_xlsx(carpeta_nic)

        resultado["estado"] = "completado"
        logger.info(f"   ✅ NIC {nic} procesado exitosamente.")

    except Exception as e:
        resultado["estado"] = "error"
        resultado["error"] = str(e)
        logger.error(f"   ❌ Error procesando NIC {nic}: {e}")
        logger.debug(traceback.format_exc())

    return resultado


def main():
    """Función principal que orquesta todo el proceso."""
    print("\n" + "═" * 70)
    print("   GENERADOR AUTOMÁTICO DE FICHAS TÉCNICAS — GestorEx")
    print("   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("═" * 70 + "\n")

    # Verificar plantilla y proforma
    plantilla_path = TEMPLATE_DOCX
    if not Path(plantilla_path).exists():
        plantilla_path = str(Path(__file__).parent / TEMPLATE_DOCX)
        if not Path(plantilla_path).exists():
            logger.warning(f"⚠️  Plantilla '{TEMPLATE_DOCX}' no encontrada. Se usará formato básico.")
            plantilla_path = None

    # ── PASO 1: Conectar a MySQL y obtener data_table_1 ─────────────────────
    logger.info("📡 Conectando a base de datos MySQL...")
    conn = conectar_mysql()
    data_table_1 = obtener_data_table_1(conn)
    conn.close()

    if not data_table_1:
        logger.warning("⚠️  No hay registros con etapa='en generacion'. Proceso terminado.")
        return

    logger.info(f"📊 Total de NICs a procesar: {len(data_table_1)}")

    # ── PASO 2: Crear cliente GCS ────────────────────────────────────────────
    logger.info("\n☁️  Conectando a Google Cloud Storage...")
    gcs_client = crear_cliente_gcs()

    # ── PASO 3: Inicializar Vertex AI ────────────────────────────────────────
    logger.info("\n🤖 Inicializando Vertex AI (Gemini)...")
    modelo_ia = inicializar_vertex_ai()

    # ── PROCESAR CADA NIC ────────────────────────────────────────────────────
    resultados = []
    total = len(data_table_1)

    for i, fila in enumerate(data_table_1, 1):
        logger.info(f"\n⏳ Procesando {i}/{total}...")
        resultado = procesar_nic(fila, gcs_client, modelo_ia, plantilla_path)
        resultados.append(resultado)
        # Pequeña pausa entre NICs para no sobrecargar la API
        if i < total:
            time.sleep(1)

    # ── RESUMEN FINAL ────────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("   RESUMEN DE PROCESAMIENTO")
    print("═" * 70)

    completados = [r for r in resultados if r["estado"] == "completado"]
    errores = [r for r in resultados if r["estado"] == "error"]
    sin_archivos = [r for r in resultados if r["estado"] == "sin_archivos"]

    print(f"   ✅ Completados:    {len(completados)}/{total}")
    print(f"   📂 Sin archivos:   {len(sin_archivos)}/{total}")
    print(f"   ❌ Con errores:    {len(errores)}/{total}")

    if completados:
        carpeta_base = obtener_carpeta_documentos_usuario() / "Documentos de Contratación"
        print(f"\n   📁 Archivos guardados en:")
        print(f"      {carpeta_base}")

    if errores:
        print("\n   NICs con error:")
        for r in errores:
            print(f"      ⚠️  {r['nic']}: {r['error']}")

    # Guardar resumen en JSON
    resumen_path = Path("logs") / f"resumen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(resumen_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"\n📝 Resumen guardado en: {resumen_path}")

    print("\n" + "═" * 70)
    print("   ✅ Proceso completado.")
    print("═" * 70 + "\n")


# ─── PUNTO DE ENTRADA ────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Proceso interrumpido por el usuario.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"❌ Error crítico no manejado: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)