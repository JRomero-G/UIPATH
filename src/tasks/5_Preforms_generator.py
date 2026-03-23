"""
NexusGenerator - Automatización de documentos de contratación.
Conecta a BD MySQL → analiza documentos en GCS con Gemini →
busca mejores precios en proveedores → genera fichas técnicas (.docx)
y proformas (.xlsx) → sube todo al bucket de GCS.
"""

import os, sys, json, shutil, tempfile, datetime, re, copy, io, time, hashlib, mimetypes, traceback
from pathlib import Path
# ✅ API nueva
from vertexai.generative_models import Tool, grounding as vertexai_grounding


#raíz del proyecto al path de Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from Config import Global

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

MYSQL_CONFIG = {
    "host": Global.DB_HOST,
    "user": Global.DB_USER,
    "password": Global.DB_PASSWORD,
    "database": Global.DATABASE,
}

#GEMINI_CREDENTIALS_PATH = "src/Credentials/Clave_bucket_AIgemini.json"
GEMINI_CREDENTIALS_PATH = Global.RENDER_CRENDENTIALS_JSON # Credenciales en las variables de entorno
BUCKET_NAME             = Global.BUCKET_NAME
BUCKET_FOLDER           = "Documentos de Contratación"
AI_MODEL                = "gemini-2.5-pro"   # mejor razonamiento multimodal

# Plantillas (misma carpeta que el script o path relativo)
SCRIPT_DIR     = Path(__file__).parent
TEMPLATE_DOCX  = SCRIPT_DIR / "FICHA TECNICA MICROFONO Y MEMORIA.docx"
TEMPLATE_XLSX  = SCRIPT_DIR / "FORMATO DE PROFORMA RECREADO VACÍO.xlsm"

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

def resolver_credenciales_a_archivo():
    """
    GEMINI_CREDENTIALS_PATH puede ser un path a archivo .json
    o directamente el contenido JSON como string (caso Render / .env).
    Si es JSON string, lo escribe en un archivo temporal y devuelve ese path.
    """
    raw = GEMINI_CREDENTIALS_PATH

    if raw is None:
        raise ValueError(
            "La variable RENDER_CRENDENTIALS_JSON no está definida. "
            "Verifica tu archivo .env en la raíz del proyecto."
        )

    stripped = raw.strip()

    if stripped.startswith("{"):
        # Es JSON directo como string → escribir a archivo temporal
        creds_dict = json.loads(stripped)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(creds_dict, tmp)
        tmp.close()
        log("Credenciales resueltas desde variable de entorno (JSON string).")
        return tmp.name
    else:
        # Es un path de archivo normal
        log(f"Credenciales resueltas desde archivo: {stripped}")
        return stripped

# ═══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES DE TERMINAL
# ═══════════════════════════════════════════════════════════════════════════════

def log(msg, nivel="INFO"):
    iconos = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "STEP": "🔷"}
    print(f"{iconos.get(nivel,'  ')} [{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def paso(n, total, desc):
    print(f"\n{'─'*60}\n  PASO {n}/{total}: {desc}\n{'─'*60}", flush=True)


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
    return rows   # lista de dicts


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
    """Devuelve lista de blobs (.doc, .docx, .pdf) para un código de necesidad."""
    bucket   = gcs_client.bucket(BUCKET_NAME)
    prefijo  = f"{BUCKET_FOLDER}/{codigo_necesidad}/"
    blobs    = list(gcs_client.list_blobs(bucket, prefix=prefijo))
    docs     = [b for b in blobs if b.name.lower().endswith((".doc", ".docx", ".pdf"))]
    log(f"  Docs encontrados para {codigo_necesidad}: {len(docs)}")
    return docs


def descargar_blob_a_tmp(blob):
    """Descarga blob a archivo temporal y devuelve su path."""
    suffix = Path(blob.name).suffix
    tmp    = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    blob.download_to_filename(tmp.name)
    return tmp.name


def subir_archivo_a_bucket(gcs_client, local_path, carpeta_destino):
    """Sube un archivo local al bucket en la carpeta indicada."""
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
        project  = creds_data["project_id"],
        credentials = creds,
        location = "us-central1",
    )
    modelo = GenerativeModel(AI_MODEL)
    log(f"VertexAI inicializado con modelo: {AI_MODEL}", "OK")
    return modelo


