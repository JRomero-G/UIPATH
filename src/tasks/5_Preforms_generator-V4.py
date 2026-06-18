# ═══════════════════════════════════════════════════════════════════════════════
#  Proyecto NEXUS — 5_Preforms_generator (V3)
#  Genera, por cada código de necesidad "en generacion":
#     • una Ficha Técnica .docx  → carpeta GCS "Fichas Técnicas"
#     • una Proforma   .xlsm     → carpeta GCS "Proformas"
#  y marca la ínfima como "finalizada".
#
#  Cambios clave de esta versión (ver notas al pie del script):
#   - Migrado al SDK google-genai (Vertex AI) con Gemini 3.1 Pro (tareas complejas
#     y búsqueda con grounding) y Gemini 2.5 Pro como fallback.
#   - Búsqueda de productos con Google Search grounding (links reales) en vez del
#     scraping/scoring manual; DuckDuckGo se conserva solo como respaldo de imágenes.
#   - Ficha y proforma reescritas según la especificación y la estructura EXACTA
#     de las plantillas (orden de secciones, celdas, alturas, alternativas, etc.).
# ═══════════════════════════════════════════════════════════════════════════════

import os, sys, json, shutil, tempfile, datetime, re, io, time, traceback
import urllib.parse, html
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from Config import Global

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

MYSQL_CONFIG = {
    "host":     Global.DB_HOST,
    "user":     Global.DB_USER,
    "password": Global.DB_PASSWORD,
    "database": Global.DATABASE,
    "connection_timeout": 20,
}

GEMINI_CREDENTIALS_PATH = Global.CREDENTIALS_GEMINI
BUCKET_NAME             = Global.BUCKET_NAME
BUCKET_FOLDER           = "Documentos de Contratación"
CARPETA_FICHAS          = "Fichas Técnicas"
CARPETA_PROFORMAS       = "Proformas"

# --- Modelos / Vertex ---
MODEL_COMPLEX   = "gemini-3.1-pro-preview"   # tareas complejas + grounding
MODEL_SIMPLE    = "gemini-2.5-pro"           # tareas simples / fallback
VERTEX_LOCATION = "global"                    # endpoint global (Gemini 3.x)

# --- Reglas de negocio ---
LIMITE_ARTICULOS   = 10        # > 10 artículos distintos ⇒ no se genera proforma
ENVIO_MIN, ENVIO_MAX       = 86.0, 155.0   # USD, entregas fuera de Guayaquil
INSTAL_MIN, INSTAL_MAX     = 60.0, 80.0    # USD por artículo, si requiere instalación

# Un proveedor se considera "compartido" cuando surte a este número de artículos o más.
# (La instrucción menciona "más de dos"; con 2 el costo se distribuye en cuanto un
#  proveedor se repite. Cambia a 3 si se desea el umbral literal de "más de dos".)
MIN_ARTICULOS_PROVEEDOR_COMPARTIDO = 2

# --- Plantillas (junto al script en producción) ---
SCRIPT_DIR    = Path(__file__).parent
TEMPLATE_DOCX = SCRIPT_DIR / "FICHA TECNICA MICROFONO Y MEMORIA.docx"
TEMPLATE_XLSX = SCRIPT_DIR / "FORMATO DE PROFORMA RECREADO VACÍO.xlsm"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent":      USER_AGENT,
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# Listas de proveedores de confianza (se inyectan en el prompt de búsqueda)
PROVEEDORES_NACIONALES = [
    "https://mibodega.ec/", "https://bodeguitadelahorro.com/", "https://comercialvaca.ec/",
    "https://kissu.com.ec/", "https://altatenalmacen.com.ec/", "https://www.tventas.com/",
    "https://store.intcomex.com/es-XPE/Home", "https://lavictoria.ec/", "https://www.marcimex.com/",
    "https://almacenesespana.ec/", "https://www.novicompu.com/", "https://technoprimec.com/",
    "https://point.com.ec/", "https://www.computron.com.ec/", "https://nomadaware.com.ec/",
    "https://www.idcmayoristas.com/", "https://tecnit.com.ec/", "https://tecnomegastore.ec/",
    "https://www.artefacta.com/", "https://mundotek.com.ec/", "https://eljuri.store/",
    "https://www.kywi.com.ec/", "https://tecnocostoec.com/", "https://www.almacenesjapon.com/",
    "https://electromegaecuador.com/", "https://www.compraecuador.com/", "https://granhogar.com.ec/",
    "https://miamihome-ec.com/",
]
PROVEEDORES_EXTRANJEROS = [
    "https://www.amazon.com/", "https://www.mercadolibre.com.mx/", "https://www.mercadolibre.com.co/",
    "https://www.mercadolibre.com.ar/", "https://www.mercadolibre.cl/", "https://www.mercadolibre.com.pe/",
    "https://www.ebay.com/", "https://www.walmart.com/", "https://www.bestbuy.com/",
    "https://www.homedepot.com/", "https://www.costco.com/",
]

def _dominio(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""

DOMINIOS_NACIONALES = [d for d in (_dominio(u) for u in PROVEEDORES_NACIONALES) if d]
DOMINIOS_EXTRANJEROS = [d for d in (_dominio(u) for u in PROVEEDORES_EXTRANJEROS) if d]

# Respaldo opcional de búsqueda de imágenes (no crítico si no está instalado)
try:
    from ddgs import DDGS
except Exception:
    DDGS = None

_URL_CACHE: Dict[str, bool] = {}

# ═══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES BÁSICAS
# ═══════════════════════════════════════════════════════════════════════════════

def log(msg, nivel="INFO"):
    iconos = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌"}
    print(f"{iconos.get(nivel,'  ')} [{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def paso(n, total, desc):
    print(f"\n{'─'*60}\n  PASO {n}/{total}: {desc}\n{'─'*60}", flush=True)

def _get_session():
    import requests
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session

def resolver_credenciales_a_archivo():
    """GEMINI_CREDENTIALS puede ser una ruta a un JSON o el JSON en texto plano."""
    raw = GEMINI_CREDENTIALS_PATH
    if raw is None:
        raise ValueError("GEMINI_CREDENTIALS_PATH no definida.")
    stripped = raw.strip()
    if stripped.startswith("{"):
        creds_dict = json.loads(stripped)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(creds_dict, tmp)
        tmp.close()
        log("Credenciales resueltas desde variable de entorno.")
        return tmp.name
    log(f"Credenciales resueltas desde archivo: {stripped}")
    return stripped

def _parsear_json_de_respuesta(raw):
    """Extrae el primer objeto/array JSON válido de la respuesta del modelo."""
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for ch_open, ch_close in [("{", "}"), ("[", "]")]:
            i = raw.find(ch_open)
            if i < 0:
                continue
            depth = 0
            for j in range(i, len(raw)):
                if raw[j] == ch_open:
                    depth += 1
                elif raw[j] == ch_close:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[i:j + 1])
                        except Exception:
                            break
    return None

def _num(valor, defecto=0.0):
    """Convierte de forma segura a float (acepta '1.234,56', '$1,234.56', None, etc.)."""
    if valor is None:
        return defecto
    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except Exception:
            return defecto
    s = str(valor)
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s:
        return defecto
    # formato europeo 1.234,56
    if re.match(r"^-?\d{1,3}(\.\d{3})+,\d{1,2}$", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return defecto

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))

