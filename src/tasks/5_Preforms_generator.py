"""
Generador.py — Automatización de fichas técnicas y proformas.

Versión corregida que resuelve:
  Bug 1) No encontraba imágenes del producto.
         → Pipeline robusto multi-fuente con verificación de Content-Type.
  Bug 2) Generaba URLs falsas en los .xlsx (Gemini alucinaba).
         → Búsqueda real con DuckDuckGo HTML + verificación de contenido.
  Bug 3) URL del producto principal en hoja Costos iba a C15 → debe ir a K14
         (según funcionamiento del script y plantilla real).
  Bug 4) Subida de archivos a destinos específicos en el bucket:
         .docx → carpeta "Fichas Técnicas"  (nombre exacto)
         .xlsm → carpeta "Proformas"        (nombre exacto)
  Bug 5) Inicialización de Vertex AI grounding con dict en vez de Tool object
         (siempre fallaba el primer intento).
  Bug 6) PDFs grandes podían exceder el límite de Gemini → control de tamaño.
  Bug 7) Falta de reintentos ante errores transitorios de Vertex AI.
"""

import os, sys, json, shutil, tempfile, datetime, re, copy, io, time, hashlib
import mimetypes, traceback, urllib.parse, html
from pathlib import Path
import random
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

GEMINI_CREDENTIALS_PATH = Global.RENDER_CRENDENTIALS_JSON
BUCKET_NAME             = Global.BUCKET_NAME
BUCKET_FOLDER           = "Documentos de Contratación"
AI_MODEL                = "gemini-2.5-pro"

SCRIPT_DIR     = Path(__file__).parent
TEMPLATE_DOCX  = SCRIPT_DIR / "FICHA TECNICA MICROFONO Y MEMORIA.docx"
TEMPLATE_XLSX  = SCRIPT_DIR / "FORMATO DE PROFORMA RECREADO VACÍO.xlsm"

# User-Agent realista compartido para todas las peticiones HTTP
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://duckduckgo.com/",
    "Origin": "https://duckduckgo.com",
    "Connection": "keep-alive",
}

PROVEEDORES_NACIONALES = [
    "https://mibodega.ec/",
    "https://bodeguitadelahorro.com/",
    "https://comercialvaca.ec/",
    "https://www.instagram.com/comercialvaca.ec/",
    "https://kissu.com.ec/",
    "https://altatenalmacen.com.ec/",
    "https://www.tventas.com/",
    "https://store.intcomex.com/es-XPE/Home",
    "https://lavictoria.ec/",
    "https://www.marcimex.com/",
    "https://almacenesespana.ec/",
    "https://www.novicompu.com/",
    "https://technoprimec.com/",
    "https://point.com.ec/",
    "https://www.computron.com.ec/",
    "https://nomadaware.com.ec/",
    "https://www.idcmayoristas.com/",
    "https://tecnit.com.ec/",
    "https://tecnomegastore.ec/",
    "https://www.artefacta.com/",
    "https://mundotek.com.ec/",
    "https://eljuri.store/",
    "https://www.kywi.com.ec/",
    "https://tecnocostoec.com/",
    "https://www.almacenesjapon.com/",
    "https://electromegaecuador.com/",
    "https://www.compraecuador.com/",
    "https://granhogar.com.ec/",
    "https://miamihome-ec.com/",
]
PROVEEDORES_EXTRANJEROS = [
    "https://www.amazon.com/",
    "https://www.mercadolibre.com.hn/",
    "https://www.ebay.com/",
]

# Dominios derivados (para buscar con `site:`)
def _dominio(url):
    p = urllib.parse.urlparse(url)
    return p.netloc.lower().lstrip("www.")

DOMINIOS_NACIONALES  = [_dominio(u) for u in PROVEEDORES_NACIONALES if "instagram" not in u]
DOMINIOS_EXTRANJEROS = [_dominio(u) for u in PROVEEDORES_EXTRANJEROS]


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES BÁSICAS
# ═══════════════════════════════════════════════════════════════════════════════
def _get_session():
    import requests
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session

def log(msg, nivel="INFO"):
    iconos = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "STEP": "🔷"}
    print(f"{iconos.get(nivel,'  ')} [{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def paso(n, total, desc):
    print(f"\n{'─'*60}\n  PASO {n}/{total}: {desc}\n{'─'*60}", flush=True)

def resolver_credenciales_a_archivo():
    raw = GEMINI_CREDENTIALS_PATH
    if raw is None:
        raise ValueError("La variable RENDER_CRENDENTIALS_JSON no está definida.")
    stripped = raw.strip()
    if stripped.startswith("{"):
        creds_dict = json.loads(stripped)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(creds_dict, tmp)
        tmp.close()
        log("Credenciales resueltas desde variable de entorno (JSON string).")
        return tmp.name
    log(f"Credenciales resueltas desde archivo: {stripped}")
    return stripped


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDACIÓN ROBUSTA DE URLs (CORRECCIÓN BUG 1 y 2)
# ═══════════════════════════════════════════════════════════════════════════════

# Cache para no repetir validaciones costosas
_URL_CACHE = {}

def validar_url(url, timeout=12, verificar_contenido=False, terminos_requeridos=None):
    """
    Verifica que una URL existe y responde con HTTP 200-399.

    Mejoras respecto a la versión original:
      - Usa GET con stream=True (HEAD no es soportado por muchos CDNs).
      - Acepta lista `terminos_requeridos`: si se pasa, también verifica que
        al menos uno aparezca en el HTML (para detectar páginas de error 200).
      - Cachea resultados para no repetir peticiones.
    """
    import requests
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return False

    cache_key = (url, tuple(terminos_requeridos or ()))
    if cache_key in _URL_CACHE:
        return _URL_CACHE[cache_key]

    try:
        # GET con stream=True descarga sólo headers + comienzo del body
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                         allow_redirects=True, stream=True)
        if r.status_code >= 400:
            _URL_CACHE[cache_key] = False
            return False

        if not verificar_contenido and not terminos_requeridos:
            _URL_CACHE[cache_key] = True
            return True

        # Leer hasta 200 KB para verificar contenido
        chunks = []
        leido = 0
        for chunk in r.iter_content(chunk_size=8192, decode_unicode=False):
            if not chunk:
                break
            chunks.append(chunk)
            leido += len(chunk)
            if leido >= 200_000:
                break
        r.close()

        try:
            cuerpo = b"".join(chunks).decode("utf-8", errors="ignore").lower()
        except Exception:
            _URL_CACHE[cache_key] = True
            return True

        # Detectar páginas de error genéricas
        senales_404 = [
            "página no encontrada", "page not found", "404 not found",
            "producto no disponible", "no encontramos", "this page can",
            "error 404", "no se encontró",
        ]
        for senal in senales_404:
            if senal in cuerpo:
                _URL_CACHE[cache_key] = False
                return False

        if terminos_requeridos:
            terminos_norm = [t.lower() for t in terminos_requeridos if t and len(t) >= 2]
            if terminos_norm and not any(t in cuerpo for t in terminos_norm):
                _URL_CACHE[cache_key] = False
                return False

        _URL_CACHE[cache_key] = True
        return True

    except Exception:
        _URL_CACHE[cache_key] = False
        return False


def validar_url_imagen(url, timeout=10):
    """
    Verifica que una URL devuelve realmente una imagen.
    Comprueba:
      - HTTP 200-399.
      - Content-Type empieza por 'image/'.
      - El archivo pesa al menos 1 KB (descarta placeholders rotos).
    """
    import requests
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return False
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                         allow_redirects=True, stream=True)
        if r.status_code >= 400:
            return False
        ct = (r.headers.get("Content-Type") or "").lower()
        if not ct.startswith("image/"):
            return False
        # Leer un poco para asegurar que el cuerpo no está vacío
        chunk = next(r.iter_content(chunk_size=2048), b"")
        r.close()
        return len(chunk) >= 1024
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  BÚSQUEDA REAL EN INTERNET (Reemplaza la dependencia de Gemini para encontrar URLs)
# ═══════════════════════════════════════════════════════════════════════════════