def blob_a_part(blob_path_local):
    """Convierte archivo local a Part de Gemini."""
    from vertexai.generative_models import Part
    suffix = Path(blob_path_local).suffix.lower()
    mapa   = {".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc":  "application/msword"}
    mime   = mapa.get(suffix, "application/octet-stream")
    with open(blob_path_local, "rb") as f:
        data = f.read()
    return Part.from_data(data=data, mime_type=mime)


def analizar_documentos_con_gemini(modelo, archivos_locales, codigo_necesidad):
    """
    Pide a Gemini que analice los documentos y devuelva JSON con:
    nombre, marca, modelo, características, especificaciones_tecnicas,
    especificaciones_electricas, incluye, resumen.
    """
    from vertexai.generative_models import Part

    partes = []
    for path in archivos_locales:
        try:
            partes.append(blob_a_part(path))
            log(f"    Documento cargado: {Path(path).name}")
        except Exception as e:
            log(f"    No se pudo cargar {path}: {e}", "WARN")

    if not partes:
        log("No hay documentos válidos para analizar.", "ERR")
        return None

    prompt = f"""
Eres un analista de contratación pública especializado en fichas técnicas.
Analiza TODOS los documentos adjuntos que corresponden al código de necesidad: {codigo_necesidad}.

Tu tarea es extraer la información del ARTÍCULO DE COMPRA solicitado y devolver ÚNICAMENTE un objeto JSON válido (sin bloques de código markdown, sin texto adicional) con la siguiente estructura:

{{
  "nombre_articulo": "Nombre completo del artículo",
  "marca": "Marca exacta",
  "modelo": "Modelo exacto",
  "caracteristicas": [
    "Característica 1",
    "Característica 2",
    "... (al menos 7, preferiblemente generales y relevantes)"
  ],
  "especificaciones_tecnicas": [
    "Especificación técnica 1: valor",
    "... (al menos 10, incluir conectividad, dimensiones, peso, capacidades, etc.)"
  ],
  "especificaciones_electricas": [
    "Especificación eléctrica 1: valor",
    "... (voltaje, amperaje, potencia, frecuencia, etc. — lista vacía [] si no aplica)"
  ],
  "incluye": [
    "Accesorio o ítem incluido 1",
    "... (todo lo que viene incluido con el producto)"
  ],
  "resumen": "Descripción del producto de 50 a 80 palabras tomada o inspirada en la documentación oficial del fabricante o proveedor."
}}

IMPORTANTE:
- El nombre, marca y modelo deben ser EXACTAMENTE los que se solicitan en los documentos.
- Las características deben ser generales y descriptivas.
- Las especificaciones técnicas deben ser precisas con sus valores.
- Si hay varios artículos, incluye una entrada por artículo en un array 'articulos': [...] con la misma estructura.
- Si es un solo artículo, devuelve directamente el objeto sin array.
"""

    log(f"  Enviando {len(partes)} doc(s) a Gemini para análisis…")
    response = modelo.generate_content([*partes, prompt])
    raw      = response.text.strip()

    # Limpiar posibles bloques markdown
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$",          "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
        log("  Análisis Gemini completado.", "OK")
        return data
    except json.JSONDecodeError as e:
        log(f"  Error al parsear JSON de Gemini: {e}", "ERR")
        log(f"  Respuesta raw: {raw[:500]}", "WARN")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 4 – BÚSQUEDA DE PRODUCTOS EN PROVEEDORES
# ═══════════════════════════════════════════════════════════════════════════════