def _sanitizar_nombre_archivo(nombre: str) -> str:
    """Solo reemplaza caracteres ilegales en nombres de archivo (conserva acentos)."""
    return re.sub(r'[\\/:*?"<>|]', "_", str(nombre)).strip()

def _es_fuera_de_guayaquil(direccion: str) -> bool:
    return "guayaquil" not in (direccion or "").lower()

def _envio_clamp(envio: float, fuera: bool) -> float:
    """Acota el costo de envío/aduana según la dirección de entrega.
       Fuera de Guayaquil: [ENVIO_MIN, ENVIO_MAX]; en Guayaquil: [0, ENVIO_MAX]."""
    if fuera:
        return _clamp(envio if envio > 0 else ENVIO_MIN, ENVIO_MIN, ENVIO_MAX)
    return _clamp(envio, 0.0, ENVIO_MAX)

def _numero_proforma(id_infima) -> str:
    """8 dígitos fijos (00100100) + id_infima a la derecha, total 11 dígitos.
       21 → 00100100021 | 5 → 00100100005 | 1234 → 00100101234."""
    s = str(id_infima)
    base = "00100100000"  # 11 chars
    if len(s) >= len(base):
        return s[-len(base):]
    return base[:len(base) - len(s)] + s


# ═══════════════════════════════════════════════════════════════════════════════
#  VERTEX AI / GEMINI  (SDK google-genai)
# ═══════════════════════════════════════════════════════════════════════════════

from google import genai
from google.genai import types

_GENAI_CLIENT = None

def get_genai_client():
    """Cliente google-genai sobre Vertex AI (endpoint global)."""
    global _GENAI_CLIENT
    if _GENAI_CLIENT is not None:
        return _GENAI_CLIENT
    from google.oauth2 import service_account
    creds_path = resolver_credenciales_a_archivo()
    with open(creds_path, "r", encoding="utf-8") as f:
        project_id = json.load(f)["project_id"]
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    _GENAI_CLIENT = genai.Client(
        vertexai=True, project=project_id, location=VERTEX_LOCATION,
        credentials=creds, http_options=types.HttpOptions(api_version="v1"),
    )
    log(f"Cliente Vertex AI (google-genai) inicializado — proyecto {project_id}, location={VERTEX_LOCATION}", "OK")
    return _GENAI_CLIENT

def _texto_de_respuesta(resp) -> str:
    """Extrae texto de la respuesta de google-genai de forma robusta."""
    try:
        t = resp.text
        if t:
            return t
    except Exception:
        pass
    partes = []
    for cand in (getattr(resp, "candidates", None) or []):
        content = getattr(cand, "content", None)
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "text", None):
                partes.append(part.text)
    return "\n".join(partes)

def generar(client, contents, use_search=False, prefer_complex=True,
            max_intentos=3, espera_inicial=8) -> str:
    """
    Llama a Gemini con reintentos ante errores transitorios y fallback de modelo.
    - prefer_complex=True  → intenta MODEL_COMPLEX y luego MODEL_SIMPLE.
    - use_search=True      → habilita Google Search (grounding).
    Devuelve SIEMPRE texto (cadena vacía si no hubo contenido).
    """
    modelos = [MODEL_COMPLEX, MODEL_SIMPLE] if prefer_complex else [MODEL_SIMPLE]
    cfg = None
    if use_search:
        cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    ultimo_error = None
    for modelo in modelos:
        for intento in range(1, max_intentos + 1):
            try:
                resp = client.models.generate_content(model=modelo, contents=contents, config=cfg)
                return _texto_de_respuesta(resp)
            except Exception as e:
                ultimo_error = e
                msg = str(e).lower()
                transitorio = any(t in msg for t in
                                  ["503", "500", "429", "deadline", "unavailable", "rate",
                                   "exhaust", "quota", "resource", "overloaded"])
                if intento < max_intentos and transitorio:
                    espera = espera_inicial * (2 ** (intento - 1))
                    log(f"  Gemini '{modelo}' error transitorio (intento {intento}/{max_intentos}); "
                        f"reintentando en {espera}s.", "WARN")
                    time.sleep(espera)
                    continue
                log(f"  Gemini '{modelo}' falló: {str(e)[:160]}", "WARN")
                break  # pasar al siguiente modelo (fallback)
    if ultimo_error:
        raise ultimo_error
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 1 — BASE DE DATOS (MySQL)
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_data_table_1():
    """Devuelve las ínfimas 'en generacion' con las columnas requeridas (incluye id_infima)."""
    import mysql.connector
    log("Conectando a MySQL…")
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_infima, codigo_necesidad, entidad_contratante, entidad_contratante_url,
               direccion_entrega, contacto
        FROM   infimas
        WHERE  LOWER(etapa) = 'en generacion'
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    log(f"Registros 'en generacion' encontrados: {len(rows)}", "OK")
    for r in rows:
        log(f"  → id {r['id_infima']} | {r['codigo_necesidad']} | {r['entidad_contratante']}")
    return rows

def actualizar_etapa_bd(codigo_necesidad):
    import mysql.connector
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE infimas SET etapa='finalizada' "
        "WHERE codigo_necesidad=%s AND LOWER(etapa)='en generacion'",
        (codigo_necesidad,),
    )
    filas = cursor.rowcount
    conn.commit(); cursor.close(); conn.close()
    if filas:
        log(f"  BD actualizada: {codigo_necesidad} → 'finalizada'", "OK")
    else:
        log(f"  BD: no se actualizó ningún registro para {codigo_necesidad}.", "WARN")


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 2 — GOOGLE CLOUD STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_cliente_gcs():
    from google.oauth2 import service_account
    from google.cloud import storage
    creds_path = resolver_credenciales_a_archivo()
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return storage.Client(credentials=creds, project=creds.project_id)

def listar_docs_necesidad(gcs_client, codigo_necesidad):
    bucket  = gcs_client.bucket(BUCKET_NAME)
    prefijo = f"{BUCKET_FOLDER}/{codigo_necesidad}/"
    blobs   = list(gcs_client.list_blobs(bucket, prefix=prefijo))
    docs    = [b for b in blobs if b.name.lower().endswith((".doc", ".docx", ".pdf"))]
    log(f"  Documentos encontrados para {codigo_necesidad}: {len(docs)}")
    return docs

def descargar_blob_a_tmp(blob):
    suffix = Path(blob.name).suffix
    tmp    = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    blob.download_to_filename(tmp.name)
    return tmp.name

def subir_archivo_a_bucket(gcs_client, local_path, carpeta_destino):
    bucket    = gcs_client.bucket(BUCKET_NAME)
    nombre    = Path(local_path).name
    blob_name = f"{carpeta_destino}/{nombre}"
    blob      = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    log(f"  Subido: {blob_name}", "OK")
    return blob_name

def verificar_blob_en_bucket(gcs_client, blob_name):
    bucket = gcs_client.bucket(BUCKET_NAME)
    try:
        b = bucket.blob(blob_name)
        b.reload()
        return b.exists() and (b.size or 0) > 0
    except Exception as e:
        log(f"  No se pudo verificar {blob_name}: {e}", "WARN")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 3 — ANÁLISIS DE DOCUMENTOS CON GEMINI