def _ddg_html_search(query, max_results=10, timeout=25):
    import requests
    try:
        session = _get_session()

        r = session.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            timeout=timeout,
        )

        if r.status_code >= 400:
            return []

        urls = []

        # extracción por uddg
        for m in re.finditer(r'href="(?:(?:https?:)?//duckduckgo\.com)?/l/\?uddg=([^"&]+)', r.text):
            try:
                u = urllib.parse.unquote(m.group(1))
                if u.startswith("http"):
                    urls.append(u)
            except Exception:
                pass

        # extracción directa
        for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="(https?://[^"]+)"', r.text):
            urls.append(m.group(1))

        # deduplicación
        vistos = set()
        out = []
        for u in urls:
            if u not in vistos and "duckduckgo.com" not in u:
                vistos.add(u)
                out.append(u)
                if len(out) >= max_results:
                    break

        return out

    except requests.exceptions.ConnectTimeout:
        log("  DuckDuckGo timeout (red lenta o bloqueo).", "WARN")
        return []
    except requests.exceptions.ConnectionError:
        log("  Error de conexión a DuckDuckGo (posible bloqueo o DNS).", "WARN")
        return []
    except Exception as e:
        log(f"  DuckDuckGo HTML search falló: {e}", "WARN")
        return []

def _ddg_image_search(query, max_results=5, timeout=12):
    """
    Búsqueda de imágenes en DuckDuckGo.
    Implementación correcta: 1) obtener token vqd, 2) consultar i.js.
    """
    import requests
    try:
        # Paso 1: token vqd
        r1 = requests.get(
            "https://duckduckgo.com/",
            params={"q": query, "iar": "images", "iax": "images", "ia": "images"},
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        # vqd aparece en formato: vqd='...'  o vqd="..."  o vqd=...&
        m = re.search(r'vqd=["\']?(\d-[\d-]+)', r1.text)
        if not m:
            return []
        vqd = m.group(1)

        # Paso 2: consultar i.js
        r2 = requests.get(
            "https://duckduckgo.com/i.js",
            params={
                "l": "us-en",
                "o": "json",
                "q": query,
                "vqd": vqd,
                "f": ",,,,,",
                "p": "1",
            },
            headers={**DEFAULT_HEADERS, "Referer": "https://duckduckgo.com/"},
            timeout=timeout,
        )
        if r2.status_code >= 400:
            return []
        try:
            data = r2.json()
        except Exception:
            return []
        results = data.get("results", [])
        urls = []
        for it in results[:max_results * 3]:  # tomar más por si algunos fallan validación
            u = it.get("image") or it.get("thumbnail")
            if u and u.startswith("http"):
                urls.append(u)
        return urls
    except Exception as e:
        log(f"  DuckDuckGo Images search falló: {e}", "WARN")
        return []


def _bing_image_search(query, max_results=5, timeout=12):
    """
    Búsqueda de imágenes en Bing como respaldo.
    Bing devuelve un atributo `m="..."` con JSON conteniendo `murl` (URL real de la imagen).
    """
    import requests
    try:
        r = requests.get(
            "https://www.bing.com/images/search",
            params={"q": query, "form": "HDRSC2", "first": "1"},
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        if r.status_code >= 400:
            return []
        # Buscar todos los m="{...}"
        urls = []
        for m in re.finditer(r'm="([^"]+)"', r.text):
            try:
                meta = html.unescape(m.group(1))
                obj = json.loads(meta)
                u = obj.get("murl")
                if u and u.startswith("http"):
                    urls.append(u)
                    if len(urls) >= max_results * 2:
                        break
            except Exception:
                continue
        return urls
    except Exception as e:
        log(f"  Bing Images search falló: {e}", "WARN")
        return []


def _hay_marca_modelo_especificos(info_articulo):
    """
    Determina si los documentos de contratación especifican marca Y modelo
    concretos para el artículo. Si no, se entrará al modo "propuesta" donde
    la IA elegirá un artículo adecuado entre los proveedores autorizados.
    """
    marca  = (info_articulo.get("marca")  or "").strip().lower()
    modelo = (info_articulo.get("modelo") or "").strip().lower()
    indeterminados = {
        "", "no especificada", "no especificado", "no especifica", "n/a", "na",
        "ninguna", "ninguno", "genérico", "generico", "sin marca", "sin modelo",
        "no aplica", "varios", "various", "cualquiera", "—", "-",
    }
    return marca not in indeterminados and modelo not in indeterminados


def _construir_query_caracteristicas(info_articulo, max_terms=6):
    """
    Para el modo "propuesta": arma una consulta de búsqueda usando nombre del
    artículo + las características/especificaciones distintivas, ya que no
    contamos con marca/modelo.
    """
    nombre = (info_articulo.get("nombre_articulo") or "").strip()
    caract = info_articulo.get("caracteristicas", []) or []
    specs  = info_articulo.get("especificaciones_tecnicas", []) or []

    keywords = []
    for item in (caract + specs)[:8]:
        if not isinstance(item, str):
            continue
        # Si es "Etiqueta: valor", quedarse con el valor (más informativo)
        if ":" in item:
            etiq, val = item.split(":", 1)
            keywords.append(val.strip() if val.strip() else etiq.strip())
        else:
            keywords.append(item)

    # Tomar hasta `max_terms` palabras únicas y descriptivas
    palabras_extras = []
    palabras_unicas = set(w.lower() for w in nombre.split())
    for kw in keywords:
        for w in re.split(r"[\s,;]+", kw):
            w_low = w.strip().lower()
            if len(w_low) >= 3 and w_low not in palabras_unicas:
                palabras_extras.append(w.strip())
                palabras_unicas.add(w_low)
                if len(palabras_extras) >= max_terms:
                    break
        if len(palabras_extras) >= max_terms:
            break
    return f"{nombre} {' '.join(palabras_extras)}".strip()


def extraer_titulo_de_html(html_text):
    """
    Extrae un título descriptivo del producto desde el HTML.
    Prioriza: og:title → JSON-LD name → h1 → <title>.
    Devuelve None si no encuentra nada útil.
    """
    if not html_text:
        return None

    # og:title
    for pat in [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
    ]:
        m = re.search(pat, html_text, re.IGNORECASE)
        if m:
            t = html.unescape(m.group(1)).strip()
            if t:
                return t[:200]

    # JSON-LD "name"
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text, re.IGNORECASE | re.DOTALL
    ):
        try:
            data = json.loads(m.group(1).strip())
            candidatos = data if isinstance(data, list) else [data]
            for c in candidatos:
                if isinstance(c, dict):
                    n = c.get("name")
                    if isinstance(n, str) and n.strip():
                        return n.strip()[:200]
        except Exception:
            continue

    # <h1>
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.IGNORECASE | re.DOTALL)
    if m:
        t = re.sub(r"<[^>]+>", "", m.group(1))
        t = html.unescape(t).strip()
        if t:
            return t[:200]

    # <title>
    m = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    if m:
        t = html.unescape(m.group(1)).strip()
        if t:
            return t[:200]
    return None


def buscar_urls_producto_en_proveedores(nombre, marca, modelo, max_por_proveedor=2,
                                        query_base=None):
    """
    Búsqueda directa en internet de URLs reales del producto en los dominios
    de los proveedores autorizados. Devuelve lista de dicts:
      [{ "url": ..., "es_extranjero": bool, "dominio": ... }, ...]

    Esto reemplaza la dependencia de Gemini para "encontrar URLs" — Gemini ya
    no inventa URLs porque le entregamos URLs reales y le pedimos analizar.

    Si se pasa `query_base`, se usa esa cadena como consulta base (modo
    "propuesta", sin marca/modelo). En caso contrario, se construye con
    nombre+marca+modelo (modo "exacto").
    """
    consultas = []
    if query_base:
        base = query_base.strip()
    else:
        base = " ".join(x for x in (nombre, marca, modelo) if x).strip()
    if not base:
        return []

    # Construir consultas con `site:` para cada dominio
    for dom in DOMINIOS_NACIONALES:
        consultas.append((f"{base} site:{dom}", False, dom))
    for dom in DOMINIOS_EXTRANJEROS:
        consultas.append((f"{base} site:{dom}", True, dom))

    encontrados = []
    log(f"  Buscando '{base}' en {len(consultas)} dominios autorizados…")

    for q, es_ext, dom in consultas:
        urls = _ddg_html_search(q, max_results=max_por_proveedor)

        if not urls:
            log("  DDG falló, usando Bing como fallback...", "WARN")
            urls = _bing_image_search(q, max_results=max_por_proveedor)
        for u in urls:
            # Filtrar solo URLs que realmente pertenezcan al dominio buscado
            if dom in u.lower():
                encontrados.append({"url": u, "es_extranjero": es_ext, "dominio": dom})
        # Pequeña pausa para no ser bloqueado
        time.sleep(1.5 + random.uniform(0.5, 1.5))

    # Eliminar duplicados manteniendo orden
    vistos = set()
    out = []
    for it in encontrados:
        if it["url"] not in vistos:
            vistos.add(it["url"])
            out.append(it)

    log(f"  URLs candidatas encontradas: {len(out)}", "OK")
    return out