def buscar_producto_en_proveedores(modelo, info_articulo):
    """
    Usa Gemini + Google Search Grounding para encontrar el producto
    en la lista de proveedores nacionales y extranjeros.
    Devuelve dict con: mejor_opcion, alternativas, url_imagen
    """
    from vertexai.generative_models import GenerativeModel, Tool
    from vertexai.preview.generative_models import grounding

    nombre  = info_articulo.get("nombre_articulo", "")
    marca   = info_articulo.get("marca", "")
    modelo_prod = info_articulo.get("modelo", "")

    provs_nac_str  = "\n".join(f"- {p}" for p in PROVEEDORES_NACIONALES)
    provs_ext_str  = "\n".join(f"- {p}" for p in PROVEEDORES_EXTRANJEROS)

    prompt = f"""
Eres un agente de compras especializado. Busca en internet el siguiente producto NUEVO:

PRODUCTO: {nombre}
MARCA: {marca}
MODELO: {modelo_prod}

INSTRUCCIONES DE BÚSQUEDA:
1. Busca el producto EXACTO (mismo nombre, marca y modelo) en los siguientes proveedores NACIONALES (Ecuador):
{provs_nac_str}

2. Si no hay stock en nacionales o el precio no es competitivo, busca en EXTRANJEROS:
{provs_ext_str}

3. Para cada opción encontrada obtén: URL exacta del producto, precio unitario en USD, disponibilidad, nombre exacto en la tienda.

4. Para proveedores EXTRANJEROS, calcula el costo total estimado sumando: precio + envío estimado a Ecuador + arancel aduanero (aproximadamente 20-30% del valor CIF) + otros costos logísticos.

5. Selecciona LA MEJOR OPCIÓN considerando:
   - El artículo sea EXACTAMENTE el solicitado (mismo modelo y marca)
   - El precio final total sea el MENOR posible
   - Si extranjero resulta más económico incluso con aduanas, ese es el mejor.

6. Encuentra también la URL de una imagen de alta calidad del producto (desde el proveedor o el fabricante oficial).

Devuelve ÚNICAMENTE un objeto JSON válido (sin markdown) con esta estructura:
{{
  "mejor_opcion": {{
    "proveedor": "Nombre del proveedor",
    "url_producto": "URL exacta y completa del producto",
    "precio_unitario_usd": 0.00,
    "precio_total_usd": 0.00,
    "es_extranjero": false,
    "costos_adicionales_usd": 0.00,
    "detalle_costos": "descripción de costos adicionales si aplica",
    "nombre_en_tienda": "Nombre exacto del producto en la tienda",
    "disponible": true
  }},
  "alternativas": [
    {{
      "proveedor": "Nombre proveedor 2",
      "url_producto": "URL exacta",
      "precio_total_usd": 0.00,
      "nombre_en_tienda": "Nombre en tienda"
    }},
    {{
      "proveedor": "Nombre proveedor 3",
      "url_producto": "URL exacta",
      "precio_total_usd": 0.00,
      "nombre_en_tienda": "Nombre en tienda"
    }},
    {{
      "proveedor": "Nombre proveedor 4",
      "url_producto": "URL exacta",
      "precio_total_usd": 0.00,
      "nombre_en_tienda": "Nombre en tienda"
    }}
  ],
  "url_imagen_producto": "URL directa a imagen de calidad del producto"
}}
"""

    log(f"  Buscando '{nombre} {marca} {modelo_prod}' en proveedores con Gemini…")

    #  API correcta sin disable_attribution
    try:
        from vertexai.preview.generative_models import grounding
        tool_grounding = Tool.from_google_search_retrieval(
            grounding.GoogleSearchRetrieval()   # ← sin argumentos
        )
        model_search = GenerativeModel(AI_MODEL, tools=[tool_grounding])
        response = model_search.generate_content(prompt)
    except Exception as e:
        log(f"  Grounding no disponible ({e}), usando Gemini sin grounding…", "WARN")
        response = modelo.generate_content(prompt)

    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$",          "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
        mejor = data.get("mejor_opcion", {})
        log(f"  Mejor opción: {mejor.get('proveedor','?')} → ${mejor.get('precio_total_usd','?')}", "OK")
        return data
    except json.JSONDecodeError as e:
        log(f"  Error al parsear respuesta de búsqueda: {e}", "ERR")
        log(f"  Raw: {raw[:400]}", "WARN")
        return {"mejor_opcion": {}, "alternativas": [], "url_imagen_producto": ""}