# ═══════════════════════════════════════════════════════════════════════════════

def docx_a_pdf(docx_path):
    """Convierte .doc/.docx a PDF con LibreOffice para enviarlo a Gemini como PDF."""
    import subprocess
    out_dir = tempfile.mkdtemp()
    try:
        res = subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
            capture_output=True, text=True, timeout=120,
        )
        if res.returncode != 0:
            log(f"    LibreOffice error: {res.stderr[:160]}", "WARN")
            return None
        pdf_path = Path(out_dir) / (Path(docx_path).stem + ".pdf")
        if not pdf_path.exists():
            return None
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf"); tmp.close()
        shutil.copy2(str(pdf_path), tmp.name)
        shutil.rmtree(out_dir, ignore_errors=True)
        return tmp.name
    except FileNotFoundError:
        log("    LibreOffice no encontrado (soffice).", "WARN")
        return None
    except subprocess.TimeoutExpired:
        log("    Conversión a PDF superó 120s.", "WARN")
        return None
    except Exception as e:
        log(f"    Error al convertir a PDF: {e}", "WARN")
        return None

def _archivo_a_part_pdf(path_local):
    """Devuelve un types.Part PDF (convirtiendo .doc/.docx si hace falta)."""
    suf = Path(path_local).suffix.lower()
    pdf_path = path_local
    if suf != ".pdf":
        pdf_path = docx_a_pdf(path_local)
        if not pdf_path:
            return None
    try:
        size_mb = Path(pdf_path).stat().st_size / (1024 * 1024)
        if size_mb > 18:
            log(f"    PDF muy grande ({size_mb:.1f} MB), omitido.", "WARN")
            return None
        with open(pdf_path, "rb") as f:
            data = f.read()
        return types.Part.from_bytes(data=data, mime_type="application/pdf")
    except Exception as e:
        log(f"    No se pudo preparar PDF: {e}", "WARN")
        return None

def analizar_documentos(client, archivos_locales, codigo_necesidad):
    """
    Envía los documentos del bucket a Gemini 3 y devuelve:
      {"articulos": [ {nombre_articulo, marca, modelo, cantidad, caracteristicas[],
                       especificaciones_tecnicas[], especificaciones_electricas[],
                       incluye[], resumen, funcion_principal} ], "n": <int> }
    """
    partes = []
    for path in archivos_locales:
        part = _archivo_a_part_pdf(path)
        if part is not None:
            partes.append(part)
            log(f"    Documento cargado: {Path(path).name}")
        else:
            log(f"    Documento omitido: {Path(path).name}", "WARN")
    if not partes:
        log("No hay documentos válidos para analizar.", "ERR")
        return None

    prompt = f"""Eres un analista experto en contratación pública del Ecuador (ínfima cuantía).
Analiza TODOS los documentos adjuntos del código de necesidad: {codigo_necesidad}.

Identifica CADA artículo de compra DISTINTO solicitado (no repitas variantes del mismo
artículo). Para cada artículo extrae nombre, marca y modelo si se especifican; si NO se
especifican, deja esos campos vacíos (luego se buscarán en la web). Extrae la CANTIDAD
solicitada de cada artículo. Sé exhaustivo en características y especificaciones.

Devuelve ÚNICAMENTE un JSON válido (sin markdown, sin texto adicional):
{{
  "articulos": [
    {{
      "nombre_articulo": "Nombre exacto del artículo solicitado",
      "marca": "Marca exacta o cadena vacía",
      "modelo": "Modelo exacto o cadena vacía",
      "cantidad": 1,
      "caracteristicas": ["al menos 7 características generales si es posible"],
      "especificaciones_tecnicas": ["al menos 10 especificaciones técnicas si es posible"],
      "especificaciones_electricas": ["especificaciones eléctricas o [] si no aplica"],
      "incluye": ["accesorios/extras que debe incluir o [] si no se indica"],
      "resumen": "Descripción de 50 a 80 palabras del artículo solicitado",
      "funcion_principal": "Para qué sirve / requisito esencial que debe cumplir"
    }}
  ]
}}

REGLAS:
- Un objeto por cada artículo DISTINTO.
- La cantidad debe provenir de los documentos (si no se indica, usa 1).
- No inventes marcas/modelos que el documento no menciona; déjalos vacíos.
"""
    log(f"  Enviando {len(partes)} documento(s) a Gemini para análisis…")
    texto = generar(client, partes + [prompt], use_search=False, prefer_complex=True)
    data = _parsear_json_de_respuesta(texto)
    if not data:
        log(f"  No se pudo parsear el análisis. Inicio respuesta: {texto[:200]}", "ERR")
        return None
    if isinstance(data, list):
        data = {"articulos": data}
    articulos = data.get("articulos") or []
    if not isinstance(articulos, list) or not articulos:
        log("  El análisis no devolvió artículos.", "ERR")
        return None
    # Normalizar mínimos
    for a in articulos:
        a.setdefault("marca", ""); a.setdefault("modelo", "")
        a.setdefault("cantidad", 1)
        try:
            a["cantidad"] = max(1, int(round(_num(a.get("cantidad", 1), 1))))
        except Exception:
            a["cantidad"] = 1
        for k in ("caracteristicas", "especificaciones_tecnicas",
                  "especificaciones_electricas", "incluye"):
            if not isinstance(a.get(k), list):
                a[k] = []
        a.setdefault("resumen", ""); a.setdefault("funcion_principal", "")
    data["articulos"] = articulos
    data["n"] = len(articulos)
    log(f"  Análisis completado: {len(articulos)} artículo(s) distinto(s).", "OK")
    for i, a in enumerate(articulos, 1):
        log(f"    {i}. {str(a.get('nombre_articulo',''))[:60]} (x{a.get('cantidad',1)})")
    return data


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDACIÓN DE URLS E IMÁGENES + DESCARGA
# ═══════════════════════════════════════════════════════════════════════════════

def validar_url(url, timeout=10):
    """True si la URL responde HTTP < 400 (la IA suele inventar enlaces)."""
    import requests
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return False
    if url in _URL_CACHE:
        return _URL_CACHE[url]
    ok = False
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                         allow_redirects=True, stream=True)
        ok = r.status_code < 400
        r.close()
    except Exception:
        ok = False
    _URL_CACHE[url] = ok
    return ok

def validar_url_imagen(url, timeout=10):
    """True si la URL devuelve realmente una imagen (Content-Type + tamaño)."""
    import requests
    if not url or not isinstance(url, str) or not url.startswith("http") or "localhost" in url:
        return False
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                         allow_redirects=True, stream=True)
        if r.status_code >= 400:
            return False
        ct = (r.headers.get("Content-Type") or "").lower()
        if not ct.startswith("image/"):
            return False
        chunk = next(r.iter_content(chunk_size=2048), b"")
        r.close()
        return len(chunk) >= 512
    except Exception:
        return False