# ═══════════════════════════════════════════════════════════════════════════════
#  EXTRACCIÓN DE DATOS DE PÁGINAS DE PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_html(url, timeout=15, max_bytes=600_000):
    """Descarga HTML de una URL y devuelve string. Limitado para no consumir RAM."""
    import requests
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                         allow_redirects=True, stream=True)
        if r.status_code >= 400:
            return None
        chunks = []
        leido = 0
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
    """
    Extrae la mejor URL de imagen del HTML de una página de producto.
    Estrategias en orden de preferencia:
      1) <meta property="og:image:secure_url" content="...">
      2) <meta property="og:image" content="...">
      3) <meta name="twitter:image" content="...">
      4) <link rel="image_src" href="...">
      5) JSON-LD con "image": "..." o ["..."]
      6) Primer <img> con src.jpg/.jpeg/.png/.webp y dimensiones razonables.
    """
    if not html_text:
        return None

    # 1-3) meta tags
    patrones_meta = [
        r'<meta[^>]+property=["\']og:image:secure_url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:secure_url["\']',
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    ]
    for pat in patrones_meta:
        m = re.search(pat, html_text, re.IGNORECASE)
        if m:
            url = html.unescape(m.group(1))
            url_abs = urllib.parse.urljoin(url_base, url)
            if url_abs.startswith("http"):
                return url_abs

    # 5) JSON-LD
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text, re.IGNORECASE | re.DOTALL
    ):
        try:
            data = json.loads(m.group(1).strip())
            # Puede ser dict o lista
            candidatos = data if isinstance(data, list) else [data]
            for cand in candidatos:
                if not isinstance(cand, dict):
                    continue
                img = cand.get("image")
                if isinstance(img, str) and img.startswith("http"):
                    return img
                if isinstance(img, list) and img:
                    primero = img[0]
                    if isinstance(primero, str) and primero.startswith("http"):
                        return primero
                    if isinstance(primero, dict) and primero.get("url", "").startswith("http"):
                        return primero["url"]
                if isinstance(img, dict) and img.get("url", "").startswith("http"):
                    return img["url"]
        except Exception:
            continue

    # 6) Primer <img> con extensión de imagen razonable
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html_text, re.IGNORECASE):
        src = html.unescape(m.group(1))
        if any(src.lower().split("?")[0].endswith(ext)
               for ext in (".jpg", ".jpeg", ".png", ".webp")):
            url_abs = urllib.parse.urljoin(url_base, src)
            if url_abs.startswith("http") and "logo" not in url_abs.lower():
                return url_abs

    return None