def descargar_imagen_producto(url_imagen):
    """Descarga imagen del producto desde URL y devuelve path temporal."""
    import requests
    if not url_imagen:
        return None
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url_imagen, headers=headers, timeout=15)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "image/jpeg")
        ext = ".jpg" if "jpeg" in content_type else ".png"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(r.content)
        tmp.close()
        log(f"  Imagen descargada: {len(r.content)//1024} KB", "OK")
        return tmp.name
    except Exception as e:
        log(f"  No se pudo descargar imagen: {e}", "WARN")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 5 – GENERACIÓN DE FICHA TÉCNICA (.docx)
# ═══════════════════════════════════════════════════════════════════════════════

def generar_ficha_tecnica(info_articulo, resultado_busqueda, codigo_necesidad, directorio_salida):
    """
    Copia la plantilla docx y reemplaza contenido manteniendo estilos,
    encabezado y pie de página.
    Devuelve path del archivo generado.
    """
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import lxml.etree as etree
    from copy import deepcopy

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

    # Nombre seguro para archivo
    nombre_archivo = re.sub(r'[^a-zA-Z0-9_\-]', '_', f"{codigo_necesidad}_ficha_tecnica")
    out_path       = Path(directorio_salida) / f"{nombre_archivo}.docx"

    # ── Abrir plantilla y limpiar cuerpo manteniendo estilos/encabezado/pie ──
    doc = Document(str(TEMPLATE_DOCX))

    # Limpiar todos los párrafos del cuerpo (mantiene sección con header/footer)
    cuerpo = doc.element.body
    # Guardar elemento de propiedades de sección (último elemento)
    secPr = None
    for child in list(cuerpo):
        if child.tag.endswith("}sectPr"):
            secPr = child
            break

    # Eliminar todo el contenido del cuerpo excepto sectPr
    for child in list(cuerpo):
        if not child.tag.endswith("}sectPr"):
            cuerpo.remove(child)

    # ── Función auxiliar para agregar párrafo con estilo Century Gothic ──
    def agregar_parrafo(text, bold=False, size_pt=11, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
                        espacio_antes=0, espacio_despues=0, sangria_izq=0, color=None):
        p = doc.add_paragraph()
        p.alignment = align
        pPr = p._p.get_or_add_pPr()
        # Espaciado
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:before"), str(int(espacio_antes * 20)))
        spacing.set(qn("w:after"),  str(int(espacio_despues * 20)))
        pPr.append(spacing)
        if sangria_izq:
            ind = OxmlElement("w:ind")
            ind.set(qn("w:left"), str(int(sangria_izq * 567)))  # 567 twips = 1cm
            pPr.append(ind)

        run = p.add_run(text)
        run.bold = bold
        run.font.name = "Century Gothic"
        run.font.size = Pt(size_pt)
        if color:
            run.font.color.rgb = RGBColor(*color)
        # Forzar fuente en XML
        rPr = run._r.get_or_add_rPr()
        rFonts = OxmlElement("w:rFonts")
        rFonts.set(qn("w:ascii"), "Century Gothic")
        rFonts.set(qn("w:hAnsi"), "Century Gothic")
        rPr.insert(0, rFonts)
        return p

    def agregar_item_lista(texto, size_pt=10):
        """Agrega ítem con viñeta tipográfica en Century Gothic."""
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

        # Símbolo de viñeta
        run_bul = p.add_run("•  ")
        run_bul.font.name = "Century Gothic"
        run_bul.font.size = Pt(size_pt)
        rPr_b = run_bul._r.get_or_add_rPr()
        rF = OxmlElement("w:rFonts")
        rF.set(qn("w:ascii"), "Century Gothic")
        rF.set(qn("w:hAnsi"), "Century Gothic")
        rPr_b.insert(0, rF)

        run_txt = p.add_run(texto)
        run_txt.font.name = "Century Gothic"
        run_txt.font.size = Pt(size_pt)
        rPr_t = run_txt._r.get_or_add_rPr()
        rF2 = OxmlElement("w:rFonts")
        rF2.set(qn("w:ascii"), "Century Gothic")
        rF2.set(qn("w:hAnsi"), "Century Gothic")
        rPr_t.insert(0, rF2)
        return p

    # ── TÍTULO ──
    titulo_completo = f"{nombre} {marca} {mod_prod}".strip()
    agregar_parrafo(titulo_completo, bold=True, size_pt=12,
                    align=WD_ALIGN_PARAGRAPH.CENTER, espacio_despues=6)

    # ── IMAGEN ──
    if path_img and Path(path_img).exists():
        try:
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_img = p_img.add_run()
            run_img.add_picture(path_img, width=Inches(4.5))
            log("  Imagen insertada en ficha técnica.", "OK")
        except Exception as e:
            log(f"  No se pudo insertar imagen: {e}", "WARN")
            agregar_parrafo("[Imagen del producto]", align=WD_ALIGN_PARAGRAPH.CENTER, size_pt=9)
    else:
        agregar_parrafo("[Imagen del producto no disponible]",
                        align=WD_ALIGN_PARAGRAPH.CENTER, size_pt=9, color=(128, 128, 128))

    # ── PÁRRAFO VACÍO separador ──
    agregar_parrafo("", size_pt=6)

    # ── RESUMEN ──
    if resumen:
        agregar_parrafo(resumen, size_pt=10, espacio_despues=8)
        agregar_parrafo("", size_pt=6)

    # ── CARACTERÍSTICAS ──
    if caract:
        agregar_parrafo("Características:", bold=True, size_pt=11, espacio_antes=4, espacio_despues=4)
        for c in caract:
            agregar_item_lista(c, size_pt=10)
        agregar_parrafo("", size_pt=6)

    # ── ESPECIFICACIONES TÉCNICAS ──
    if specs_tec:
        agregar_parrafo("Especificaciones técnicas:", bold=True, size_pt=11,
                        espacio_antes=4, espacio_despues=4)
        for s in specs_tec:
            agregar_item_lista(s, size_pt=10)
        agregar_parrafo("", size_pt=6)

    # ── ESPECIFICACIONES ELÉCTRICAS ──
    if specs_ele:
        agregar_parrafo("Especificaciones eléctricas:", bold=True, size_pt=11,
                        espacio_antes=4, espacio_despues=4)
        for s in specs_ele:
            agregar_item_lista(s, size_pt=10)
        agregar_parrafo("", size_pt=6)

    # ── INCLUYE ──
    if incluye:
        agregar_parrafo("Incluye:", bold=True, size_pt=11, espacio_antes=4, espacio_despues=4)
        for item in incluye:
            agregar_item_lista(item, size_pt=10)

    doc.save(str(out_path))
    log(f"  Ficha técnica guardada: {out_path.name}", "OK")
    return str(out_path), path_img


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 7 – GENERACIÓN DE PROFORMA (.xlsx)
# ═══════════════════════════════════════════════════════════════════════════════