def fetch_html(url, timeout=15, max_bytes=400_000):
    import requests
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                         allow_redirects=True, stream=True)
        if r.status_code >= 400:
            return None
        chunks, leido = [], 0
        for chunk in r.iter_content(chunk_size=8192, decode_unicode=False):
            if not chunk:
                break
            chunks.append(chunk)
            leido += len(chunk)
            if leido >= max_bytes:
                break
        r.close()
        return b"".join(chunks).decode("utf-8", errors="ignore")
    except Exception:
        return None

def extraer_imagen_de_html(html_text, url_base):
    """Extrae la mejor URL de imagen del HTML (og:image, twitter:image, JSON-LD)."""
    if not html_text:
        return None
    patrones_meta = [
        r'<meta[^>]+property=["\']og:image:secure_url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:secure_url["\']',
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]
    for pat in patrones_meta:
        m = re.search(pat, html_text, re.IGNORECASE)
        if m:
            url = urllib.parse.urljoin(url_base, html.unescape(m.group(1)))
            if url.startswith("http") and "localhost" not in url:
                return url
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text, re.IGNORECASE | re.DOTALL
    ):
        try:
            data = json.loads(m.group(1).strip())
            for cand in (data if isinstance(data, list) else [data]):
                if not isinstance(cand, dict):
                    continue
                img = cand.get("image")
                if isinstance(img, str) and img.startswith("http"):
                    return img
                if isinstance(img, list) and img:
                    p = img[0]
                    if isinstance(p, str) and p.startswith("http"):
                        return p
                    if isinstance(p, dict) and str(p.get("url", "")).startswith("http"):
                        return p["url"]
        except Exception:
            continue
    return None

def extraer_imagen_de_pagina(url, timeout=15):
    """Descarga el HTML de una página de producto y extrae su imagen principal."""
    if not url:
        return None
    html_text = fetch_html(url, timeout=timeout)
    if not html_text:
        return None
    img = extraer_imagen_de_html(html_text, url)
    if img and validar_url_imagen(img):
        return img
    return None

def descargar_imagen_producto(url_imagen):
    """Descarga una imagen (Referer para CDNs) y la deja como .png/.jpg local."""
    import requests
    if not url_imagen or "localhost" in url_imagen:
        return None
    try:
        parsed = urllib.parse.urlparse(url_imagen)
        referer = f"{parsed.scheme}://{parsed.netloc}/"
    except Exception:
        referer = "https://www.google.com/"
    headers = {**DEFAULT_HEADERS, "Referer": referer,
               "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"}
    try:
        r = requests.get(url_imagen, headers=headers, timeout=20)
        r.raise_for_status()
        ct = r.headers.get("content-type", "image/jpeg").lower()
        if "image" not in ct:
            return None
        ext = ".png" if "png" in ct else (".webp" if "webp" in ct else ".jpg")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(r.content); tmp.close()
        # convertir formatos no soportados por python-docx/openpyxl a PNG
        if ext == ".webp":
            try:
                from PIL import Image as PILImage
                im = PILImage.open(tmp.name).convert("RGB")
                tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".png"); tmp2.close()
                im.save(tmp2.name, "PNG")
                os.unlink(tmp.name)
                return tmp2.name
            except Exception as e:
                log(f"  No se pudo convertir webp: {e}", "WARN")
                os.unlink(tmp.name)
                return None
        log(f"  Imagen descargada: {len(r.content)//1024} KB", "OK")
        return tmp.name
    except Exception as e:
        log(f"  No se pudo descargar imagen: {e}", "WARN")
        return None

def buscar_imagen_ddg(query, nombre_producto=""):
    """Respaldo: busca una imagen relevante del producto vía DuckDuckGo."""
    if DDGS is None:
        return None
    try:
        keywords = set(re.findall(r"\b\w{4,}\b", (nombre_producto or query).lower()))
        with DDGS() as ddgs:
            resultados = list(ddgs.images(query, region="ec-es", max_results=10, safesearch="off"))
        # primero, imágenes cuyo título coincide con el producto
        for r in resultados:
            img_url = r.get("image", "")
            title = (r.get("title", "") or "").lower()
            if img_url and img_url.startswith("http") and any(k in title for k in list(keywords)[:5]):
                if validar_url_imagen(img_url):
                    return img_url
        # si no, la primera válida
        for r in resultados:
            img_url = r.get("image", "")
            if img_url and validar_url_imagen(img_url):
                return img_url
    except Exception as e:
        log(f"  Error buscando imagen (DDG): {e}", "WARN")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 4 — BÚSQUEDA DE PRODUCTOS (Gemini + Google Search grounding)
# ═══════════════════════════════════════════════════════════════════════════════

def _prompt_busqueda_articulo(info, direccion, n_articulos):
    nac = "\n".join(f"- {u}" for u in PROVEEDORES_NACIONALES)
    ext = "\n".join(f"- {u}" for u in PROVEEDORES_EXTRANJEROS)
    return f"""Eres un comprador profesional en Ecuador. Usa Google Search para encontrar UN producto
REAL y disponible que satisfaga el siguiente requerimiento de contratación pública.

ARTÍCULO SOLICITADO:
- Nombre: {info.get('nombre_articulo','')}
- Marca:  {info.get('marca','') or '(no especificada)'}
- Modelo: {info.get('modelo','') or '(no especificado)'}
- Cantidad: {info.get('cantidad',1)}
- Función principal: {info.get('funcion_principal','')}
- Características requeridas: {json.dumps(info.get('caracteristicas',[]), ensure_ascii=False)}
- Especificaciones requeridas: {json.dumps(info.get('especificaciones_tecnicas',[]), ensure_ascii=False)}
- Dirección de entrega: {direccion}

REGLAS DE SELECCIÓN:
1) El producto debe ser NUEVO y coincidir con lo solicitado (marca/modelo exactos si se
   especifican; si no, propón un producto que cumpla las características).
2) Busca PRIMERO en estos proveedores NACIONALES (Ecuador):
{nac}
3) Si no lo encuentras en los nacionales, busca en estos proveedores EXTRANJEROS:
{ext}
4) Si tras agotar las listas no aparece, propón un proveedor de Ecuador que lo tenga.
5) Elige la MEJOR opción = la de MENOR precio unitario que cumpla los requisitos. Si la mejor
   opción es extranjera, considera envío + aduanas hasta Guayaquil; aun con esos costos su
   total debe ser el menor.
6) Los enlaces (producto e imagen) DEBEN ser reales y accesibles (no inventes URLs).
7) La descripción y las características deben provenir de la página del proveedor o del
   fabricante y coincidir con lo solicitado.

Devuelve ÚNICAMENTE un JSON válido (sin markdown):
{{
  "encontrado": true,
  "nombre": "Nombre comercial del producto",
  "marca": "Marca",
  "modelo": "Modelo",
  "proveedor": "Nombre del proveedor elegido",
  "url_producto": "https://enlace-real-del-producto",
  "es_extranjero": false,
  "precio_unitario_usd": 0.0,
  "costo_envio_aduana_usd": 0.0,
  "requiere_instalacion": false,
  "costo_instalacion_unitario_usd": 0.0,
  "descripcion": "Resumen de 50 a 80 palabras tomado del proveedor/fabricante",
  "caracteristicas": ["al menos 7 características generales"],
  "especificaciones_tecnicas": ["al menos 10 especificaciones técnicas"],
  "especificaciones_electricas": ["especificaciones eléctricas o []"],
  "incluye": ["accesorios/extras incluidos o []"],
  "imagen_url": "https://enlace-real-de-la-imagen",
  "imagenes_adicionales": ["otras imágenes reales del MISMO producto"],
  "alternativas": ["url-2da-mejor-opcion", "url-3ra", "url-4ta"]
}}

- "costo_envio_aduana_usd": costo logístico TOTAL estimado para traer la cantidad solicitada
  hasta la dirección de entrega (incluye aduana si es extranjero). Para entregas fuera de
  Guayaquil suele ser de 86 a 155 USD.
- "costo_instalacion_unitario_usd": mano de obra por unidad si el artículo requiere instalación
  (entre 60 y 80 USD); 0 si no requiere.
- "alternativas": hasta 3 URLs reales de las siguientes mejores opciones, en orden decreciente
  de conveniencia. [] si no hay.
- Si NO encuentras ningún producto adecuado, devuelve {{"encontrado": false}}.
"""