def extraer_precio_de_html(html_text):
    """
    Heurísticas para extraer un precio aproximado en USD del HTML.
    Devuelve float o None.
    """
    if not html_text:
        return None

    candidatos = []

    # 1) JSON-LD con "price" o "priceCurrency": "USD"
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text, re.IGNORECASE | re.DOTALL
    ):
        try:
            data = json.loads(m.group(1).strip())
            stack = [data] if not isinstance(data, list) else list(data)
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    offer = cur.get("offers")
                    if isinstance(offer, dict):
                        stack.append(offer)
                    elif isinstance(offer, list):
                        stack.extend(offer)
                    p = cur.get("price")
                    if p:
                        try:
                            candidatos.append(float(str(p).replace(",", "")))
                        except Exception:
                            pass
                    for v in cur.values():
                        if isinstance(v, (dict, list)):
                            stack.append(v)
                elif isinstance(cur, list):
                    stack.extend(cur)
        except Exception:
            continue

    # 2) Meta product:price:amount
    for pat in [
        r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+itemprop=["\']price["\'][^>]+content=["\']([^"\']+)["\']',
    ]:
        m = re.search(pat, html_text, re.IGNORECASE)
        if m:
            try:
                candidatos.append(float(m.group(1).replace(",", "").replace("$", "").strip()))
            except Exception:
                pass

    # 3) Patrones $XX.XX o USD XX.XX en el texto
    for m in re.finditer(r'(?:USD|US\$|\$)\s*([0-9]{1,5}(?:[.,][0-9]{2})?)', html_text):
        try:
            candidatos.append(float(m.group(1).replace(",", ".")))
        except Exception:
            pass

    if not candidatos:
        return None
    # Filtrar valores absurdos (productos < $1 o > $50000)
    candidatos = [c for c in candidatos if 1.0 <= c <= 50000.0]
    if not candidatos:
        return None
    # Tomar la mediana para eliminar outliers
    candidatos.sort()
    return candidatos[len(candidatos) // 2]


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 1 – BASE DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_data_table_1():
    import mysql.connector
    log("Conectando a MySQL…")
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT
            codigo_necesidad,
            entidad_contratante,
            entidad_contratante_url,
            `direccion_entrega`,
            contacto
        FROM infimas
        WHERE LOWER(etapa) = 'en generacion'
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    log(f"Registros encontrados en BD: {len(rows)}", "OK")
    for r in rows:
        log(f"  → {r['codigo_necesidad']} | {r['entidad_contratante']}")
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 2 – GOOGLE CLOUD STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_cliente_gcs():
    from google.oauth2 import service_account
    from google.cloud import storage
    creds_path = resolver_credenciales_a_archivo()
    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return storage.Client(credentials=creds, project=creds.project_id)


def listar_docs_necesidad(gcs_client, codigo_necesidad):
    bucket  = gcs_client.bucket(BUCKET_NAME)
    prefijo = f"{BUCKET_FOLDER}/{codigo_necesidad}/"
    blobs   = list(gcs_client.list_blobs(bucket, prefix=prefijo))
    docs    = [b for b in blobs if b.name.lower().endswith((".doc", ".docx", ".pdf"))]
    log(f"  Docs encontrados para {codigo_necesidad}: {len(docs)}")
    return docs


def descargar_blob_a_tmp(blob):
    suffix = Path(blob.name).suffix
    tmp    = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    blob.download_to_filename(tmp.name)
    return tmp.name


def subir_archivo_a_bucket(gcs_client, local_path, carpeta_destino):
    """
    Sube un archivo al bucket dentro de la carpeta `carpeta_destino`
    (nombre exacto, ej. "Fichas Técnicas" o "Proformas").
    """
    bucket    = gcs_client.bucket(BUCKET_NAME)
    nombre    = Path(local_path).name
    blob_name = f"{carpeta_destino}/{nombre}"
    blob      = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    log(f"  Subido: {blob_name}", "OK")
    return blob_name


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 3 – VERTEX AI / GEMINI
# ═══════════════════════════════════════════════════════════════════════════════

def inicializar_vertex_ai():
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from google.oauth2 import service_account

    creds_path = resolver_credenciales_a_archivo()
    with open(creds_path, "r", encoding="utf-8") as f:
        creds_data = json.load(f)

    creds = service_account.Credentials.from_service_account_file(creds_path)
    vertexai.init(
        project=creds_data["project_id"],
        credentials=creds,
        location="us-central1",
    )
    modelo = GenerativeModel(AI_MODEL)
    log(f"VertexAI inicializado con modelo: {AI_MODEL}", "OK")
    return modelo


def docx_a_pdf(docx_path):
    """
    Convierte .doc/.docx a PDF con LibreOffice headless.
    Devuelve path del PDF temporal o None.
    Verifica tamaño máximo 18 MB para no exceder límite de Gemini (~20 MB).
    """
    import subprocess
    SOFFICE_PATH = "soffice"
    out_dir = tempfile.mkdtemp()
    try:
        resultado = subprocess.run(
            [SOFFICE_PATH, "--headless", "--convert-to", "pdf",
             "--outdir", out_dir, docx_path],
            capture_output=True, text=True, timeout=120
        )
        if resultado.returncode != 0:
            log(f"    LibreOffice error: {resultado.stderr[:200]}", "WARN")
            return None

        nombre_pdf = Path(docx_path).stem + ".pdf"
        pdf_path = Path(out_dir) / nombre_pdf
        if not pdf_path.exists():
            log(f"    PDF no generado en: {out_dir}", "WARN")
            return None

        # Validar tamaño
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if size_mb > 18:
            log(f"    PDF demasiado grande ({size_mb:.1f} MB), se omitirá.", "WARN")
            shutil.rmtree(out_dir, ignore_errors=True)
            return None

        # Mover a tmp propio para poder borrar out_dir
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        shutil.copy2(str(pdf_path), tmp.name)
        shutil.rmtree(out_dir, ignore_errors=True)
        return tmp.name
    except FileNotFoundError:
        log("    LibreOffice ('soffice') no encontrado en el PATH.", "ERR")
        return None
    except subprocess.TimeoutExpired:
        log("    Conversión a PDF superó el tiempo límite (120s).", "WARN")
        return None
    except Exception as e:
        log(f"    Error al convertir a PDF: {e}", "WARN")
        return None


def blob_a_part(blob_path_local):
    """
    Convierte archivo local a Part de Gemini.
    .doc/.docx se convierten a PDF (Gemini no acepta docx directamente).
    """
    from vertexai.generative_models import Part
    suffix = Path(blob_path_local).suffix.lower()

    if suffix in (".docx", ".doc"):
        log(f"    Convirtiendo {Path(blob_path_local).name} a PDF para Gemini…")
        pdf_path = docx_a_pdf(blob_path_local)
        if pdf_path is None:
            return None
        blob_path_local = pdf_path
        suffix = ".pdf"

    if suffix != ".pdf":
        log(f"    Formato no soportado por Gemini: {suffix}. Se omite.", "WARN")
        return None

    # Verificar tamaño antes de cargar
    size_mb = Path(blob_path_local).stat().st_size / (1024 * 1024)
    if size_mb > 18:
        log(f"    Archivo PDF demasiado grande ({size_mb:.1f} MB). Se omite.", "WARN")
        return None

    with open(blob_path_local, "rb") as f:
        data = f.read()
    return Part.from_data(data=data, mime_type="application/pdf")


def llamar_gemini_con_reintentos(modelo, contents, max_intentos=3, espera_inicial=8):
    """
    Llama a generate_content con reintentos exponenciales para errores transitorios.
    """
    ultimo_error = None
    for intento in range(1, max_intentos + 1):
        try:
            return modelo.generate_content(contents)
        except Exception as e:
            ultimo_error = e
            msg = str(e)
            transient = any(t in msg.lower() for t in
                            ["503", "500", "429", "deadline", "unavailable",
                             "rate", "resource exhausted"])
            if intento < max_intentos and transient:
                espera = espera_inicial * (2 ** (intento - 1))
                log(f"  Gemini error transitorio (intento {intento}/{max_intentos}). "
                    f"Reintentando en {espera}s. Detalle: {msg[:120]}", "WARN")
                time.sleep(espera)
                continue
            raise
    raise ultimo_error


def _parsear_json_de_respuesta(raw):
    """Limpia bloques markdown ``` y devuelve dict/list parseado, o None."""
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Intento de recuperación: buscar el primer { ... } o [ ... ] balanceado
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
                            return json.loads(raw[i:j+1])
                        except json.JSONDecodeError:
                            break
        return None


def analizar_documentos_con_gemini(modelo, archivos_locales, codigo_necesidad):
    """
    Pide a Gemini que analice los documentos y devuelva JSON con la info
    del/los artículo(s) de compra.
    """
    partes = []
    for path in archivos_locales:
        try:
            part = blob_a_part(path)
            if part is None:
                log(f"    Documento omitido (no convertible): {Path(path).name}", "WARN")
                continue
            partes.append(part)
            log(f"    Documento cargado: {Path(path).name}")
        except Exception as e:
            log(f"    No se pudo cargar {path}: {e}", "WARN")

    if not partes:
        log("No hay documentos válidos para analizar.", "ERR")
        return None

    prompt = f"""
Eres un analista de contratación pública especializado en fichas técnicas.
Analiza TODOS los documentos adjuntos que corresponden al código de necesidad: {codigo_necesidad}.

Tu tarea es extraer la información del ARTÍCULO DE COMPRA solicitado y devolver ÚNICAMENTE
un objeto JSON válido (sin bloques de código markdown, sin texto adicional) con la siguiente estructura:

{{
  "nombre_articulo": "Nombre completo del artículo",
  "marca": "Marca exacta",
  "modelo": "Modelo exacto",
  "cantidad": 1,
  "caracteristicas": [
    "Característica 1",
    "... (al menos 7)"
  ],
  "especificaciones_tecnicas": [
    "Especificación técnica 1: valor",
    "... (al menos 10)"
  ],
  "especificaciones_electricas": [
    "Especificación eléctrica 1: valor",
    "... (lista vacía [] si no aplica)"
  ],
  "incluye": [
    "Accesorio o ítem incluido 1"
  ],
  "resumen": "Descripción del producto de 50 a 80 palabras."
}}

IMPORTANTE:
- El campo "cantidad" debe ser el número entero de unidades solicitadas en los documentos.
- El nombre, marca y modelo deben ser EXACTAMENTE los que se solicitan en los documentos.
- Si el documento menciona un modelo conocido de una marca específica (ej: "S3 Heavy Duty" es Bosch,
  "Wireless Micro" es RODE), INFIERE la marca aunque no esté escrita explícitamente.
- Si los documentos NO especifican marca ni modelo concretos (sólo describen el artículo
  de manera genérica o por sus características funcionales — por ejemplo "disco duro
  externo de 2TB con USB 3.0"), deja "marca": "" y "modelo": "" (cadenas vacías).
  NO inventes una marca o modelo en este caso. En esa situación, asegúrate de que
  "caracteristicas" y "especificaciones_tecnicas" sean lo más completas y descriptivas
  posibles, ya que serán la base para que después se proponga un producto adecuado
  desde la lista de proveedores autorizados.
- Si hay varios artículos DIFERENTES, incluye un array 'articulos': [...] con la misma estructura
  (incluyendo "cantidad" por cada artículo). Si es un solo artículo, devuelve el objeto directo.
"""

    log(f"  Enviando {len(partes)} doc(s) a Gemini para análisis…")
    response = llamar_gemini_con_reintentos(modelo, [*partes, prompt])
    data = _parsear_json_de_respuesta(response.text)
    if data is None:
        log(f"  Error al parsear JSON de Gemini.", "ERR")
        log(f"  Respuesta raw: {response.text[:500]}", "WARN")
        return None

    log("  Análisis Gemini completado.", "OK")
    return data


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 4 – BÚSQUEDA DE PRODUCTOS EN PROVEEDORES
#  CORRECCIÓN BUG 2: ahora se buscan URLs REALES en internet (no las inventa
#  Gemini). Después se le pide a Gemini que escoja la mejor opción entre las
#  URLs reales encontradas.
# ═══════════════════════════════════════════════════════════════════════════════

def buscar_producto_en_proveedores(modelo, info_articulo):
    """
    Estrategia híbrida con dos modos según los documentos de contratación:

    MODO EXACTO (los documentos especifican marca y modelo):
      1) Búsqueda real con DuckDuckGo HTML restringida a los dominios autorizados,
         usando "<nombre> <marca> <modelo> site:dominio".
      2) Validación de cada URL: HTTP 200 + el HTML menciona la marca o el modelo.
      3) Para cada URL válida, extraer precio e imagen del HTML real.
      4) Pedir a Gemini que SELECCIONE la mejor opción entre las URLs validadas.

    MODO PROPUESTA (los documentos NO especifican marca/modelo):
      1) Búsqueda en los dominios autorizados usando nombre + características distintivas.
      2) Validación más laxa: la página debe mencionar al menos un término del nombre
         o de las características.
      3) Enriquecimiento adicional con el título del producto en cada página.
      4) Pedir a Gemini que PROPONGA, a partir de los candidatos reales:
         - Un artículo idóneo que cumpla los requisitos al menor precio (con su marca/modelo).
         - 3 alternativas que también cumplen los requisitos pero son menos recomendadas.

    En MODO PROPUESTA, el resultado incluye `info_articulo_actualizada` con la marca
    y modelo del producto propuesto, para que la ficha técnica y la proforma se
    generen a partir de ese artículo.
    """
    nombre      = info_articulo.get("nombre_articulo", "") or ""
    marca       = info_articulo.get("marca", "") or ""
    modelo_prod = info_articulo.get("modelo", "") or ""

    es_propuesta = not _hay_marca_modelo_especificos(info_articulo)

    # ── 1. Búsqueda real ─────────────────────────────────────────────────────
    if es_propuesta:
        query_base = _construir_query_caracteristicas(info_articulo)
        log("  Modo PROPUESTA: los documentos no especifican marca/modelo concretos.")
        log(f"  Buscando '{query_base}' en proveedores (a partir de características)…")
        candidatos_brutos = buscar_urls_producto_en_proveedores(
            nombre, marca, modelo_prod, query_base=query_base
        )
    else:
        log(f"  Modo EXACTO. Buscando '{nombre} {marca} {modelo_prod}' en proveedores…")
        candidatos_brutos = buscar_urls_producto_en_proveedores(nombre, marca, modelo_prod)

    if not candidatos_brutos:
        log("  No se encontraron URLs en los proveedores autorizados.", "WARN")
        return {"mejor_opcion": {}, "alternativas": [], "url_imagen_producto": "",
                "info_articulo_actualizada": None}

    # ── 2. Validar y enriquecer cada URL ─────────────────────────────────────
    if es_propuesta:
        # Validación laxa: que la página mencione al menos un término del nombre
        terminos_match = [w for w in re.split(r"\s+", nombre.lower()) if len(w) >= 3]
        if not terminos_match:
            terminos_match = None
    else:
        terminos_match = [t for t in (marca, modelo_prod)
                          if t and t.lower() != "no especificada"]
        if not terminos_match:
            terminos_match = [nombre.split()[0]] if nombre else None

    enriquecidos = []
    for cand in candidatos_brutos[:25]:  # tope para no demorar demasiado
        url = cand["url"]
        html_text = fetch_html(url)
        if not html_text:
            continue

        cuerpo_lower = html_text.lower()
        if terminos_match:
            coincide = any(t.lower() in cuerpo_lower for t in terminos_match)
            if not coincide:
                log(f"    URL descartada (sin coincidencias): {url[:80]}", "WARN")
                continue

        precio = extraer_precio_de_html(html_text)
        img    = extraer_imagen_de_html(html_text, url)
        if img and not validar_url_imagen(img, timeout=8):
            img = None

        # En modo propuesta enriquecemos también con título para que Gemini decida bien
        titulo = extraer_titulo_de_html(html_text) if es_propuesta else None

        enriquecidos.append({
            "url": url,
            "es_extranjero": cand["es_extranjero"],
            "dominio": cand["dominio"],
            "precio_unitario_usd": precio,
            "imagen_extraida": img,
            "titulo": titulo,
        })
        msg = f"    OK: {cand['dominio']} → precio≈{precio} | img={'sí' if img else 'no'}"
        if titulo:
            msg += f" | titulo='{titulo[:60]}'"
        log(msg)

        time.sleep(0.3)

    if not enriquecidos:
        log("  Ninguna URL pasó la validación de contenido.", "WARN")
        return {"mejor_opcion": {}, "alternativas": [], "url_imagen_producto": "",
                "info_articulo_actualizada": None}

    # ── 3. Pedir a Gemini que ELIJA (modo exacto) o PROPONGA (modo propuesta) ─
    if es_propuesta:
        # Listado con título para que Gemini pueda evaluar idoneidad
        listado_str = "\n".join(
            f"- [{i}] proveedor={c['dominio']}  extranjero={c['es_extranjero']}  "
            f"precio_aprox=${c['precio_unitario_usd']}  "
            f"titulo='{(c.get('titulo') or '')[:120]}'  url={c['url']}"
            for i, c in enumerate(enriquecidos)
        )
        caract_str = "\n".join(f"  - {c}" for c in (info_articulo.get("caracteristicas") or [])[:10])
        specs_str  = "\n".join(f"  - {s}" for s in (info_articulo.get("especificaciones_tecnicas") or [])[:10])

        prompt_decision = f"""
Los documentos de contratación NO especifican marca ni modelo concretos para el artículo.
Tu tarea es PROPONER un artículo adecuado entre los candidatos REALES de los proveedores
autorizados que se listan más abajo, basándote en las características y especificaciones
descritas en los documentos.

ARTÍCULO REQUERIDO (de los documentos de contratación):
- Nombre genérico: {nombre}
- Características requeridas:
{caract_str or '  (no detalladas)'}
- Especificaciones técnicas requeridas:
{specs_str or '  (no detalladas)'}

CANDIDATOS REALES (URLs ya verificadas en proveedores autorizados):
{listado_str}

Reglas:
1. Selecciona como artículo IDÓNEO el candidato que MEJOR cumpla las características
   y especificaciones requeridas con el MENOR precio final. Para extranjero=true, suma
   ~25% al precio_aprox por envío y arancel; para extranjero=false, precio_final = precio_aprox.
2. Identifica también 3 ALTERNATIVAS que también cumplen los requisitos pero son menos
   recomendadas (peor relación calidad/precio o cumplen los requisitos de forma menos completa).
3. Para el idóneo extrae la marca y modelo reales del producto a partir del título dado.

Devuelve ÚNICAMENTE este JSON (sin markdown):
{{
  "mejor_indice": 0,
  "marca_propuesta": "Marca real del artículo idóneo",
  "modelo_propuesto": "Modelo real del artículo idóneo",
  "nombre_propuesto": "Nombre completo del artículo idóneo",
  "precio_total_usd": 0.00,
  "costos_adicionales_usd": 0.00,
  "detalle_costos": "envío + arancel" | "",
  "alternativas_ordenadas": [1, 2, 3]
}}
"""
        prompt_seleccion = prompt_decision
    else:
        listado_str = "\n".join(
            f"- [{i}] proveedor={c['dominio']}  extranjero={c['es_extranjero']}  "
            f"precio_aprox=${c['precio_unitario_usd']}  url={c['url']}"
            for i, c in enumerate(enriquecidos)
        )
        prompt_seleccion = f"""
Te entrego una lista de candidatos REALES (URLs ya verificadas) para el producto:
PRODUCTO: {nombre}  MARCA: {marca}  MODELO: {modelo_prod}

CANDIDATOS:
{listado_str}

Tu tarea es elegir LA MEJOR OPCIÓN. Reglas:
1. El producto debe ser EXACTAMENTE el solicitado (mismo modelo/marca).
2. Para extranjero=true, suma envío + arancel aduanero (~25% del precio) al precio final.
3. Para extranjero=false, el precio_final = precio_aprox.
4. Gana el menor precio_final.

Devuelve ÚNICAMENTE este JSON (sin markdown):
{{
  "mejor_indice": 0,
  "precio_total_usd": 0.00,
  "costos_adicionales_usd": 0.00,
  "detalle_costos": "envío + arancel" | "",
  "alternativas_ordenadas": [1, 2, 3]
}}

donde "mejor_indice" y "alternativas_ordenadas" son índices del listado anterior
(las alternativas son las siguientes mejores opciones en orden ascendente de precio_final).
"""

    decision = None
    try:
        resp = llamar_gemini_con_reintentos(modelo, prompt_seleccion)
        decision = _parsear_json_de_respuesta(resp.text)
    except Exception as e:
        log(f"  Gemini no pudo decidir ({e}). Usando heurística por precio.", "WARN")

    # Heurística de respaldo si Gemini falla: ordenar por precio
    if not decision or not isinstance(decision, dict):
        con_precio = [c for c in enriquecidos if c["precio_unitario_usd"]]
        sin_precio = [c for c in enriquecidos if not c["precio_unitario_usd"]]
        con_precio.sort(key=lambda c: (
            c["precio_unitario_usd"] * (1.25 if c["es_extranjero"] else 1.0)
        ))
        ordenados = con_precio + sin_precio
        if not ordenados:
            return {"mejor_opcion": {}, "alternativas": [], "url_imagen_producto": "",
                    "info_articulo_actualizada": None}
        mejor = ordenados[0]
        alts  = ordenados[1:4]
        precio_final = (mejor["precio_unitario_usd"] or 0) * (1.25 if mejor["es_extranjero"] else 1.0)
        costos_adic  = precio_final - (mejor["precio_unitario_usd"] or 0)
        decision = {
            "mejor_indice": enriquecidos.index(mejor),
            "precio_total_usd": round(precio_final, 2),
            "costos_adicionales_usd": round(costos_adic, 2),
            "detalle_costos": "envío + arancel (25%)" if mejor["es_extranjero"] else "",
            "alternativas_ordenadas": [enriquecidos.index(a) for a in alts],
        }

    idx_mejor = decision.get("mejor_indice", 0)
    if not (0 <= idx_mejor < len(enriquecidos)):
        idx_mejor = 0
    mejor = enriquecidos[idx_mejor]

    # En modo propuesta, la marca/modelo finales son los que devolvió Gemini
    if es_propuesta:
        marca_final  = (decision.get("marca_propuesta")  or "").strip() or marca
        modelo_final = (decision.get("modelo_propuesto") or "").strip() or modelo_prod
        nombre_final = (decision.get("nombre_propuesto") or "").strip() or nombre
        info_articulo_actualizada = {
            "marca":           marca_final,
            "modelo":          modelo_final,
            "nombre_articulo": nombre_final,
        }
        log(f"  Artículo propuesto por la IA: {nombre_final} | "
            f"Marca: {marca_final} | Modelo: {modelo_final}", "OK")
    else:
        marca_final  = marca
        modelo_final = modelo_prod
        nombre_final = nombre
        info_articulo_actualizada = None

    # Construir mejor_opcion en el formato esperado por el resto del script
    mejor_opcion = {
        "proveedor": mejor["dominio"],
        "url_producto": mejor["url"],
        "precio_unitario_usd": mejor["precio_unitario_usd"] or 0,
        "precio_total_usd": decision.get("precio_total_usd",
                                         mejor["precio_unitario_usd"] or 0),
        "es_extranjero": mejor["es_extranjero"],
        "costos_adicionales_usd": decision.get("costos_adicionales_usd", 0),
        "detalle_costos": decision.get("detalle_costos", ""),
        "nombre_en_tienda": f"{nombre_final} {marca_final} {modelo_final}".strip(),
        "disponible": True,
        "url_verificada": True,
    }

    # Alternativas (en modo propuesta son las "menos recomendadas pero válidas")
    indices_alt = decision.get("alternativas_ordenadas", []) or []
    alternativas = []
    for idx in indices_alt[:3]:
        if 0 <= idx < len(enriquecidos) and idx != idx_mejor:
            alt = enriquecidos[idx]
            alternativas.append({
                "proveedor": alt["dominio"],
                "url_producto": alt["url"],
                "precio_total_usd": (alt["precio_unitario_usd"] or 0) *
                                    (1.25 if alt["es_extranjero"] else 1.0),
                "nombre_en_tienda": f"{nombre_final} {marca_final} {modelo_final}".strip(),
                "url_verificada": True,
            })

    # ── 4. Imagen del producto ───────────────────────────────────────────────
    url_imagen = mejor.get("imagen_extraida") or ""

    # Si la mejor opción no tiene imagen, probar las alternativas
    if not url_imagen:
        for c in enriquecidos:
            if c.get("imagen_extraida"):
                url_imagen = c["imagen_extraida"]
                log(f"  Imagen tomada de un proveedor alternativo: {c['dominio']}", "OK")
                break

    # Si aún no hay imagen, búsqueda directa con DuckDuckGo Images / Bing
    if not url_imagen:
        log("  Buscando imagen del producto en motores de imágenes…")
        query_img = " ".join(x for x in (nombre_final, marca_final, modelo_final) if x).strip()
        for fuente, fn in [("DuckDuckGo Images", _ddg_image_search),
                           ("Bing Images",       _bing_image_search)]:
            urls_img = fn(query_img, max_results=8)
            for u in urls_img:
                if validar_url_imagen(u, timeout=8):
                    url_imagen = u
                    log(f"  Imagen obtenida de {fuente}: {u[:80]}…", "OK")
                    break
            if url_imagen:
                break

    if not url_imagen:
        log("  No se encontró imagen del producto por ningún método.", "WARN")

    log(f"  Mejor opción: {mejor_opcion['proveedor']} → "
        f"${mejor_opcion['precio_total_usd']}", "OK")

    return {
        "mejor_opcion": mejor_opcion,
        "alternativas": alternativas,
        "url_imagen_producto": url_imagen,
        "info_articulo_actualizada": info_articulo_actualizada,
    }


def descargar_imagen_producto(url_imagen):
    """Descarga una URL de imagen a un archivo temporal local."""
    import requests
    if not url_imagen:
        return None
    try:
        r = requests.get(url_imagen, headers=DEFAULT_HEADERS, timeout=20,
                         allow_redirects=True)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "image/jpeg").lower()
        if not content_type.startswith("image/"):
            log(f"  La URL no devolvió una imagen (content-type={content_type}).", "WARN")
            return None
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        elif "gif" in content_type:
            ext = ".gif"
        else:
            ext = ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(r.content)
        tmp.close()
        # Convertir webp a png si es necesario (python-docx no soporta webp)
        if ext == ".webp":
            try:
                from PIL import Image as PILImage
                im = PILImage.open(tmp.name).convert("RGB")
                tmp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                tmp_png.close()
                im.save(tmp_png.name, "PNG")
                os.unlink(tmp.name)
                tmp_path = tmp_png.name
            except Exception as e:
                log(f"  No se pudo convertir webp a png: {e}. Se descarta la imagen.", "WARN")
                os.unlink(tmp.name)
                return None
        else:
            tmp_path = tmp.name
        log(f"  Imagen descargada: {len(r.content)//1024} KB", "OK")
        return tmp_path
    except Exception as e:
        log(f"  No se pudo descargar imagen: {e}", "WARN")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 5 – GENERACIÓN DE FICHA TÉCNICA (.docx)
# ═══════════════════════════════════════════════════════════════════════════════

def generar_ficha_tecnica(info_articulo, resultado_busqueda, codigo_necesidad, directorio_salida):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    nombre    = info_articulo.get("nombre_articulo", "Artículo")
    marca     = info_articulo.get("marca", "")
    mod_prod  = info_articulo.get("modelo", "")
    caract    = info_articulo.get("caracteristicas", [])
    specs_tec = info_articulo.get("especificaciones_tecnicas", [])
    specs_ele = info_articulo.get("especificaciones_electricas", [])
    incluye   = info_articulo.get("incluye", [])
    resumen   = info_articulo.get("resumen", "")

    url_imagen = resultado_busqueda.get("url_imagen_producto", "")
    path_img   = descargar_imagen_producto(url_imagen)

    nombre_archivo = re.sub(r'[^a-zA-Z0-9_\-]', '_', f"{codigo_necesidad}_ficha_tecnica")
    out_path       = Path(directorio_salida) / f"{nombre_archivo}.docx"

    doc    = Document(str(TEMPLATE_DOCX))
    cuerpo = doc.element.body

    # Limpiar el cuerpo conservando sectPr (encabezado/pie viven en otra parte y se preservan)
    for child in list(cuerpo):
        if not child.tag.endswith("}sectPr"):
            cuerpo.remove(child)

    def agregar_parrafo(text, bold=False, size_pt=11, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
                        espacio_antes=0, espacio_despues=0, color=None):
        p = doc.add_paragraph()
        p.alignment = align
        pPr = p._p.get_or_add_pPr()
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:before"), str(int(espacio_antes * 20)))
        spacing.set(qn("w:after"),  str(int(espacio_despues * 20)))
        pPr.append(spacing)
        run = p.add_run(text)
        run.bold = bold
        run.font.name = "Century Gothic"
        run.font.size = Pt(size_pt)
        if color:
            run.font.color.rgb = RGBColor(*color)
        rPr = run._r.get_or_add_rPr()
        rFonts = OxmlElement("w:rFonts")
        rFonts.set(qn("w:ascii"), "Century Gothic")
        rFonts.set(qn("w:hAnsi"), "Century Gothic")
        rPr.insert(0, rFonts)
        return p

    def agregar_item_lista(texto, size_pt=10):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pPr = p._p.get_or_add_pPr()
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"),    "360")
        ind.set(qn("w:hanging"), "360")
        pPr.append(ind)
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:before"), "0")
        spacing.set(qn("w:after"),  "60")
        pPr.append(spacing)
        run_bul = p.add_run("•  ")
        run_bul.font.name = "Century Gothic"
        run_bul.font.size = Pt(size_pt)
        run_txt = p.add_run(texto)
        run_txt.font.name = "Century Gothic"
        run_txt.font.size = Pt(size_pt)
        return p

    titulo_completo = f"{nombre} {marca} {mod_prod}".strip()
    agregar_parrafo(titulo_completo, bold=True, size_pt=12,
                    align=WD_ALIGN_PARAGRAPH.CENTER, espacio_despues=6)

    if path_img and Path(path_img).exists():
        try:
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_img = p_img.add_run()
            run_img.add_picture(path_img, width=Inches(4.5))
            log("  Imagen insertada en ficha técnica.", "OK")
        except Exception as e:
            log(f"  No se pudo insertar imagen: {e}", "WARN")
            agregar_parrafo("[Imagen del producto]",
                            align=WD_ALIGN_PARAGRAPH.CENTER, size_pt=9)
    else:
        agregar_parrafo("[Imagen del producto no disponible]",
                        align=WD_ALIGN_PARAGRAPH.CENTER, size_pt=9, color=(128, 128, 128))

    agregar_parrafo("", size_pt=6)

    if resumen:
        agregar_parrafo(resumen, size_pt=10, espacio_despues=8)
        agregar_parrafo("", size_pt=6)

    if caract:
        agregar_parrafo("Características:", bold=True, size_pt=11,
                        espacio_antes=4, espacio_despues=4)
        for c in caract:
            agregar_item_lista(c, size_pt=10)
        agregar_parrafo("", size_pt=6)

    if specs_tec:
        agregar_parrafo("Especificaciones técnicas:", bold=True, size_pt=11,
                        espacio_antes=4, espacio_despues=4)
        for s in specs_tec:
            agregar_item_lista(s, size_pt=10)
        agregar_parrafo("", size_pt=6)

    if specs_ele:
        agregar_parrafo("Especificaciones eléctricas:", bold=True, size_pt=11,
                        espacio_antes=4, espacio_despues=4)
        for s in specs_ele:
            agregar_item_lista(s, size_pt=10)
        agregar_parrafo("", size_pt=6)

    if incluye:
        agregar_parrafo("Incluye:", bold=True, size_pt=11,
                        espacio_antes=4, espacio_despues=4)
        for item in incluye:
            agregar_item_lista(item, size_pt=10)

    doc.save(str(out_path))
    log(f"  Ficha técnica guardada: {out_path.name}", "OK")
    return str(out_path), path_img


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 7 – GENERACIÓN DE PROFORMA (.xlsm)
# ═══════════════════════════════════════════════════════════════════════════════

def generar_proforma(registro_bd, info_articulo, resultado_busqueda,
                     directorio_salida, img_path=None):
    """
    Copia la plantilla xlsm y completa las celdas indicadas según el
    funcionamiento. Plantilla real (verificada):

      Hoja "Cotización ":
        B8  → CLIENTE (entidad contratante, en mayúsculas)
        B9  → caracteres 5..17 del código (RUC del contratante)
        B10 → DIRECCIÓN
        B11 → ATENCIÓN (contacto)
        D12 → CÓDIGO NECESIDAD (A12:C12 fusionada con la etiqueta)
        I8  → FECHA dd/mm/yyyy
        C16,C17,... → nombre+marca+modelo del/los producto(s)
        G16,G17,... → cantidad

      Hoja "Costos":
        C7  → URL del proceso de contratación (entidad_contratante_url)
        K14 → URL del producto recomendado (mejor opción)  ← CORRECCIÓN BUG 3
        J16, J17, J18 → URLs alternativas en orden de cercanía
    """
    import openpyxl
    from openpyxl.drawing.image import Image as XlImage
    from openpyxl.utils import get_column_letter

    codigo      = registro_bd["codigo_necesidad"]
    entidad     = str(registro_bd.get("entidad_contratante", "") or "").upper()
    entidad_url = str(registro_bd.get("entidad_contratante_url", "") or "")
    direccion   = str(registro_bd.get("direccion_entrega", "") or "")
    contacto    = str(registro_bd.get("contacto", "") or "")

    ruc_ish = codigo[4:17] if len(codigo) >= 17 else codigo

    # Determinar lista de artículos
    if isinstance(info_articulo, list):
        articulos = info_articulo
    elif isinstance(info_articulo, dict) and "articulos" in info_articulo:
        articulos = info_articulo["articulos"]
        if articulos and isinstance(articulos[0], list):
            articulos = articulos[0]
    else:
        articulos = [info_articulo]

    mejor        = resultado_busqueda.get("mejor_opcion", {}) or {}
    alternativas = resultado_busqueda.get("alternativas", []) or []
    url_mejor    = mejor.get("url_producto", "") or ""
    urls_alt     = [a.get("url_producto", "") for a in alternativas[:3] if a.get("url_producto")]

    fecha_hoy   = datetime.date.today().strftime("%d/%m/%Y")
    nombre_arch = re.sub(r'[^a-zA-Z0-9_\-]', '_', codigo)
    out_path    = Path(directorio_salida) / f"{nombre_arch}.xlsm"

    shutil.copy2(str(TEMPLATE_XLSX), str(out_path))
    wb = openpyxl.load_workbook(str(out_path), keep_vba=True)

    # ── Hoja "Cotización" ──────────────────────────────────────────────────────
    hoja_cot = None
    for sn in wb.sheetnames:
        if "cotizaci" in sn.lower():
            hoja_cot = wb[sn]
            break
    if hoja_cot is None:
        hoja_cot = wb.worksheets[0]

    def escribir_celda(ws, ref, valor):
        """
        Escribe valor en la celda. Si está fusionada, escribe en la celda ancla
        (superior-izquierda) del rango fusionado.
        """
        for merged_range in ws.merged_cells.ranges:
            if ref in merged_range:
                anchor = f"{get_column_letter(merged_range.min_col)}{merged_range.min_row}"
                ws[anchor].value = valor
                return
        ws[ref].value = valor

    # Cabecera
    escribir_celda(hoja_cot, "B8",  entidad)
    escribir_celda(hoja_cot, "B9",  ruc_ish)
    escribir_celda(hoja_cot, "B10", direccion)
    escribir_celda(hoja_cot, "B11", contacto)
    escribir_celda(hoja_cot, "D12", codigo)
    escribir_celda(hoja_cot, "I8",  fecha_hoy)

    # Artículos: nombre+marca+modelo en columna C, cantidad en columna G
    FILA_INICIO_PRODUCTOS = 16
    for i, art in enumerate(articulos):
        fila        = FILA_INICIO_PRODUCTOS + i
        nombre_prod = art.get("nombre_articulo", "") or ""
        marca_prod  = art.get("marca", "") or ""
        mod_prod    = art.get("modelo", "") or ""
        cantidad    = art.get("cantidad", 1)

        texto_producto = f"{nombre_prod}\nMarca: {marca_prod} | Modelo: {mod_prod}"
        escribir_celda(hoja_cot, f"C{fila}", texto_producto)
        escribir_celda(hoja_cot, f"G{fila}", cantidad)

    # Imagen del producto
    if img_path and Path(img_path).exists():
        try:
            img_xl        = XlImage(img_path)
            img_xl.width  = 120
            img_xl.height = 90
            img_xl.anchor = f"G{FILA_INICIO_PRODUCTOS}"
            hoja_cot.add_image(img_xl)
            log("  Imagen insertada en Excel.", "OK")
        except Exception as e:
            log(f"  No se pudo insertar imagen en Excel: {e}", "WARN")

    # ── Hoja "Costos" ──────────────────────────────────────────────────────────
    hoja_cos = None
    for sn in wb.sheetnames:
        if "costo" in sn.lower():
            hoja_cos = wb[sn]
            break
    if hoja_cos is None and len(wb.worksheets) > 1:
        hoja_cos = wb.worksheets[1]

    if hoja_cos is not None:
        # URL del proceso de contratación
        escribir_celda(hoja_cos, "C7", entidad_url)

        # CORRECCIÓN BUG 3: URL del producto recomendado en K14 (no en C15)
        if url_mejor:
            escribir_celda(hoja_cos, "K14", url_mejor)

        # Datos del primer artículo en fila 15 (la plantilla tiene fórmulas H15=G15*F15, etc.)
        for i, art in enumerate(articulos):
            fila_cos     = 15 + i
            cantidad_cos = art.get("cantidad", 1)
            precio_real  = mejor.get("precio_unitario_usd", 0) if i == 0 else 0
            costo_final  = mejor.get("precio_total_usd", 0)    if i == 0 else 0
            nombre_corto = (art.get("nombre_articulo", "") or "")[:90]

            # Nombre del producto en la columna PRODUCTO de Costos
            if nombre_corto:
                escribir_celda(hoja_cos, f"C{fila_cos}", nombre_corto)
            if precio_real:
                escribir_celda(hoja_cos, f"E{fila_cos}", precio_real)
            if cantidad_cos:
                escribir_celda(hoja_cos, f"F{fila_cos}", cantidad_cos)
            if costo_final:
                escribir_celda(hoja_cos, f"G{fila_cos}", costo_final)

        # URLs alternativas: J16, J17, J18 (en orden decreciente de cercanía a la mejor)
        refs_alt = ["J16", "J17", "J18"]
        for i, url_a in enumerate(urls_alt[:3]):
            if url_a:
                escribir_celda(hoja_cos, refs_alt[i], url_a)

    wb.save(str(out_path))
    log(f"  Proforma guardada: {out_path.name}", "OK")
    return str(out_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 9 – VERIFICACIÓN Y ACTUALIZACIÓN DE BD
# ═══════════════════════════════════════════════════════════════════════════════

def verificar_blobs_en_bucket(gcs_client, blob_docx, blob_xlsx):
    bucket = gcs_client.bucket(BUCKET_NAME)

    def existe_y_valido(blob_name):
        blob = bucket.blob(blob_name)
        blob.reload()
        return blob.exists() and (blob.size or 0) > 0

    ok_docx = ok_xlsx = False
    try:
        ok_docx = existe_y_valido(blob_docx)
    except Exception as e:
        log(f"  No se pudo verificar ficha técnica en bucket: {e}", "WARN")
    try:
        ok_xlsx = existe_y_valido(blob_xlsx)
    except Exception as e:
        log(f"  No se pudo verificar proforma en bucket: {e}", "WARN")
    return ok_docx, ok_xlsx


def actualizar_etapa_bd(codigo_necesidad):
    import mysql.connector
    conn   = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    query  = """
        UPDATE infimas
        SET etapa = 'finalizada'
        WHERE codigo_necesidad = %s
          AND LOWER(etapa) = 'en generacion'
    """
    cursor.execute(query, (codigo_necesidad,))
    filas  = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    if filas:
        log(f"  BD actualizada: {codigo_necesidad} → 'finalizada'", "OK")
    else:
        log(f"  BD: no se actualizó ningún registro para {codigo_necesidad}.", "WARN")


# ═══════════════════════════════════════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "═"*60)
    print("  Preform_generator — Automatización de Documentos")
    print("═"*60 + "\n")

    paso(1, 9, "Obteniendo registros de la BD MySQL")
    data_table_1 = obtener_data_table_1()
    if not data_table_1:
        log("No hay registros 'en generacion'. Fin.", "WARN")
        return

    paso(2, 9, "Inicializando clientes GCS y VertexAI")
    gcs_client = obtener_cliente_gcs()
    modelo_ai  = inicializar_vertex_ai()

    dir_salida = Path(tempfile.mkdtemp(prefix="nexus_out_"))
    log(f"Directorio de trabajo temporal: {dir_salida}")

    errores = []

    for idx, registro in enumerate(data_table_1, 1):
        codigo = registro["codigo_necesidad"]
        print(f"\n{'━'*60}")
        print(f"  [{idx}/{len(data_table_1)}] Procesando: {codigo}")
        print(f"{'━'*60}")

        dir_necesidad = dir_salida / codigo
        dir_necesidad.mkdir(exist_ok=True)
        path_img = None
        archivos_locales = []

        try:
            paso(3, 9, f"Descargando y analizando documentos — {codigo}")
            blobs = listar_docs_necesidad(gcs_client, codigo)
            if not blobs:
                log(f"Sin documentos en bucket para {codigo}. Saltando.", "WARN")
                errores.append(f"{codigo}: sin documentos en bucket.")
                continue

            for blob in blobs:
                local_path = descargar_blob_a_tmp(blob)
                archivos_locales.append(local_path)
                log(f"  Descargado: {blob.name.split('/')[-1]}")

            info_articulo = analizar_documentos_con_gemini(
                modelo_ai, archivos_locales, codigo
            )
            if not info_articulo:
                log(f"Análisis fallido para {codigo}.", "ERR")
                errores.append(f"{codigo}: análisis Gemini fallido.")
                continue

            # Normalizar estructura
            if isinstance(info_articulo, list):
                articulos = info_articulo
                info_principal = articulos[0] if articulos else {}
            elif isinstance(info_articulo, dict) and "articulos" in info_articulo:
                articulos = info_articulo["articulos"]
                if articulos and isinstance(articulos[0], list):
                    articulos = articulos[0]
                info_principal = articulos[0] if articulos else {}
            elif isinstance(info_articulo, dict):
                articulos      = [info_articulo]
                info_principal = info_articulo
            else:
                info_principal = {}
                articulos      = []

            if not info_principal:
                log("  No se pudo extraer artículo del análisis.", "ERR")
                errores.append(f"{codigo}: formato de respuesta Gemini no reconocido.")
                continue

            log(f"  Artículo: {info_principal.get('nombre_articulo','')} "
                f"| Marca: {info_principal.get('marca','')} "
                f"| Modelo: {info_principal.get('modelo','')} "
                f"| Cantidad: {info_principal.get('cantidad','?')}", "OK")

            paso(4, 9, f"Buscando producto en proveedores — {codigo}")
            resultado_busqueda = buscar_producto_en_proveedores(modelo_ai, info_principal)

            # Si la IA propuso un artículo (modo PROPUESTA: los documentos no
            # especificaban marca/modelo concretos), actualizamos info_principal
            # y articulos[0] para que la ficha técnica y la proforma se generen
            # a partir del artículo propuesto.
            info_actualizada = resultado_busqueda.get("info_articulo_actualizada")
            if info_actualizada:
                log(f"  Actualizando datos del artículo con la propuesta de la IA: "
                    f"Marca={info_actualizada.get('marca')} | "
                    f"Modelo={info_actualizada.get('modelo')}", "OK")
                for k, v in info_actualizada.items():
                    if v:
                        info_principal[k] = v
                        if articulos:
                            articulos[0][k] = v

            paso(5, 9, f"Generando ficha técnica .docx — {codigo}")
            path_docx, path_img = generar_ficha_tecnica(
                info_principal, resultado_busqueda, codigo, str(dir_necesidad)
            )

            paso(6, 9, f"Subiendo ficha técnica al bucket — {codigo}")
            blob_docx = subir_archivo_a_bucket(gcs_client, path_docx, "Fichas Técnicas")

            log("  Esperando 60 segundos antes de generar la proforma…", "INFO")
            time.sleep(60)

            paso(7, 9, f"Generando proforma .xlsm — {codigo}")
            path_xlsx = generar_proforma(
                registro, articulos, resultado_busqueda,
                str(dir_necesidad), img_path=path_img
            )

            paso(8, 9, f"Subiendo proforma al bucket — {codigo}")
            blob_xlsx = subir_archivo_a_bucket(gcs_client, path_xlsx, "Proformas")

            paso(9, 9, f"Verificando archivos en bucket y actualizando BD — {codigo}")
            ok_docx, ok_xlsx = verificar_blobs_en_bucket(gcs_client, blob_docx, blob_xlsx)

            if ok_docx and ok_xlsx:
                log(f"  Ficha técnica en bucket: ✔", "OK")
                log(f"  Proforma en bucket:      ✔", "OK")
                actualizar_etapa_bd(codigo)
            else:
                msg_partes = []
                if not ok_docx:
                    msg_partes.append("ficha técnica no verificada")
                    log(f"  Ficha técnica en bucket: ✗", "ERR")
                if not ok_xlsx:
                    msg_partes.append("proforma no verificada")
                    log(f"  Proforma en bucket:      ✗", "ERR")
                motivo = "; ".join(msg_partes)
                log(f"  BD NO actualizada para {codigo}: {motivo}", "WARN")
                errores.append(f"{codigo}: {motivo}")

            log(f"✔ {codigo} procesado exitosamente.", "OK")

        except Exception as e:
            log(f"Error procesando {codigo}: {e}", "ERR")
            traceback.print_exc()
            errores.append(f"{codigo}: {e}")
        finally:
            # Limpieza de temporales por iteración (siempre, incluso si hubo error)
            for f in archivos_locales:
                try: os.unlink(f)
                except: pass
            if path_img:
                try: os.unlink(path_img)
                except: pass

    # ── Resumen final ──────────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  RESUMEN FINAL")
    print(f"{'═'*60}")
    exitosos = len(data_table_1) - len(errores)
    log(f"Procesados exitosamente: {exitosos}/{len(data_table_1)}", "OK")
    if errores:
        log("Errores encontrados:", "WARN")
        for e in errores:
            print(f"    ✗ {e}")

    try:
        shutil.rmtree(str(dir_salida))
    except Exception:
        pass

    print(f"\n{'═'*60}")
    print("  Preform_generator finalizado.")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()