def generar_proforma(registro_bd, info_articulo, resultado_busqueda, directorio_salida, img_path=None):
    """
    Copia la plantilla xlsx y completa las celdas indicadas.
    Devuelve path del archivo generado.
    """
    import openpyxl
    from openpyxl.drawing.image import Image as XlImage
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter
    from copy import copy as obj_copy

    codigo      = registro_bd["codigo_necesidad"]
    entidad     = str(registro_bd.get("entidad_contratante", "")).upper()
    entidad_url = str(registro_bd.get("entidad_contratante_url", ""))
    direccion   = str(registro_bd.get("direccion_entrega", ""))
    contacto    = str(registro_bd.get("contacto", ""))
    ruc_ish     = codigo[4:17] if len(codigo) >= 17 else codigo  # chars 5-17 (índice 4 a 16)

    nombre_prod = info_articulo.get("nombre_articulo", "")
    marca_prod  = info_articulo.get("marca", "")
    model_prod  = info_articulo.get("modelo", "")

    mejor        = resultado_busqueda.get("mejor_opcion", {})
    alternativas = resultado_busqueda.get("alternativas", [])

    url_mejor   = mejor.get("url_producto", "")
    urls_alt    = [a.get("url_producto", "") for a in alternativas[:3]]

    fecha_hoy   = datetime.date.today().strftime("%d/%m/%Y")
    nombre_arch = re.sub(r'[^a-zA-Z0-9_\-]', '_', codigo)
    out_path    = Path(directorio_salida) / f"{nombre_arch}.xlsm"

    # Copiar plantilla
    shutil.copy2(str(TEMPLATE_XLSX), str(out_path))

    #wb = openpyxl.load_workbook(str(out_path))
    wb = openpyxl.load_workbook(str(out_path), keep_vba=True)

    # ── Hoja "Cotización " ──
    # Buscar hoja por nombre (puede tener espacios)
    hoja_cot = None
    for sn in wb.sheetnames:
        if "cotizaci" in sn.lower():
            hoja_cot = wb[sn]
            break
    if hoja_cot is None:
        hoja_cot = wb.worksheets[0]

    def escribir_celda(ws, ref, valor):
        """
        Escribe valor en la celda indicada.
        Si la celda pertenece a un rango fusionado, redirige la escritura
        a la celda superior-izquierda de dicho rango (que sí admite .value).
        """
        from openpyxl.utils import get_column_letter, column_index_from_string
        import re as _re

        # Comprobar si ref cae dentro de algún rango fusionado
        for merged_range in ws.merged_cells.ranges:
            if ref in merged_range:
                # Escribir en la celda ancla del rango fusionado
                anchor = f"{get_column_letter(merged_range.min_col)}{merged_range.min_row}"
                ws[anchor].value = valor
                return

        # Celda normal: escritura directa
        ws[ref].value = valor

    escribir_celda(hoja_cot, "B8",  entidad)
    escribir_celda(hoja_cot, "B9",  ruc_ish)
    escribir_celda(hoja_cot, "B10", direccion)
    escribir_celda(hoja_cot, "B11", contacto)
    escribir_celda(hoja_cot, "D12", codigo)
    escribir_celda(hoja_cot, "I8",  fecha_hoy)

    # Celda C16/C17 – nombre, marca y modelo del producto
    texto_prod_linea1 = f"{nombre_prod}"
    texto_prod_linea2 = f"Marca: {marca_prod} | Modelo: {model_prod}"
    escribir_celda(hoja_cot, "C16", texto_prod_linea1)
    escribir_celda(hoja_cot, "C17", texto_prod_linea2)

    # Insertar imagen del producto en celda C16 si está disponible
    if img_path and Path(img_path).exists():
        try:
            img_xl = XlImage(img_path)
            img_xl.width  = 120
            img_xl.height = 90
            # Anclar cerca de C16
            img_xl.anchor = "G16"
            hoja_cot.add_image(img_xl)
            log("  Imagen insertada en Excel.", "OK")
        except Exception as e:
            log(f"  No se pudo insertar imagen en Excel: {e}", "WARN")

    # ── Hoja "Costos" ──
    hoja_cos = None
    for sn in wb.sheetnames:
        if "costo" in sn.lower():
            hoja_cos = wb[sn]
            break
    if hoja_cos is None and len(wb.worksheets) > 1:
        hoja_cos = wb.worksheets[1]

    if hoja_cos is not None:
        escribir_celda(hoja_cos, "C7",  entidad_url)
        escribir_celda(hoja_cos, "K14", url_mejor)
        # Alternativas en orden decreciente de calidad
        refs_alt = ["J16", "J17", "J18"]
        for i, url_a in enumerate(urls_alt[:3]):
            escribir_celda(hoja_cos, refs_alt[i], url_a)

    wb.save(str(out_path))
    log(f"  Proforma guardada: {out_path.name}", "OK")
    return str(out_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 9 – VERIFICACIÓN EN BUCKET Y ACTUALIZACIÓN DE BD
# ═══════════════════════════════════════════════════════════════════════════════

def verificar_blobs_en_bucket(gcs_client, blob_docx, blob_xlsx):
    """
    Comprueba que los dos blobs (rutas dentro del bucket) existan y tengan
    tamaño mayor a cero.  Devuelve (ok_docx, ok_xlsx).
    """
    bucket = gcs_client.bucket(BUCKET_NAME)

    def existe_y_valido(blob_name):
        blob = bucket.blob(blob_name)
        blob.reload()          # Refresca metadatos desde GCS
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
    """
    Actualiza la etapa del registro correspondiente de 'en generacion'
    a 'finalizada' en la tabla infimas.
    """
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
        log(f"  No se actualizó ningún registro para {codigo_necesidad} "
            f"(¿ya estaba en otro estado?).", "WARN")


# ═══════════════════════════════════════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "═"*60)
    print("  Preform_generator — Automatización de Documentos")
    print("═"*60 + "\n")

    # ── 1. Base de datos ─────────────────────────────────────────
    paso(1, 9, "Obteniendo registros de la BD MySQL")
    data_table_1 = obtener_data_table_1()
    if not data_table_1:
        log("No hay registros 'en generacion'. Fin.", "WARN")
        return

    # ── 2. Clientes GCS y VertexAI ───────────────────────────────
    paso(2, 9, "Inicializando clientes GCS y VertexAI")
    gcs_client = obtener_cliente_gcs()
    modelo_ai  = inicializar_vertex_ai()

    # ── Directorio de salida temporal ────────────────────────────
    dir_salida = Path(tempfile.mkdtemp(prefix="nexus_out_"))
    log(f"Directorio de trabajo temporal: {dir_salida}")

    errores = []

    # ── Procesar cada código de necesidad ────────────────────────
    for idx, registro in enumerate(data_table_1, 1):
        codigo = registro["codigo_necesidad"]
        print(f"\n{'━'*60}")
        print(f"  [{idx}/{len(data_table_1)}] Procesando: {codigo}")
        print(f"{'━'*60}")

        dir_necesidad = dir_salida / codigo
        dir_necesidad.mkdir(exist_ok=True)

        try:
            # ── 3. Obtener y analizar documentos del bucket ───────
            paso(3, 9, f"Descargando y analizando documentos — {codigo}")
            blobs = listar_docs_necesidad(gcs_client, codigo)
            if not blobs:
                log(f"Sin documentos en bucket para {codigo}. Saltando.", "WARN")
                errores.append(f"{codigo}: sin documentos en bucket.")
                continue

            archivos_locales = []
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

            # ── FIX: Maneja los 4 formatos posibles que devuelve Gemini ──
            if isinstance(info_articulo, list):
                # Gemini devolvió lista directamente → [{...}, {...}]
                articulos = info_articulo
                log(f"  Múltiples artículos detectados (lista raíz): {len(articulos)}")
                info_principal = articulos[0] if articulos and isinstance(articulos[0], dict) else {}
            elif isinstance(info_articulo, dict) and "articulos" in info_articulo:
                # {"articulos": [{...}]}  o  {"articulos": [[{...}]]}
                articulos = info_articulo["articulos"]
                if articulos and isinstance(articulos[0], list):
                    articulos = articulos[0]   # desanidar [[{...}]] → [{...}]
                log(f"  Múltiples artículos detectados: {len(articulos)}")
                info_principal = articulos[0] if articulos and isinstance(articulos[0], dict) else {}
            elif isinstance(info_articulo, dict):
                # Objeto directo {"nombre_articulo": ...}
                info_principal = info_articulo
            else:
                info_principal = {}

            if not info_principal:
                log(f"  No se pudo extraer artículo del análisis de Gemini.", "ERR")
                errores.append(f"{codigo}: formato de respuesta Gemini no reconocido.")
                continue

            log(f"  Artículo: {info_principal.get('nombre_articulo','')} "
                f"| Marca: {info_principal.get('marca','')} "
                f"| Modelo: {info_principal.get('modelo','')}", "OK")

            # ── 4. Buscar producto en proveedores ─────────────────
            paso(4, 9, f"Buscando producto en proveedores — {codigo}")
            resultado_busqueda = buscar_producto_en_proveedores(modelo_ai, info_principal)

            # ── 5. Generar ficha técnica .docx ────────────────────
            paso(5, 9, f"Generando ficha técnica .docx — {codigo}")
            path_docx, path_img = generar_ficha_tecnica(
                info_principal, resultado_busqueda, codigo, str(dir_necesidad)
            )

            # ── 6. Subir ficha técnica al bucket ──────────────────
            paso(6, 9, f"Subiendo ficha técnica al bucket — {codigo}")
            blob_docx = subir_archivo_a_bucket(gcs_client, path_docx, "Fichas Tecnicas")

            # ── Pausa de 60 segundos antes de generar la proforma ─
            log("  Esperando 60 segundos antes de generar la proforma…", "INFO")
            time.sleep(60)

            # ── 7. Generar proforma .xlsx ─────────────────────────
            paso(7, 9, f"Generando proforma .xlsx — {codigo}")
            path_xlsx = generar_proforma(
                registro, info_principal, resultado_busqueda,
                str(dir_necesidad), img_path=path_img
            )

            # ── 8. Subir proforma al bucket ───────────────────────
            paso(8, 9, f"Subiendo proforma al bucket — {codigo}")
            blob_xlsx = subir_archivo_a_bucket(gcs_client, path_xlsx, "Proformas")

            # ── 9. Verificar subidas y actualizar BD ──────────────
            paso(9, 9, f"Verificando archivos en bucket y actualizando BD — {codigo}")
            ok_docx, ok_xlsx = verificar_blobs_en_bucket(gcs_client, blob_docx, blob_xlsx)

            if ok_docx and ok_xlsx:
                log(f"  Ficha técnica en bucket: ✔", "OK")
                log(f"  Proforma en bucket:      ✔", "OK")
                actualizar_etapa_bd(codigo)
            else:
                msg_partes = []
                if not ok_docx:
                    msg_partes.append("ficha técnica no verificada en bucket")
                    log(f"  Ficha técnica en bucket: ✗", "ERR")
                if not ok_xlsx:
                    msg_partes.append("proforma no verificada en bucket")
                    log(f"  Proforma en bucket:      ✗", "ERR")
                motivo = "; ".join(msg_partes)
                log(f"  BD NO actualizada para {codigo}: {motivo}", "WARN")
                errores.append(f"{codigo}: {motivo}")

            # Limpiar temporales de documentos
            for f in archivos_locales:
                try: os.unlink(f)
                except: pass
            if path_img:
                try: os.unlink(path_img)
                except: pass

            log(f"✔ {codigo} procesado exitosamente.", "OK")

        except Exception as e:
            log(f"Error procesando {codigo}: {e}", "ERR")
            traceback.print_exc()
            errores.append(f"{codigo}: {e}")

    # ── Resumen final ─────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  RESUMEN FINAL")
    print(f"{'═'*60}")
    exitosos = len(data_table_1) - len(errores)
    log(f"Procesados exitosamente: {exitosos}/{len(data_table_1)}", "OK")
    if errores:
        log("Errores encontrados:", "WARN")
        for e in errores:
            print(f"    ✗ {e}")

    # Limpiar directorio temporal
    try:
        shutil.rmtree(str(dir_salida))
    except Exception:
        pass

    print(f"\n{'═'*60}")
    print("  Preform_generator finalizado.")
    print(f"{'═'*60}\n")

if __name__ == "__main__":
    main()