def _resolver_imagen(res, nombre):
    """Devuelve una ruta local de imagen válida usando varios respaldos."""
    candidatas = []
    if res.get("imagen_url"):
        candidatas.append(res["imagen_url"])
    # imagen extraída de la propia página del producto
    if res.get("url_producto"):
        img_pag = extraer_imagen_de_pagina(res["url_producto"])
        if img_pag:
            candidatas.append(img_pag)
    candidatas.extend([u for u in (res.get("imagenes_adicionales") or []) if u])
    # respaldo final: búsqueda de imágenes
    query = " ".join(x for x in [res.get("marca", ""), res.get("modelo", ""),
                                 res.get("nombre", "") or nombre] if x).strip()
    img_ddg = buscar_imagen_ddg(query, res.get("nombre", "") or nombre)
    if img_ddg:
        candidatas.append(img_ddg)

    vistas = set()
    for url in candidatas:
        if not url or url in vistas:
            continue
        vistas.add(url)
        if validar_url_imagen(url):
            local = descargar_imagen_producto(url)
            if local and Path(local).exists():
                return local, url
    return None, ""

def _resolver_url_producto(res):
    """Garantiza que url_producto sea accesible; si no, usa una alternativa válida."""
    url = res.get("url_producto", "")
    if url and validar_url(url):
        return url
    for alt in (res.get("alternativas") or []):
        if alt and validar_url(alt):
            log(f"    URL principal inválida; se usa alternativa verificada.", "WARN")
            return alt
    return url  # se conserva la propuesta aunque no se haya podido verificar

def buscar_articulo(client, info, direccion, n_articulos, descargar_imagenes=True):
    """
    Busca el producto para un artículo y devuelve un dict NORMALIZADO con todo lo
    necesario para la ficha y la proforma (incluye imágenes ya descargadas).
    """
    nombre = info.get("nombre_articulo", "")
    log(f"  Buscando producto: {nombre[:60]} …")
    texto = generar(client, _prompt_busqueda_articulo(info, direccion, n_articulos),
                    use_search=True, prefer_complex=True)
    res = _parsear_json_de_respuesta(texto) or {}

    encontrado = bool(res.get("encontrado", True)) and bool(res.get("nombre") or res.get("url_producto"))
    qty = max(1, int(info.get("cantidad", 1) or 1))

    # Costos logísticos (con reglas/clamps de la especificación)
    fuera = _es_fuera_de_guayaquil(direccion)
    envio_total = _num(res.get("costo_envio_aduana_usd", 0.0))
    if fuera:
        envio_total = _clamp(envio_total if envio_total > 0 else ENVIO_MIN, ENVIO_MIN, ENVIO_MAX)
    else:
        envio_total = _clamp(envio_total, 0.0, ENVIO_MAX)
    requiere_inst = bool(res.get("requiere_instalacion", False))
    inst_unit = _num(res.get("costo_instalacion_unitario_usd", 0.0))
    inst_unit = _clamp(inst_unit, INSTAL_MIN, INSTAL_MAX) if (requiere_inst and inst_unit > 0) else (
        _clamp(INSTAL_MIN, INSTAL_MIN, INSTAL_MAX) if requiere_inst else 0.0)

    # Costo agregado UNITARIO:
    #   - mismo proveedor (A): el envío del pedido se reparte entre todos los artículos
    #   - distinto proveedor (G, operativo): cada artículo asume su propio envío
    extra_unit_mismo    = round(envio_total / max(1, n_articulos) / qty + inst_unit, 2)
    extra_unit_distinto = round(envio_total / qty + inst_unit, 2)

    # Listas; relleno desde el análisis si la búsqueda no las trajo
    def _lista(clave_busqueda, clave_info):
        v = res.get(clave_busqueda)
        if isinstance(v, list) and v:
            return v
        return info.get(clave_info, []) or []

    out = {
        "info": info,
        "encontrado": encontrado,
        "nombre": (res.get("nombre") or nombre or "").strip(),
        "marca": (res.get("marca") or info.get("marca", "") or "").strip(),
        "modelo": (res.get("modelo") or info.get("modelo", "") or "").strip(),
        "proveedor": (res.get("proveedor") or "").strip(),
        "es_extranjero": bool(res.get("es_extranjero", False)),
        "precio_unitario_usd": round(_num(res.get("precio_unitario_usd", 0.0)), 2),
        "cantidad": qty,
        "costo_envio_total_usd": round(envio_total, 2),
        "costo_instalacion_unitario_usd": round(inst_unit, 2),
        "extra_unit_mismo_usd": extra_unit_mismo,
        "extra_unit_distinto_usd": extra_unit_distinto,
        "descripcion": (res.get("descripcion") or info.get("resumen", "") or "").strip(),
        "caracteristicas": _lista("caracteristicas", "caracteristicas"),
        "especificaciones_tecnicas": _lista("especificaciones_tecnicas", "especificaciones_tecnicas"),
        "especificaciones_electricas": _lista("especificaciones_electricas", "especificaciones_electricas"),
        "incluye": _lista("incluye", "incluye"),
        "alternativas": [u for u in (res.get("alternativas") or []) if u][:3],
        "imagen_local": None,
        "imagen_url": "",
        "imagenes_adicionales_local": [],
    }

    out["url_producto"] = _resolver_url_producto(res)

    if descargar_imagenes:
        img_local, img_url = _resolver_imagen(res, out["nombre"])
        out["imagen_local"] = img_local
        out["imagen_url"] = img_url
        if not img_local:
            log("    Sin imagen disponible para el producto.", "WARN")
        # imágenes adicionales para el final de la ficha (máx. 2)
        for u in (res.get("imagenes_adicionales") or [])[:3]:
            if u and u != img_url and validar_url_imagen(u):
                p = descargar_imagen_producto(u)
                if p:
                    out["imagenes_adicionales_local"].append(p)
            if len(out["imagenes_adicionales_local"]) >= 2:
                break

    estado = "OK" if encontrado else "WARN"
    log(f"    Producto: {out['nombre'][:55]} | ${out['precio_unitario_usd']:.2f} | "
        f"{'extranjero' if out['es_extranjero'] else 'nacional'} | "
        f"{'con imagen' if out['imagen_local'] else 'sin imagen'}", estado)
    return out

def buscar_todos_los_articulos(client, articulos, direccion, descargar_imagenes=True):
    n = len(articulos)
    resultados = []
    for i, info in enumerate(articulos, 1):
        log(f"\n  [{i}/{n}] {str(info.get('nombre_articulo',''))[:60]}")
        try:
            resultados.append(buscar_articulo(client, info, direccion, n, descargar_imagenes))
        except Exception as e:
            log(f"    Error buscando artículo {i}: {e}", "WARN")
            resultados.append({
                "info": info, "encontrado": False,
                "nombre": info.get("nombre_articulo", ""),
                "marca": info.get("marca", ""), "modelo": info.get("modelo", ""),
                "proveedor": "", "es_extranjero": False,
                "precio_unitario_usd": 0.0, "cantidad": max(1, int(info.get("cantidad", 1) or 1)),
                "costo_envio_total_usd": 0.0, "costo_instalacion_unitario_usd": 0.0,
                "extra_unit_mismo_usd": 0.0, "extra_unit_distinto_usd": 0.0,
                "descripcion": info.get("resumen", ""),
                "caracteristicas": info.get("caracteristicas", []),
                "especificaciones_tecnicas": info.get("especificaciones_tecnicas", []),
                "especificaciones_electricas": info.get("especificaciones_electricas", []),
                "incluye": info.get("incluye", []),
                "alternativas": [], "url_producto": "",
                "imagen_local": None, "imagen_url": "", "imagenes_adicionales_local": [],
            })
    return resultados


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 5 — GENERACIÓN DE LA FICHA TÉCNICA (.docx)
# ═══════════════════════════════════════════════════════════════════════════════

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


def _set_fuente(run, nombre="Century Gothic", size=11, bold=False, italic=False, color=None):
    """Aplica fuente/atributos a un run y fija rFonts (ascii/hAnsi/cs)."""
    run.font.name = nombre
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(attr), nombre)


def _add_par(doc, texto="", size=11, bold=False, italic=False, align=None,
             color=None, space_after=6, space_before=0):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    if texto:
        _set_fuente(p.add_run(texto), size=size, bold=bold, italic=italic, color=color)
    return p


def _add_bullet(doc, texto, size=10):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Pt(18)          # 360 twips
    pf.first_line_indent = Pt(-18)   # sangría francesa
    pf.space_after = Pt(2)
    _set_fuente(p.add_run("•  " + str(texto)), size=size)
    return p


def _add_image_centered(doc, path, width_in=3.3):
    if not path or not os.path.exists(path):
        return False
    try:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(6)
        p.add_run().add_picture(path, width=Inches(width_in))
        return True
    except Exception as e:
        log(f"    No se pudo insertar imagen en la ficha: {e}", "WARN")
        return False


def _abrir_plantilla_docx_limpia():
    """Clona la plantilla y vacía el cuerpo conservando sectPr (tamaño A4,
       márgenes, encabezado y pie con membrete, y las fuentes embebidas)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp.close()
    shutil.copy(str(TEMPLATE_DOCX), tmp.name)
    doc = Document(tmp.name)
    body = doc.element.body
    sectPr = body.find(qn("w:sectPr"))
    for child in list(body):
        if child is not sectPr:
            body.remove(child)
    return doc, tmp.name


def generar_ficha_tecnica(resultados, codigo, id_infima, directorio):
    """Genera la ficha técnica .docx (un bloque por artículo) según la especificación."""
    doc, tmp_base = _abrir_plantilla_docx_limpia()
    try:
        for idx, r in enumerate(resultados):
            nombre = (r.get("nombre") or r.get("info", {}).get("nombre_articulo")
                      or f"Artículo {idx + 1}").strip()
            # Título (negrita, centrado) — salto de página antes de cada artículo (salvo el 1.º)
            p_title = _add_par(doc, nombre, size=14, bold=True,
                               align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=4)
            if idx > 0:
                p_title.paragraph_format.page_break_before = True

            # Subtítulo marca/modelo (si existen)
            mm = " · ".join([x for x in [
                (f"Marca: {r['marca']}" if r.get("marca") else ""),
                (f"Modelo: {r['modelo']}" if r.get("modelo") else "")] if x])
            if mm:
                _add_par(doc, mm, size=10, italic=True,
                         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)

            # Imagen principal (debajo del título)
            _add_image_centered(doc, r.get("imagen_local"), width_in=3.3)

            # Resumen / descripción (50-80 palabras), justificado
            desc = (r.get("descripcion") or "").strip()
            if desc:
                _add_par(doc, desc, size=11, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
                         space_before=6, space_after=8)

            # Secciones con viñetas
            secciones = [
                ("Características generales:", r.get("caracteristicas") or []),
                ("Especificaciones técnicas:", r.get("especificaciones_tecnicas") or []),
                ("Especificaciones eléctricas:", r.get("especificaciones_electricas") or []),
                ("Incluye:", r.get("incluye") or []),
            ]
            for titulo, items in secciones:
                items = [str(x).strip() for x in items if str(x).strip()]
                if not items:
                    continue
                _add_par(doc, titulo, size=11, bold=True, space_before=4, space_after=2)
                for it in items:
                    _add_bullet(doc, it, size=10)

            # Imágenes adicionales al final del bloque
            for img in (r.get("imagenes_adicionales_local") or []):
                _add_image_centered(doc, img, width_in=3.0)

        nombre_archivo = _sanitizar_nombre_archivo(f"{codigo}_Ficha_técnica_{id_infima}.docx")
        ruta = os.path.join(directorio, nombre_archivo)
        doc.save(ruta)
        log(f"  Ficha técnica generada: {nombre_archivo}", "OK")
        return ruta
    finally:
        try:
            os.remove(tmp_base)
        except Exception:
            pass


def generar_ficha_limite(codigo, id_infima, directorio):
    """Ficha con el ÚNICO mensaje rojo cuando se supera el límite de 10 artículos."""
    doc, tmp_base = _abrir_plantilla_docx_limpia()
    try:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(40)
        _set_fuente(
            p.add_run("La cantidad de artículos supera el límite permitido de 10 artículos de compra"),
            nombre="Arial", size=14, bold=True, color=RGBColor(0xFF, 0x00, 0x00),
        )
        nombre_archivo = _sanitizar_nombre_archivo(f"{codigo}_Ficha_técnica_{id_infima}.docx")
        ruta = os.path.join(directorio, nombre_archivo)
        doc.save(ruta)
        log(f"  Ficha de límite (> {LIMITE_ARTICULOS} artículos) generada: {nombre_archivo}", "WARN")
        return ruta
    finally:
        try:
            os.remove(tmp_base)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 6 — GENERACIÓN DE LA PROFORMA (.xlsm)
# ═══════════════════════════════════════════════════════════════════════════════

def _formatear_contacto(contacto):
    """Conserva solo nombre + correo/teléfono del contacto."""
    if not contacto:
        return ""
    s = str(contacto).strip()
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", s)
    phone = re.search(r"(?:\+?593[\s-]?|0)\d[\d\s-]{6,}\d", s)
    nombre = re.split(r"[\d,;|]|@", s)[0].strip(" -:·\t")
    partes = []
    if nombre:
        partes.append(nombre)
    if email:
        partes.append(email.group(0))
    if phone:
        partes.append(re.sub(r"\s+", " ", phone.group(0)).strip())
    return "  ·  ".join(partes) if partes else s


def _clave_proveedor(r, idx):
    """Clave para agrupar por proveedor: nombre normalizado o, en su defecto,
       el dominio de la URL del producto. Si no hay ninguno, se trata como único."""
    p = (r.get("proveedor") or "").strip().lower()
    if p:
        return p
    dom = _dominio(r.get("url_producto", ""))
    return dom if dom else f"__unico_{idx}__"


def _calcular_costos_por_proveedor(resultados, direccion):
    """
    Decide, por artículo, dónde va el costo extra (envío/aduana + instalación):

      • Proveedor COMPARTIDO (surte a MIN_ARTICULOS_PROVEEDOR_COMPARTIDO+ artículos):
        el costo extra UNITARIO va en la columna A y se conserva la fórmula de G,
        de modo que el costo del proveedor queda DISTRIBUIDO (promediado) entre
        todos sus productos. El envío del proveedor se consolida (un solo envío)
        y se reparte entre la cantidad total de unidades del grupo.

      • Proveedor ÚNICO (no coincide con ningún otro): el costo extra UNITARIO se
        escribe directamente en G (se suma directo al costo final de ese producto)
        y la columna A queda vacía.

    Devuelve una lista paralela a 'resultados' con {compartido, A, G}.
    """
    from collections import defaultdict

    fuera = _es_fuera_de_guayaquil(direccion)
    grupos = defaultdict(list)
    for i, r in enumerate(resultados):
        grupos[_clave_proveedor(r, i)].append(i)

    salida = [None] * len(resultados)
    for indices in grupos.values():
        compartido = len(indices) >= MIN_ARTICULOS_PROVEEDOR_COMPARTIDO
        if compartido:
            # Un solo envío consolidado por proveedor (estimado más alto del grupo).
            envios = [_num(resultados[i].get("costo_envio_total_usd", 0.0)) for i in indices]
            envio_grupo = _envio_clamp(max(envios) if envios else 0.0, fuera)
            q_grupo = sum(max(1, int(resultados[i].get("cantidad", 1) or 1)) for i in indices)
            envio_unit = envio_grupo / max(1, q_grupo)
            for i in indices:
                inst = _num(resultados[i].get("costo_instalacion_unitario_usd", 0.0))
                salida[i] = {"compartido": True, "A": round(envio_unit + inst, 2), "G": None}
        else:
            i = indices[0]
            qty = max(1, int(resultados[i].get("cantidad", 1) or 1))
            envio = _envio_clamp(_num(resultados[i].get("costo_envio_total_usd", 0.0)), fuera)
            inst = _num(resultados[i].get("costo_instalacion_unitario_usd", 0.0))
            salida[i] = {"compartido": False, "A": None, "G": round(envio / qty + inst, 2)}
    return salida


def generar_proforma(registro, resultados, directorio, id_infima):
    """Genera la proforma .xlsm modificando ÚNICAMENTE las celdas indicadas por la
       especificación, respetando la estructura de la plantilla (sin insertar/borrar
       filas, sin renombrar hojas)."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image as XLImage

    codigo    = registro.get("codigo_necesidad", "")
    entidad   = (registro.get("entidad_contratante") or "").upper()
    ent_url   = registro.get("entidad_contratante_url") or ""
    direccion = registro.get("direccion_entrega") or ""
    contacto  = _formatear_contacto(registro.get("contacto") or "")

    nombre_archivo = _sanitizar_nombre_archivo(f"{codigo}_Proforma_{id_infima}.xlsm")
    ruta = os.path.join(directorio, nombre_archivo)
    shutil.copy(str(TEMPLATE_XLSX), ruta)

    wb = load_workbook(ruta, keep_vba=True)
    ws_cot    = wb["Cotización "]    # ← nombre con espacio final (NO renombrar)
    ws_costos = wb["Costos"]

    def escribir_celda(ws, ref, valor):
        try:
            for mr in ws.merged_cells.ranges:
                if ref in mr:
                    ws[f"{get_column_letter(mr.min_col)}{mr.min_row}"].value = valor
                    return
            ws[ref].value = valor
        except Exception as e:
            log(f"    Error escribiendo en {ref}: {e}", "WARN")

    n = len(resultados)

    # ── HOJA "Cotización " ──────────────────────────────────────────────
    log("  Llenando hoja de Cotización…")
    escribir_celda(ws_cot, "B8",  entidad)
    escribir_celda(ws_cot, "B9",  str(codigo)[4:17])      # caracteres 5-17 del código
    escribir_celda(ws_cot, "B10", direccion)
    escribir_celda(ws_cot, "B11", contacto)
    escribir_celda(ws_cot, "D12", codigo)                 # celda de VALOR de la fila 12
    escribir_celda(ws_cot, "I3",  _numero_proforma(id_infima))
    escribir_celda(ws_cot, "I8",  datetime.date.today().strftime("%d/%m/%Y"))

    FILA_COT_INI = 16
    # Filas activas (16 .. 15+n)
    for i, r in enumerate(resultados):
        fila = FILA_COT_INI + i
        ws_cot.row_dimensions[fila].height = 220
        nombre_full = " ".join([x for x in [r.get("nombre", ""), r.get("marca", ""),
                                            r.get("modelo", "")] if x]).strip()
        escribir_celda(ws_cot, f"C{fila}", nombre_full)
        escribir_celda(ws_cot, f"G{fila}", r.get("cantidad", 1))
        img_path = r.get("imagen_local")
        if img_path and os.path.exists(img_path):
            try:
                xi = XLImage(img_path)
                target_h = 140
                if xi.height:
                    ratio = target_h / float(xi.height)
                    xi.height = target_h
                    xi.width = max(40, int(xi.width * ratio))
                xi.anchor = f"E{fila}"
                ws_cot.add_image(xi)
            except Exception as e:
                log(f"    No se pudo anclar imagen en proforma (fila {fila}): {e}", "WARN")

    # Filas de producto sobrantes (16+n .. 25): dejar en blanco
    for fila in range(FILA_COT_INI + n, 26):
        ws_cot[f"A{fila}"].value = None      # número de ítem (fórmula)
        escribir_celda(ws_cot, f"C{fila}", None)
        ws_cot[f"F{fila}"].value = None      # 'U'
        escribir_celda(ws_cot, f"G{fila}", None)
        ws_cot.row_dimensions[fila].height = 15

    # Fila 15 (muestra vestigial de la plantilla): neutralizar por completo
    # (vía escribir_celda para respetar las celdas combinadas, p. ej. C15:E15)
    for col in ("A", "B", "C", "D", "E", "F", "G", "H", "I"):
        escribir_celda(ws_cot, f"{col}15", None)
    ws_cot.row_dimensions[15].height = 15

    # ── HOJA "Costos" ───────────────────────────────────────────────────
    log("  Llenando hoja de Costos…")
    escribir_celda(ws_costos, "C7", ent_url)

    # Clasificación del costo extra por proveedor:
    #   • COMPARTIDO (2+ artículos): costo extra → columna A; se RESPETA la fórmula
    #     de G (=IF(F>0,$A$25/$B$25,0)), que promedia/distribuye el costo entre los
    #     productos del mismo proveedor.
    #   • ÚNICO: costo extra → se SOBRESCRIBE en G de esa fila; A se deja vacía
    #     (para no afectar el promedio de los compartidos).
    costos_prov = _calcular_costos_por_proveedor(resultados, direccion)
    hay_compartidos = any(c["compartido"] for c in costos_prov)

    FILA_COS_INI = 15
    # Filas activas (15 .. 14+n) — Cotización 16+i ↔ Costos 15+i
    for i, r in enumerate(resultados):
        fila = FILA_COS_INI + i
        escribir_celda(ws_costos, f"C{fila}", r.get("url_producto", ""))            # link mejor opción
        ws_costos[f"E{fila}"].value = round(_num(r.get("precio_unitario_usd", 0.0)), 2)  # costo unitario
        c = costos_prov[i]
        if c["compartido"]:
            ws_costos[f"A{fila}"].value = c["A"]   # → columna A; G conserva su fórmula
        else:
            ws_costos[f"A{fila}"].value = None     # A vacía
            ws_costos[f"G{fila}"].value = c["G"]   # costo extra directo (sobrescribe la fórmula)

    # Filas de costo sobrantes (15+n .. 24): limpiar la muestra de la columna A
    for fila in range(FILA_COS_INI + n, 25):
        ws_costos[f"A{fila}"].value = None

    # Si NINGÚN proveedor es compartido, A15:A24 queda vacía y A25=AVERAGE(A15:A24)
    # daría #DIV/0!. Se coloca un 0 (oculto por el formato ';;;') en A15 para
    # mantener la fórmula válida sin alterar ningún cálculo.
    if not hay_compartidos:
        ws_costos["A15"].value = 0

    # Alternativas (top-3 decrecientes) para los productos 1, 2 y 3
    bloques_alt = {0: [15, 16, 17], 1: [19, 20, 21], 2: [23, 24, 25]}
    for idx_prod, filas_alt in bloques_alt.items():
        if idx_prod < n:
            alts = resultados[idx_prod].get("alternativas") or []
            for k, fila_alt in enumerate(filas_alt):
                escribir_celda(ws_costos, f"J{fila_alt}", alts[k] if k < len(alts) else None)

    wb.save(ruta)
    log(f"  Proforma generada: {nombre_archivo}", "OK")
    return ruta


# ═══════════════════════════════════════════════════════════════════════════════
#  ORQUESTADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    inicio = time.time()
    print("\n" + "=" * 70)
    print("  PROYECTO NEXUS — GENERADOR DE FICHAS Y PROFORMAS (V3)")
    print("=" * 70)

    # 0) Clientes
    try:
        client = get_genai_client()
    except Exception as e:
        log(f"No se pudo inicializar Vertex AI/Gemini: {e}", "ERR")
        traceback.print_exc()
        return
    try:
        gcs = obtener_cliente_gcs()
    except Exception as e:
        log(f"No se pudo inicializar el cliente de GCS: {e}", "ERR")
        traceback.print_exc()
        return

    # 1) data_table_1
    try:
        registros = obtener_data_table_1()
    except Exception as e:
        log(f"No se pudo leer la base de datos: {e}", "ERR")
        traceback.print_exc()
        return
    if not registros:
        log("No hay ínfimas 'en generacion'. Nada que procesar.", "OK")
        return

    total = len(registros)
    resumen = {"ok": 0, "limite": 0, "error": 0}

    for n_reg, registro in enumerate(registros, 1):
        codigo    = registro.get("codigo_necesidad", "")
        id_infima = registro.get("id_infima", "")
        direccion = registro.get("direccion_entrega") or ""
        paso(n_reg, total, f"Código {codigo}  (id_infima {id_infima})")

        tmp_dir = tempfile.mkdtemp(prefix=f"nexus_{id_infima}_")
        descargas = []
        try:
            # a) Documentos del bucket
            docs = listar_docs_necesidad(gcs, codigo)
            if not docs:
                log(f"  Sin documentos en el bucket para {codigo}. Se omite.", "WARN")
                resumen["error"] += 1
                continue
            locales = []
            for b in docs:
                lp = descargar_blob_a_tmp(b)
                if lp:
                    locales.append(lp)
                    descargas.append(lp)

            # b) Análisis con Gemini
            analisis = analizar_documentos(client, locales, codigo)
            if not analisis:
                log(f"  No se pudo analizar la documentación de {codigo}. Se omite.", "ERR")
                resumen["error"] += 1
                continue
            n_art = analisis["n"]

            # c) Regla del límite de artículos (> 10)
            if n_art > LIMITE_ARTICULOS:
                log(f"  {n_art} artículos (> {LIMITE_ARTICULOS}). Ficha de límite, sin proforma.", "WARN")
                ruta_ficha = generar_ficha_limite(codigo, id_infima, tmp_dir)
                blob_ficha = subir_archivo_a_bucket(gcs, ruta_ficha, CARPETA_FICHAS)
                if verificar_blob_en_bucket(gcs, blob_ficha):
                    actualizar_etapa_bd(codigo)
                    resumen["limite"] += 1
                else:
                    log(f"  No se verificó la ficha de límite en GCS para {codigo}.", "WARN")
                    resumen["error"] += 1
                continue

            # d) Búsqueda de productos reales (grounding)
            resultados = buscar_todos_los_articulos(client, analisis["articulos"], direccion)

            # e) Ficha técnica → GCS
            ruta_ficha = generar_ficha_tecnica(resultados, codigo, id_infima, tmp_dir)
            blob_ficha = subir_archivo_a_bucket(gcs, ruta_ficha, CARPETA_FICHAS)

            # f) Proforma → GCS
            ruta_prof = generar_proforma(registro, resultados, tmp_dir, id_infima)
            blob_prof = subir_archivo_a_bucket(gcs, ruta_prof, CARPETA_PROFORMAS)

            # g) Verificación y actualización de etapa
            ok_ficha = verificar_blob_en_bucket(gcs, blob_ficha)
            ok_prof  = verificar_blob_en_bucket(gcs, blob_prof)
            if ok_ficha and ok_prof:
                actualizar_etapa_bd(codigo)
                resumen["ok"] += 1
                log(f"  ✔ {codigo} procesado correctamente.", "OK")
            else:
                log(f"  Verificación incompleta en GCS (ficha={ok_ficha}, proforma={ok_prof}). "
                    f"No se marca 'finalizada'.", "WARN")
                resumen["error"] += 1

        except Exception as e:
            log(f"  Error procesando {codigo}: {e}", "ERR")
            traceback.print_exc()
            resumen["error"] += 1
        finally:
            for f in descargas:
                try:
                    os.remove(f)
                except Exception:
                    pass
            shutil.rmtree(tmp_dir, ignore_errors=True)

    dur = time.time() - inicio
    print("\n" + "=" * 70)
    log(f"PROCESO FINALIZADO en {dur:.1f}s — OK: {resumen['ok']} | "
        f"Límite: {resumen['limite']} | Errores: {resumen['error']}", "OK")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
