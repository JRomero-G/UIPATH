#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 GENERADOR AUTOMÁTICO DE FICHAS TÉCNICAS (.docx) Y PROFORMAS (.xlsm)
═══════════════════════════════════════════════════════════════════════════════

Automatización de procesos de contratación para IMPOCRUZ EC S.A.S.

Flujo general (resumen de las 9 etapas del requerimiento):
  1) Lee de MySQL (gestorex.infimas) las líneas con etapa = "en generacion".
  2) Entra al bucket de Google Cloud → carpeta "Documentos de Contratación"
     → subcarpeta por cada "codigo_necesidad" y descarga doc/docx/pdf.
  3) Pide a Gemini (Vertex AI) que analice esos documentos y extraiga los
     artículos de compra. Si hay > 10 artículos distintos → ficha con aviso
     en rojo, NO se genera proforma y la etapa pasa a "finalizada".
  4) Con Gemini (búsqueda web con grounding) + Claude Sonnet 4.6 (vía Vertex)
     busca el/los artículo(s) en la lista de proveedores y elige la mejor
     opción por menor precio (considerando logística si es extranjero).
  5) Genera la ficha técnica .docx respetando la plantilla provista
     (fuente Century Gothic, encabezado y pie de IMPOCRUZ).
  6) Sube cada ficha .docx generada a la carpeta "Fichas Técnicas" del bucket.
  7) Genera la proforma a partir de "FORMATO DE PROFORMA RECREADO VACÍO.xlsm",
     modificando ÚNICAMENTE las celdas indicadas y preservando macros/formato.
  8) Sube cada proforma .xlsm generada a la carpeta "Proformas" del bucket.
  9) Cambia la etapa de "en generacion" a "finalizada".

NOTAS DE INGENIERÍA IMPORTANTES (verificadas contra las plantillas reales):
  • La hoja de cotización se llama EXACTAMENTE "Cotización " (con un espacio
    final). No se renombra ninguna hoja.
  • El libro contiene MACROS (VBA) → se abre y guarda con keep_vba=True.
  • Existe un DESFASE entre hojas: el producto k ocupa
        Cotización!fila (15 + k)   →  nombre en C, cantidad en G
        Costos!fila    (14 + k)    →  URL en C, valor real en E, extras en G
    (confirmado por las fórmulas internas Costos!F15='Cotización '!G16, etc.).
  • El requerimiento pide escribir el código de necesidad en "B12", pero en la
    plantilla real B12 forma parte de la celda combinada A12:C12 que contiene
    la etiqueta "CODIGO NECESIDAD DE CONTRATACION:". El valor real corresponde
    a la celda combinada contigua D12:E12, por lo que se escribe en D12.
  • NO se tocan las fórmulas ni celdas que el requerimiento no menciona.
  • Plantilla actualizada y RE-VERIFICADA: el encabezado de la tabla de ítems está en
    la fila 14 (Ítem/CPC/Producto/U·M/Cantidad/Costo unitario/Costo total). El PRIMER
    producto se mantiene en Cotización!16 ↔ Costos!15 (mismo desfase de siempre, según
    las fórmulas internas). La plantilla incluye una fila de muestra (fila 15 de
    «Cotización », con un CPC de ejemplo) que se deja intacta a propósito, por lo que los
    productos se escriben a partir de la fila 16. Subtotales/IVA/total y los enlaces entre
    hojas se recalculan sin errores con estos datos.
  • Carpetas del bucket (nombres exactos): los documentos de contratación se LEEN de
    "Documentos de Contratación/<código de necesidad>/"; las fichas se SUBEN a
    "Fichas Técnicas" y las proformas a "Proformas".

Autor: (automatización generada para IMPOCRUZ EC S.A.S.)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import io
import re
import sys
import json
import time
import tempfile
import datetime
import traceback
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# ── Dependencias de terceros (ver requirements.txt) ───────────────────────────
#   pip install mysql-connector-python google-cloud-storage \
#               "anthropic[vertex]" google-genai python-docx openpyxl \
#               pillow requests
import requests
import mysql.connector
from google.cloud import storage

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

# ── Objeto de configuración compartido del proyecto (Config/Global) ───────────
#   Igual que en los demás scripts del proyecto: se añade la raíz del proyecto al
#   sys.path y se importa "Global" desde el paquete Config. De ahí provienen las
#   credenciales ADECUADAS (DB_HOST, DB_USER, DB_PASSWORD, DATABASE,
#   GEMINI_CREDENTIALS, BUCKET_NAME, etc.). El helper _g() (más abajo) leerá estos
#   valores con prioridad. Si el script se ejecuta fuera del proyecto y no encuentra
#   el paquete Config, se continúa con CONFIG_LOCAL / variables de entorno.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from Config import Global
except Exception:
    Global = None


# ═══════════════════════════════════════════════════════════════════════════════
#  0)  UTILIDAD DE REGISTRO EN TERMINAL
#      El script muestra cada paso para observar su correcto funcionamiento.
# ═══════════════════════════════════════════════════════════════════════════════
class Consola:
    """Pequeño ayudante de logging con marcas visuales para la terminal."""

    AZUL = "\033[94m"; VERDE = "\033[92m"; AMAR = "\033[93m"
    ROJO = "\033[91m"; GRIS = "\033[90m"; NEG = "\033[1m"; FIN = "\033[0m"

    @staticmethod
    def _hora() -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")

    @classmethod
    def etapa(cls, titulo: str) -> None:
        print(f"\n{cls.AZUL}{cls.NEG}{'═' * 79}{cls.FIN}")
        print(f"{cls.AZUL}{cls.NEG}▶ {titulo}{cls.FIN}")
        print(f"{cls.AZUL}{cls.NEG}{'═' * 79}{cls.FIN}")

    @classmethod
    def info(cls, msg: str) -> None:
        print(f"{cls.GRIS}[{cls._hora()}]{cls.FIN} {msg}")

    @classmethod
    def ok(cls, msg: str) -> None:
        print(f"{cls.GRIS}[{cls._hora()}]{cls.FIN} {cls.VERDE}✓{cls.FIN} {msg}")

    @classmethod
    def aviso(cls, msg: str) -> None:
        print(f"{cls.GRIS}[{cls._hora()}]{cls.FIN} {cls.AMAR}⚠ {msg}{cls.FIN}")

    @classmethod
    def error(cls, msg: str) -> None:
        print(f"{cls.GRIS}[{cls._hora()}]{cls.FIN} {cls.ROJO}✗ {msg}{cls.FIN}")


log = Consola


# ═══════════════════════════════════════════════════════════════════════════════
#  1)  CONFIGURACIÓN GLOBAL
#
#  Cada valor se resuelve con esta PRIORIDAD:
#      1) atributo del objeto Global  (si tu plataforma NEXUS lo provee),
#      2) variable de entorno del sistema operativo,
#      3) bloque CONFIG_LOCAL de aquí abajo  (edición manual),
#      4) valor por defecto.
#
#  ►► SI EJECUTAS EL SCRIPT DE FORMA AUTÓNOMA (sin el objeto Global y sin variables
#     de entorno), RELLENA CONFIG_LOCAL. Es lo único que necesitas tocar para correrlo.
# ═══════════════════════════════════════════════════════════════════════════════
CONFIG_LOCAL = {
    # --- Base de datos MySQL -------------------------------------------------
    "DB_HOST":     "",            # p. ej. "localhost"
    "DB_USER":     "",            # p. ej. "root"
    "DB_PASSWORD": "",            # contraseña de la base de datos
    "DATABASE":    "gestorex",    # nombre de la base de datos

    # --- Google Cloud / Vertex AI --------------------------------------------
    # Ruta ABSOLUTA al archivo .json de la cuenta de servicio de Google Cloud.
    # En Windows, antepón una "r" y usa la ruta tal cual (con barras invertidas),
    # por ejemplo:
    #     r"C:\Users\donom\Documents\Proyecto NEXUS\credenciales.json"
    "GEMINI_CREDENTIALS": r"C:\Users\donom\Documents\Proyecto NEXUS\Repositorio github\UIPATH\src\Credentials\Clave_bucket_AIgemini.json",
    "BUCKET_NAME":        "",     # nombre EXACTO del bucket de Google Cloud Storage

    # --- Regiones de Vertex AI (opcional; cámbialas si tu proyecto usa otras) -
    "VERTEX_LOCATION_GEMINI": "us-central1",
    "VERTEX_REGION_CLAUDE":   "us-east5",
}


def _g(nombre: str, defecto: str = "") -> str:
    """Obtiene un valor de configuración respetando la prioridad descrita arriba:
    Global.*  →  variable de entorno  →  CONFIG_LOCAL  →  valor por defecto.
    Un valor vacío en una fuente NO bloquea: se pasa a la siguiente."""
    # 1) Objeto Global de la plataforma (si está definido y tiene el atributo).
    try:
        valor = getattr(Global, nombre)           # type: ignore  # provisto por la plataforma
        if valor:
            return valor
    except (NameError, AttributeError):
        pass
    # 2) Variable de entorno del sistema.
    valor = os.environ.get(nombre)
    if valor:
        return valor
    # 3) Bloque CONFIG_LOCAL editable.
    valor = CONFIG_LOCAL.get(nombre)
    if valor:
        return valor
    # 4) Valor por defecto.
    return defecto


# --- Conexión a la base de datos MySQL --------------------------------------------------
MYSQL_CONFIG = {
    "host":               _g("DB_HOST"),
    "user":               _g("DB_USER"),
    "password":           _g("DB_PASSWORD"),
    "database":           _g("DATABASE", "gestorex"),
    "connection_timeout": 20,
}

# --- Google Cloud / Vertex AI -----------------------------------------------------------
# En el Config del proyecto, la ruta de credenciales se expone como RENDER_CRENDENTIALS_JSON
# (mismo nombre de atributo que usan los demás scripts; se respeta su grafía exacta). Si no
# hay objeto Config disponible, se recurre a la variable de entorno / CONFIG_LOCAL bajo la
# clave GEMINI_CREDENTIALS.
GEMINI_CREDENTIALS_PATH = _g("GEMINI_CREDENTIALS")
BUCKET_NAME             = _g("BUCKET_NAME")

# Carpetas del bucket (nombres EXACTOS, con tildes y espacios incluidos):
#   • Lectura  : los documentos de contratación están en "Documentos de Contratación",
#                con una subcarpeta por cada código de necesidad de data_table_1.
#   • Escritura: las fichas .docx van a "Fichas Técnicas" y las proformas .xlsm a "Proformas".
BUCKET_FOLDER            = "Documentos de Contratación"   # lectura  (subcarpetas por código)
BUCKET_FOLDER_FICHAS     = "Fichas Técnicas"              # destino de las fichas .docx
BUCKET_FOLDER_PROFORMAS  = "Proformas"                    # destino de las proformas .xlsm

# Modelos de IA.
AI_MODEL_GEMINI   = "gemini-2.5-pro"     # análisis multimodal de documentos + grounding web
AI_MODEL_CLAUDE   = "claude-sonnet-4-6"  # "Sonnet 4.6": razonamiento/selección de proveedor

# Regiones de Vertex AI (ajustar según disponibilidad del proyecto).
VERTEX_LOCATION_GEMINI = _g("VERTEX_LOCATION_GEMINI", "us-central1")
VERTEX_REGION_CLAUDE   = _g("VERTEX_REGION_CLAUDE",   "us-east5")

# --- Rutas de las plantillas (junto al script) ------------------------------------------
SCRIPT_DIR    = Path(__file__).parent
TEMPLATE_DOCX = SCRIPT_DIR / "FICHA TECNICA MICROFONO Y MEMORIA.docx"
TEMPLATE_XLSX = SCRIPT_DIR / "FORMATO DE PROFORMA RECREADO VACÍO.xlsm"

# --- Parámetros del negocio -------------------------------------------------------------
ETAPA_ORIGEN   = "en generacion"   # filtro de selección en la columna "etapa"
ETAPA_DESTINO  = "finalizada"      # estado al terminar (o al superar el límite)
LIMITE_ARTICULOS = 10              # límite permitido de artículos distintos por necesidad
                                   # (el requerimiento se redacta de forma ambigua entre
                                   #  "menor a 10" y "más de 10"; aquí: se supera con > 10,
                                   #  coherente con el aviso "supera el límite de 10").
CIUDAD_BASE = "Guayaquil"          # origen logístico de la empresa

# Lista de proveedores de confianza (nacionales + extranjeros) que la IA debe priorizar.
PROVEEDORES_NACIONALES = {
    "Mi bodega": "https://mibodega.ec/",
    "Bodeguita del ahorro": "https://bodeguitadelahorro.com/",
    "Comercial Vaca": "https://comercialvaca.ec/",
    "Kissu": "https://kissu.com.ec/",
    "Almacén Altaten": "https://altatenalmacen.com.ec/",
    "TVentas": "https://www.tventas.com/",
    "Intcomex": "https://store.intcomex.com/es-XPE/Home",
    "La Victoria": "https://lavictoria.ec/",
    "Marcimex": "https://www.marcimex.com/",
    "Almacenes España": "https://almacenesespana.ec/",
    "Novicompu": "https://www.novicompu.com/",
    "Techno Prime": "https://technoprimec.com/",
    "Point": "https://point.com.ec/",
    "Computron": "https://www.computron.com.ec/",
    "Nomadaware": "https://nomadaware.com.ec/",
    "IDC Mayoristas": "https://www.idcmayoristas.com/",
    "Tecnit": "https://tecnit.com.ec/",
    "TecnoMega": "https://tecnomegastore.ec/",
    "Artefacta": "https://www.artefacta.com/",
    "Mundo Tek": "https://mundotek.com.ec/",
    "Almacenes Juan Eljuri": "https://eljuri.store/",
    "Kywi": "https://www.kywi.com.ec/",
    "Tecnocosto": "https://tecnocostoec.com/",
    "Almacenes Japón": "https://www.almacenesjapon.com/",
    "Electromega": "https://electromegaecuador.com/",
    "Compra Ecuador": "https://www.compraecuador.com/",
    "Gran Hogar": "https://granhogar.com.ec/",
    "Miami Home EC": "https://miamihome-ec.com/",
}
PROVEEDORES_EXTRANJEROS = {
    "Amazon": "https://www.amazon.com/",
    "Mercado Libre": "https://www.mercadolibre.com.hn/",
    "Ebay": "https://www.ebay.com/",
}

# --- Mapa de celdas de la proforma (verificado contra la plantilla real) ----------------
# Hoja "Cotización " (¡con espacio final!)
HOJA_COTIZACION = "Cotización "
CELDAS_COTIZACION = {
    "entidad":       "B8",   # entidad contratante en MAYÚSCULAS  (combinada B8:G8)
    "codigo_5_17":   "B9",   # caracteres 5..17 del código          (combinada B9:F9)
    "direccion":     "B10",  # dirección de entrega                 (combinada B10:F10)
    "contacto":      "B11",  # contacto (nombre + correo o teléfono)(combinada B11:D11)
    "codigo":        "D12",  # código de necesidad completo (ver nota de cabecera; spec=B12)
    "num_proforma":  "I3",   # número de proforma 00100100###
    "fecha":         "I8",   # fecha de creación dd/mm/aaaa
}
COT_PRODUCTO_COL_NOMBRE = "C"   # nombre/marca/modelo del producto (C16, C17, ...)
COT_PRODUCTO_COL_CANT   = "G"   # cantidad (G16, G17, ...)
COT_PRIMERA_FILA_PROD   = 16    # el primer producto va en la fila 16
COT_ULTIMA_FILA_PROD    = 25    # hasta la fila 25 (10 productos)

# Hoja "Costos"
HOJA_COSTOS = "Costos"
COSTOS_URL_CONTRATANTE = "C7"   # URL del contratante                 (combinada C7:F9)
COSTOS_PRIMERA_FILA    = 15     # el primer producto va en la fila 15 (desfase de -1 vs Cotización)
COSTOS_ULTIMA_FILA     = 24     # hasta la fila 24
COSTOS_COL_URL         = "C"    # URL del producto (C15..C24, combinadas Cx:Dx)
COSTOS_COL_VALOR_REAL  = "E"    # valor real unitario (E15..E24)
COSTOS_COL_EXTRAS      = "G"    # costos extras: envío/aduana/instalación (G15..G24)
# Bloques de alternativas en columna J: producto k → encabezado J(10+4k), slots J(11+4k..13+4k)


# ═══════════════════════════════════════════════════════════════════════════════
#  ESTRUCTURAS DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class Articulo:
    """Un artículo de compra ya analizado y con su mejor opción de proveedor."""
    nombre: str = ""
    marca: str = ""
    modelo: str = ""
    resumen: str = ""                                   # 50–80 palabras (web del fabricante/proveedor)
    caracteristicas: List[str] = field(default_factory=list)            # ≥7 si es posible
    especificaciones_tecnicas: List[str] = field(default_factory=list)  # ≥10 si es posible
    especificaciones_electricas: List[str] = field(default_factory=list)
    incluye: List[str] = field(default_factory=list)
    cantidad: int = 1
    # Mejor opción encontrada:
    proveedor: str = ""
    url_mejor: str = ""
    es_extranjero: bool = False
    precio_unitario: float = 0.0          # costo real SIN extras
    costo_extra: float = 0.0              # envío/aduana/instalación/recargo fuera de Guayaquil
    moneda: str = "USD"
    imagen_url: str = ""                  # imagen principal del producto
    imagenes_extra: List[str] = field(default_factory=list)
    alternativas: List[str] = field(default_factory=list)   # hasta 3 URLs, orden decreciente de cercanía
    coincidencia: float = 0.0             # % de coincidencia con los documentos de contratación

    @property
    def titulo(self) -> str:
        return " ".join(p for p in [self.nombre, self.marca, self.modelo] if p).strip()


@dataclass
class Necesidad:
    """Una línea de la tabla 'infimas' en etapa 'en generacion'."""
    id: str
    codigo: str
    entidad: str
    entidad_url: str
    direccion: str
    contacto: str
    articulos: List[Articulo] = field(default_factory=list)
    supera_limite: bool = False
    num_distintos: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
#  2)  ACCESO A LA BASE DE DATOS  (etapa 1 y etapa 9)
# ═══════════════════════════════════════════════════════════════════════════════
class BaseDatos:
    """Encapsula la lectura de 'infimas' y la actualización de la etapa."""

    def __init__(self, config: dict):
        self.config = config

    def _conectar(self):
        return mysql.connector.connect(**self.config)

    def obtener_necesidades(self) -> List[Necesidad]:
        """Etapa 1: toma las líneas 'en generacion' y las guarda en data_table_1."""
        log.info("Conectando a MySQL y consultando la tabla `infimas`…")
        # NOTA: se usan backticks porque hay identificadores con acentos/espacios/símbolos.
        #       Ajuste el nombre real de la columna de ID si difiere de `# de ID`.
        sql = (
            "SELECT `id_infima`            AS id, "
            "       `codigo_necesidad`   AS codigo, "
            "       `entidad_contratante` AS entidad, "
            "       `entidad_contratante_url` AS entidad_url, "
            "       `direccion_entrega`  AS direccion, "
            "       `contacto`           AS contacto "
            "FROM `infimas` "
            "WHERE `etapa` = %s"
        )
        cnx = self._conectar()
        try:
            cur = cnx.cursor(dictionary=True)
            cur.execute(sql, (ETAPA_ORIGEN,))
            filas = cur.fetchall()
            cur.close()
        finally:
            cnx.close()

        necesidades = [
            Necesidad(
                id=str(f["id"]),
                codigo=str(f["codigo"]).strip(),
                entidad=(f.get("entidad") or "").strip(),
                entidad_url=(f.get("entidad_url") or "").strip(),
                direccion=(f.get("direccion") or "").strip(),
                contacto=(f.get("contacto") or "").strip(),
            )
            for f in filas
        ]
        log.ok(f"{len(necesidades)} línea(s) en etapa «{ETAPA_ORIGEN}» cargadas en data_table_1.")
        return necesidades

    def finalizar(self, codigo: str) -> None:
        """Etapas 3c y 9: cambia la etapa de la línea a 'finalizada'."""
        sql = "UPDATE `infimas` SET `etapa` = %s WHERE `codigo_necesidad` = %s"
        cnx = self._conectar()
        try:
            cur = cnx.cursor()
            cur.execute(sql, (ETAPA_DESTINO, codigo))
            cnx.commit()
            cur.close()
        finally:
            cnx.close()
        log.ok(f"Etapa de «{codigo}» actualizada a «{ETAPA_DESTINO}» en la base de datos.")


# ═══════════════════════════════════════════════════════════════════════════════
#  ACCESO AL BUCKET DE GOOGLE CLOUD STORAGE  (etapas 2, 6 y 8)
# ═══════════════════════════════════════════════════════════════════════════════
EXTENSIONES_VALIDAS = (".doc", ".docx", ".pdf")


class Bucket:
    """Lectura de documentos de contratación y subida de entregables."""

    def __init__(self, credenciales_json: str, nombre_bucket: str):
        self.cliente = storage.Client.from_service_account_json(credenciales_json)
        self.bucket = self.cliente.bucket(nombre_bucket)
        self.nombre_bucket = nombre_bucket

    def listar_documentos(self, codigo: str) -> List[storage.Blob]:
        """Etapa 2: lista doc/docx/pdf dentro de 'Documentos de Contratación/<codigo>/'."""
        prefijo = f"{BUCKET_FOLDER}/{codigo}/"
        blobs = [
            b for b in self.cliente.list_blobs(self.bucket, prefix=prefijo)
            if b.name.lower().endswith(EXTENSIONES_VALIDAS)
        ]
        log.info(f"   · {len(blobs)} documento(s) encontrados en «{prefijo}».")
        return blobs

    def descargar_bytes(self, blob: storage.Blob) -> bytes:
        return blob.download_as_bytes()

    def gs_uri(self, blob: storage.Blob) -> str:
        return f"gs://{self.nombre_bucket}/{blob.name}"

    def subir(self, ruta_local: Path, carpeta_destino: str, nombre_destino: str) -> str:
        """Etapas 6 y 8: sube un archivo a la carpeta indicada del bucket.

        'carpeta_destino' es el nombre EXACTO de la carpeta de nivel superior del
        bucket donde debe quedar el archivo (p. ej. "Fichas Técnicas" o "Proformas").
        El nombre del archivo ya incluye el código de necesidad y el ID, por lo que
        no se requiere una subcarpeta adicional para evitar colisiones.
        """
        destino = f"{carpeta_destino}/{nombre_destino}"
        blob = self.bucket.blob(destino)
        blob.upload_from_filename(str(ruta_local))
        log.ok(f"   · Subido al bucket: «{destino}».")
        return destino


# ═══════════════════════════════════════════════════════════════════════════════
#  MOTORES DE IA  (Gemini en Vertex + Claude Sonnet 4.6 en Vertex)
# ═══════════════════════════════════════════════════════════════════════════════
def _json_desde_texto(texto: str) -> dict:
    """Extrae el primer objeto JSON de una respuesta de IA (tolerante a ```json```)."""
    if not texto:
        return {}
    limpio = texto.strip()
    limpio = re.sub(r"^```(?:json)?", "", limpio).strip()
    limpio = re.sub(r"```$", "", limpio).strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        # Buscar el bloque {...} más externo.
        inicio, fin = limpio.find("{"), limpio.rfind("}")
        if inicio != -1 and fin != -1 and fin > inicio:
            try:
                return json.loads(limpio[inicio:fin + 1])
            except json.JSONDecodeError:
                pass
    log.aviso("No se pudo interpretar la respuesta de la IA como JSON.")
    return {}


class MotoresIA:
    """Inicializa y expone los dos motores de IA usados por el script."""

    def __init__(self):
        # --- Cliente Gemini (Google Gen AI SDK en modo Vertex AI) -----------------
        from google import genai
        from google.genai import types as genai_types
        self._genai = genai
        self._gtypes = genai_types

        # El project_id se toma del propio service-account .json.
        with open(GEMINI_CREDENTIALS_PATH, "r", encoding="utf-8") as fh:
            self.project_id = json.load(fh).get("project_id", "")

        # Las credenciales se exponen a las librerías de Google vía variable de entorno.
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", GEMINI_CREDENTIALS_PATH)

        self.gemini = genai.Client(
            vertexai=True, project=self.project_id, location=VERTEX_LOCATION_GEMINI
        )
        log.ok(f"Gemini «{AI_MODEL_GEMINI}» inicializado (proyecto {self.project_id}, "
               f"región {VERTEX_LOCATION_GEMINI}).")

        # --- Cliente Claude (Anthropic en Vertex AI) ------------------------------
        from anthropic import AnthropicVertex
        self.claude = AnthropicVertex(
            project_id=self.project_id, region=VERTEX_REGION_CLAUDE
        )
        log.ok(f"Claude «{AI_MODEL_CLAUDE}» inicializado (región {VERTEX_REGION_CLAUDE}).")

    # ───────────────────────────────────────────────────────────────────────────
    #  Etapa 3: análisis de los documentos del bucket con Gemini (multimodal)
    # ───────────────────────────────────────────────────────────────────────────
    def analizar_documentos(self, necesidad: Necesidad,
                            bucket: "Bucket", blobs: List[storage.Blob]) -> dict:
        """
        Lee los documentos de contratación y extrae la lista de artículos distintos
        con su cantidad. Devuelve {'articulos': [...], 'num_distintos': int}.
        Los PDF se envían por su URI gs:// (Gemini los lee de forma nativa); los
        doc/docx se adjuntan como texto extraído.
        """
        partes = []
        instruccion = f"""Eres un analista experto en pliegos de contratación pública del Ecuador.
Analiza TODOS los documentos adjuntos correspondientes al código de necesidad
«{necesidad.codigo}» e identifica los ARTÍCULOS DE COMPRA distintos solicitados.

Devuelve ESTRICTAMENTE un objeto JSON con esta forma (sin texto adicional):
{{
  "num_distintos": <entero: cantidad de artículos DISTINTOS solicitados>,
  "articulos": [
    {{
      "nombre": "<nombre del artículo>",
      "marca": "<marca si se especifica, si no, vacío>",
      "modelo": "<modelo si se especifica, si no, vacío>",
      "cantidad": <entero: cantidad solicitada de ESTE artículo>,
      "caracteristicas_solicitadas": ["<requisito 1>", "..."],
      "especificaciones_solicitadas": ["<especificación técnica/eléctrica 1>", "..."]
    }}
  ]
}}

Reglas:
- Si el documento NO especifica marca/modelo, deja esos campos vacíos
  (luego se propondrá un producto que cumpla las características).
- "num_distintos" es el número de productos diferentes, NO la suma de cantidades.
- Sé exhaustivo con las características y especificaciones técnicas/eléctricas."""
        partes.append(self._gtypes.Part.from_text(text=instruccion))

        # Adjuntar cada documento según su tipo.
        for blob in blobs:
            nombre = blob.name.lower()
            if nombre.endswith(".pdf"):
                partes.append(self._gtypes.Part.from_uri(
                    file_uri=bucket.gs_uri(blob), mime_type="application/pdf"))
            else:  # .doc / .docx → extraer texto y adjuntarlo
                texto = self._extraer_texto(bucket.descargar_bytes(blob), nombre)
                if texto.strip():
                    partes.append(self._gtypes.Part.from_text(
                        text=f"\n--- Contenido de {Path(blob.name).name} ---\n{texto}"))

        log.info("   · Enviando documentos a Gemini para su análisis…")
        respuesta = self.gemini.models.generate_content(
            model=AI_MODEL_GEMINI, contents=partes
        )
        data = _json_desde_texto(respuesta.text)
        data.setdefault("articulos", [])
        data.setdefault("num_distintos", len(data["articulos"]))
        log.ok(f"   · Gemini detectó {data['num_distintos']} artículo(s) distinto(s).")
        return data

    @staticmethod
    def _extraer_texto(contenido: bytes, nombre: str) -> str:
        """Extrae texto plano de un .docx (o .doc convertido) para la IA."""
        try:
            if nombre.endswith(".docx"):
                doc = Document(io.BytesIO(contenido))
                return "\n".join(p.text for p in doc.paragraphs)
        except Exception as exc:  # noqa: BLE001
            log.aviso(f"   · No se pudo extraer texto de {nombre}: {exc}")
        # Para .doc (binario antiguo) se recomienda convertirlo a .docx/.pdf antes.
        return ""

    # ───────────────────────────────────────────────────────────────────────────
    #  Etapa 4: búsqueda del artículo en proveedores + selección de la mejor opción
    # ───────────────────────────────────────────────────────────────────────────
    def buscar_mejor_opcion(self, necesidad: Necesidad, art_base: dict) -> Articulo:
        """
        Usa Gemini (con grounding de búsqueda web) para encontrar candidatos en los
        proveedores de confianza, y Claude Sonnet 4.6 para razonar y elegir la mejor
        opción (menor costo final, considerando logística si el proveedor es extranjero).
        """
        nombre = art_base.get("nombre", "")
        log.info(f"   · Buscando proveedores para: «{nombre}»…")

        prov_txt = "\n".join(f"- {n}: {u}" for n, u in
                             {**PROVEEDORES_NACIONALES, **PROVEEDORES_EXTRANJEROS}.items())

        # --- (a) Descubrimiento de candidatos con Gemini + Google Search grounding ---
        prompt_busqueda = f"""Busca en internet, PRIORIZANDO esta lista de proveedores de confianza,
el siguiente artículo NUEVO solicitado en un proceso de contratación:

  Nombre : {nombre}
  Marca  : {art_base.get('marca','(no especificada)')}
  Modelo : {art_base.get('modelo','(no especificado)')}
  Requisitos: {json.dumps(art_base.get('caracteristicas_solicitadas', []), ensure_ascii=False)}
  Especificaciones: {json.dumps(art_base.get('especificaciones_solicitadas', []), ensure_ascii=False)}

Proveedores de confianza (nacionales de Ecuador y extranjeros):
{prov_txt}

Si los documentos no fijan marca/modelo, propon un producto real que CUMPLA los requisitos.
La información del producto en la web y los requisitos deben coincidir en más del 50%
(idealmente 100%).

Devuelve ESTRICTAMENTE JSON:
{{
  "candidatos": [
    {{
      "proveedor": "<nombre>", "url": "<URL exacta del producto>",
      "es_extranjero": <true|false>, "precio_unitario": <número>, "moneda": "USD",
      "nombre": "<nombre real>", "marca": "<marca>", "modelo": "<modelo>",
      "imagen_url": "<URL de la foto del producto>",
      "imagenes_extra": ["<URL>", "..."],
      "resumen": "<descripción de 50 a 80 palabras tomada de la web del proveedor/fabricante>",
      "caracteristicas": ["<≥7 si es posible>"],
      "especificaciones_tecnicas": ["<≥10 si es posible>"],
      "especificaciones_electricas": ["..."],
      "incluye": ["<extras incluidos>"],
      "coincidencia": <0-100: % de coincidencia con los requisitos>
    }}
  ]
}}"""
        try:
            cfg = self._gtypes.GenerateContentConfig(
                tools=[self._gtypes.Tool(google_search=self._gtypes.GoogleSearch())]
            )
            r = self.gemini.models.generate_content(
                model=AI_MODEL_GEMINI,
                contents=[self._gtypes.Part.from_text(text=prompt_busqueda)],
                config=cfg,
            )
            candidatos = _json_desde_texto(r.text).get("candidatos", [])
        except Exception as exc:  # noqa: BLE001
            log.aviso(f"   · Grounding de Gemini no disponible ({exc}); se continúa sin candidatos.")
            candidatos = []

        # --- (b) Selección de la mejor opción con Claude Sonnet 4.6 -----------------
        prompt_seleccion = f"""Eres un comprador profesional. Elige la MEJOR opción de compra para el
artículo «{nombre}» entre los candidatos provistos, con estos criterios en orden:
1) Que cumpla EXACTAMENTE (o al menos lo más posible) los requisitos del pliego.
2) Que el COSTO FINAL sea el menor posible.

Dirección de entrega: «{necesidad.direccion}». Origen logístico de la empresa: {CIUDAD_BASE}, Ecuador.

Costos extra a estimar y SUMAR en "costo_extra" (NO en el precio unitario):
- Si el proveedor es EXTRANJERO: envío internacional + aduanas + logística hasta {CIUDAD_BASE}.
- Si la entrega es FUERA de {CIUDAD_BASE}: recargo de USD 86 a USD 155 según distancia/accesibilidad.
- Si el artículo requiere INSTALACIÓN: mano de obra de USD 60 a USD 80 por artículo según complejidad.
La mejor opción es la de menor (precio_unitario + costo_extra).

Candidatos (JSON):
{json.dumps(candidatos, ensure_ascii=False)}

Cantidad solicitada de este artículo: {art_base.get('cantidad', 1)}

Devuelve ESTRICTAMENTE JSON con la mejor opción y hasta 3 alternativas
(orden DECRECIENTE de cercanía a la mejor opción):
{{
  "nombre": "", "marca": "", "modelo": "",
  "proveedor": "", "url_mejor": "", "es_extranjero": <true|false>,
  "precio_unitario": <número>, "costo_extra": <número>, "moneda": "USD",
  "imagen_url": "", "imagenes_extra": ["..."],
  "resumen": "<50-80 palabras>",
  "caracteristicas": ["..."], "especificaciones_tecnicas": ["..."],
  "especificaciones_electricas": ["..."], "incluye": ["..."],
  "alternativas": ["<URL 2da mejor>", "<URL 3ra>", "<URL 4ta>"],
  "coincidencia": <0-100>
}}"""
        msg = self.claude.messages.create(
            model=AI_MODEL_CLAUDE,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt_seleccion}],
        )
        texto = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        sel = _json_desde_texto(texto)

        art = Articulo(
            nombre=sel.get("nombre") or art_base.get("nombre", ""),
            marca=sel.get("marca") or art_base.get("marca", ""),
            modelo=sel.get("modelo") or art_base.get("modelo", ""),
            resumen=sel.get("resumen", ""),
            caracteristicas=sel.get("caracteristicas", []),
            especificaciones_tecnicas=sel.get("especificaciones_tecnicas", []),
            especificaciones_electricas=sel.get("especificaciones_electricas", []),
            incluye=sel.get("incluye", []),
            cantidad=int(art_base.get("cantidad", 1) or 1),
            proveedor=sel.get("proveedor", ""),
            url_mejor=sel.get("url_mejor", ""),
            es_extranjero=bool(sel.get("es_extranjero", False)),
            precio_unitario=float(sel.get("precio_unitario", 0) or 0),
            costo_extra=float(sel.get("costo_extra", 0) or 0),
            moneda=sel.get("moneda", "USD"),
            imagen_url=sel.get("imagen_url", ""),
            imagenes_extra=sel.get("imagenes_extra", []),
            alternativas=[u for u in sel.get("alternativas", []) if u][:3],
            coincidencia=float(sel.get("coincidencia", 0) or 0),
        )
        if art.coincidencia and art.coincidencia < 50:
            log.aviso(f"   · Coincidencia con el pliego baja ({art.coincidencia:.0f}%).")
        log.ok(f"   · Mejor opción: {art.proveedor} → USD {art.precio_unitario:.2f} "
               f"(+{art.costo_extra:.2f} extra).")
        return art


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES DE IMÁGENES
# ═══════════════════════════════════════════════════════════════════════════════
def descargar_imagen(url: str) -> Optional[bytes]:
    """Descarga una imagen desde una URL; devuelve sus bytes o None si falla."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        if "image" in resp.headers.get("Content-Type", "") or len(resp.content) > 1024:
            return resp.content
    except Exception as exc:  # noqa: BLE001
        log.aviso(f"   · No se pudo descargar la imagen ({url[:60]}…): {exc}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  5)  GENERACIÓN DE LA FICHA TÉCNICA  (.docx)
#      Se parte de la plantilla para HEREDAR encabezado, pie, márgenes y fuente.
# ═══════════════════════════════════════════════════════════════════════════════
class GeneradorFicha:
    """Construye la ficha técnica .docx a partir de la plantilla de IMPOCRUZ."""

    FUENTE = "Century Gothic"   # fuente real detectada en la plantilla
    TAM_CUERPO = Pt(12)
    TAM_TITULO = Pt(12)

    def __init__(self, plantilla: Path):
        self.plantilla = plantilla

    # -- helpers de bajo nivel --------------------------------------------------
    def _vaciar_cuerpo(self, doc: Document) -> None:
        """Elimina todo el contenido del cuerpo pero conserva el <sectPr> final
        (que enlaza encabezado y pie de página de la plantilla)."""
        cuerpo = doc.element.body
        for hijo in list(cuerpo):
            if hijo.tag.endswith("}sectPr"):
                continue
            cuerpo.remove(hijo)

    def _fijar_fuente(self, run, negrita=False, tam=None, color=None, fuente=None) -> None:
        run.font.name = fuente or self.FUENTE
        run.font.size = tam or self.TAM_CUERPO
        run.font.bold = negrita
        if color is not None:
            run.font.color.rgb = color

    def _parrafo(self, doc, texto="", negrita=False, centrado=False, tam=None,
                 color=None, fuente=None):
        p = doc.add_paragraph()
        if centrado:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if texto:
            self._fijar_fuente(p.add_run(texto), negrita, tam, color, fuente)
        return p

    def _vinetas(self, doc, items: List[str]) -> None:
        for it in items:
            if not str(it).strip():
                continue
            p = doc.add_paragraph(style="List Bullet")
            self._fijar_fuente(p.add_run(str(it)))

    def _imagen_centrada(self, doc, datos: bytes, ancho=Inches(2.6)) -> None:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        try:
            p.add_run().add_picture(io.BytesIO(datos), width=ancho)
        except Exception as exc:  # noqa: BLE001
            log.aviso(f"   · No se pudo insertar una imagen en la ficha: {exc}")

    # -- construcción de la ficha ----------------------------------------------
    def construir(self, necesidad: Necesidad, ruta_salida: Path) -> Path:
        log.info("   · Construyendo ficha técnica .docx desde la plantilla…")
        doc = Document(str(self.plantilla))
        self._vaciar_cuerpo(doc)

        # Fuente por defecto del documento = Century Gothic 12.
        normal = doc.styles["Normal"].font
        normal.name = self.FUENTE
        normal.size = self.TAM_CUERPO

        # CASO ESPECIAL (etapa 3a): se superó el límite de artículos.
        if necesidad.supera_limite:
            self._parrafo(
                doc,
                "La cantidad de artículos supera el límite permitido de 10 artículos de compra",
                negrita=True, centrado=True,
                tam=Pt(14), color=RGBColor(0xFF, 0x00, 0x00), fuente="Arial",
            )
            doc.save(str(ruta_salida))
            log.ok(f"   · Ficha con aviso de límite generada: {ruta_salida.name}")
            return ruta_salida

        # CASO NORMAL: un bloque por cada artículo.
        for idx, art in enumerate(necesidad.articulos):
            # Título en negrita = nombre/marca/modelo del artículo.
            self._parrafo(doc, art.titulo, negrita=True, centrado=True, tam=self.TAM_TITULO)

            # Imagen del producto, justo debajo del título.
            img = descargar_imagen(art.imagen_url)
            if img:
                self._imagen_centrada(doc, img)

            # Resumen (50–80 palabras).
            if art.resumen:
                self._parrafo(doc, art.resumen)

            # Características generales.
            if art.caracteristicas:
                self._parrafo(doc, "Características:", negrita=True)
                self._vinetas(doc, art.caracteristicas)

            # Especificaciones técnicas.
            if art.especificaciones_tecnicas:
                self._parrafo(doc, "Especificaciones técnicas:", negrita=True)
                self._vinetas(doc, art.especificaciones_tecnicas)

            # Especificaciones eléctricas.
            if art.especificaciones_electricas:
                self._parrafo(doc, "Especificaciones eléctricas:", negrita=True)
                self._vinetas(doc, art.especificaciones_electricas)

            # Lo que incluye / extras.
            if art.incluye:
                self._parrafo(doc, "Incluye:", negrita=True)
                self._vinetas(doc, art.incluye)

            # Imágenes adicionales del mismo producto al final del bloque.
            for url in art.imagenes_extra[:3]:
                extra = descargar_imagen(url)
                if extra:
                    self._imagen_centrada(doc, extra, ancho=Inches(2.0))

            # Separación entre artículos (salto de página salvo en el último).
            if idx < len(necesidad.articulos) - 1:
                doc.add_page_break()

        doc.save(str(ruta_salida))
        log.ok(f"   · Ficha técnica generada: {ruta_salida.name}")
        return ruta_salida


# ═══════════════════════════════════════════════════════════════════════════════
#  7)  GENERACIÓN DE LA PROFORMA  (.xlsm)  preservando macros y formato
# ═══════════════════════════════════════════════════════════════════════════════
class GeneradorProforma:
    """Rellena la plantilla .xlsm modificando SOLO las celdas indicadas."""

    def __init__(self, plantilla: Path):
        self.plantilla = plantilla

    # -- helper: escribir respetando celdas combinadas --------------------------
    @staticmethod
    def _escribir(ws, coord: str, valor) -> None:
        """Escribe en 'coord'; si está dentro de una celda combinada, escribe en su ancla."""
        fila, col = coordinate_to_tuple(coord)
        for rango in ws.merged_cells.ranges:
            min_c, min_f, max_c, max_f = range_boundaries(str(rango))
            if min_f <= fila <= max_f and min_c <= col <= max_c:
                ws.cell(row=min_f, column=min_c).value = valor
                return
        ws[coord].value = valor

    @staticmethod
    def _numero_proforma(id_necesidad: str) -> str:
        """Formato 00100100### : 8 dígitos fijos + ID (rellenado a 3, o últimos 11 si es mayor)."""
        base = "00100100"
        id_str = str(id_necesidad)
        if len(id_str) <= 3:
            return base + id_str.zfill(3)
        return (base + id_str)[-11:]   # si el ID supera 3 dígitos, se usan los últimos 11

    @staticmethod
    def _anclar_imagen(ws, datos: bytes, coord: str, px=90) -> None:
        """Ancla una miniatura del producto en la celda indicada."""
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(datos); tmp.close()
            img = XLImage(tmp.name)
            img.width = img.height = px
            ws.add_image(img, coord)
        except Exception as exc:  # noqa: BLE001
            log.aviso(f"   · No se pudo anclar imagen en {coord}: {exc}")

    def construir(self, necesidad: Necesidad, ruta_salida: Path) -> Path:
        log.info("   · Construyendo proforma .xlsm desde la plantilla (con macros)…")
        wb = load_workbook(str(self.plantilla), keep_vba=True, data_only=False)
        cot = wb[HOJA_COTIZACION]
        cos = wb[HOJA_COSTOS]

        # ── HOJA "Cotización " ─────────────────────────────────────────────────
        self._escribir(cot, CELDAS_COTIZACION["entidad"], necesidad.entidad.upper())
        self._escribir(cot, CELDAS_COTIZACION["codigo_5_17"], necesidad.codigo[4:17])  # chars 5..17
        self._escribir(cot, CELDAS_COTIZACION["direccion"], necesidad.direccion)
        self._escribir(cot, CELDAS_COTIZACION["contacto"], self._formato_contacto(necesidad.contacto))
        self._escribir(cot, CELDAS_COTIZACION["codigo"], necesidad.codigo)
        self._escribir(cot, CELDAS_COTIZACION["num_proforma"], self._numero_proforma(necesidad.id))
        self._escribir(cot, CELDAS_COTIZACION["fecha"], datetime.date.today().strftime("%d/%m/%Y"))

        # Productos (nombre/marca/modelo + imagen en C16…, cantidad en G16…).
        for k, art in enumerate(necesidad.articulos):
            fila = COT_PRIMERA_FILA_PROD + k
            if fila > COT_ULTIMA_FILA_PROD:
                break
            self._escribir(cot, f"{COT_PRODUCTO_COL_NOMBRE}{fila}", art.titulo)
            self._escribir(cot, f"{COT_PRODUCTO_COL_CANT}{fila}", art.cantidad)
            img = descargar_imagen(art.imagen_url)
            if img:
                self._anclar_imagen(cot, img, f"{COT_PRODUCTO_COL_NOMBRE}{fila}")

        # Borrar (limpiar) las celdas de producto sobrantes en Cotización.
        for fila in range(COT_PRIMERA_FILA_PROD + len(necesidad.articulos),
                           COT_ULTIMA_FILA_PROD + 1):
            self._escribir(cot, f"{COT_PRODUCTO_COL_NOMBRE}{fila}", None)
            self._escribir(cot, f"{COT_PRODUCTO_COL_CANT}{fila}", None)

        # ── HOJA "Costos" ──────────────────────────────────────────────────────
        self._escribir(cos, COSTOS_URL_CONTRATANTE, necesidad.entidad_url)

        for k, art in enumerate(necesidad.articulos):
            fila = COSTOS_PRIMERA_FILA + k          # desfase: Costos fila = Cotización fila - 1
            if fila > COSTOS_ULTIMA_FILA:
                break
            self._escribir(cos, f"{COSTOS_COL_URL}{fila}", art.url_mejor)
            self._escribir(cos, f"{COSTOS_COL_VALOR_REAL}{fila}", art.precio_unitario)
            self._escribir(cos, f"{COSTOS_COL_EXTRAS}{fila}", art.costo_extra)

            # Alternativas (orden decreciente de cercanía) en la columna J.
            #   Encabezados reales en la plantilla: prod1=J14, prod2=J18, prod3=J22, …
            #   por lo que los 3 slots del producto k (0-index) son:
            #       prod1 → J15,J16,J17   prod2 → J19,J20,J21   prod3 → J23,J24,J25
            #   El requerimiento detalla explícitamente los productos 1, 2 y 3;
            #   aquí se generaliza con la fórmula primera_alt = 15 + 4*k (hasta 10).
            primera_alt = 15 + 4 * k
            for j, url_alt in enumerate(art.alternativas[:3]):
                self._escribir(cos, f"J{primera_alt + j}", url_alt)

        # Borrar (limpiar) las celdas de producto sobrantes en Costos.
        for fila in range(COSTOS_PRIMERA_FILA + len(necesidad.articulos),
                           COSTOS_ULTIMA_FILA + 1):
            self._escribir(cos, f"{COSTOS_COL_URL}{fila}", None)
            self._escribir(cos, f"{COSTOS_COL_VALOR_REAL}{fila}", None)
            self._escribir(cos, f"{COSTOS_COL_EXTRAS}{fila}", None)

        wb.save(str(ruta_salida))
        log.ok(f"   · Proforma generada: {ruta_salida.name}")
        return ruta_salida

    @staticmethod
    def _formato_contacto(contacto: str) -> str:
        """Deja el contacto como «Nombre — correo/teléfono» de forma compacta."""
        if not contacto:
            return ""
        # Conserva nombre + (correo electrónico o número de teléfono) si vienen mezclados.
        correo = re.search(r"[\w.\-]+@[\w.\-]+\.\w+", contacto)
        tel = re.search(r"(?:\+?\d[\s\-]?){7,}", contacto)
        # El "nombre" se toma como el texto previo al correo/teléfono.
        nombre = contacto
        for m in (correo, tel):
            if m:
                nombre = contacto[:m.start()].strip(" ,;-")
                break
        dato = (correo.group(0) if correo else (tel.group(0).strip() if tel else "")).strip()
        return f"{nombre} — {dato}".strip(" —") if dato else contacto


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDACIÓN DE CONFIGURACIÓN
#  Comprueba que estén los datos mínimos y muestra un mensaje claro (en vez de un
#  error críptico de las librerías) si falta algo. Evita, por ejemplo, que la
#  librería de Google intente abrir una ruta de credenciales vacía ("").
# ═══════════════════════════════════════════════════════════════════════════════
def validar_configuracion() -> None:
    problemas = []

    # Credenciales de Google Cloud / Vertex AI (archivo .json de cuenta de servicio).
    if not GEMINI_CREDENTIALS_PATH:
        problemas.append(
            "Falta la ruta de las credenciales (GEMINI_CREDENTIALS): no se indicó "
            "ningún archivo .json de cuenta de servicio de Google Cloud."
        )
    elif not Path(GEMINI_CREDENTIALS_PATH).is_file():
        problemas.append(
            f"No se encontró el archivo de credenciales en la ruta indicada: "
            f"«{GEMINI_CREDENTIALS_PATH}». Revisa que la ruta sea correcta y que el "
            f".json exista."
        )

    # Nombre del bucket.
    if not BUCKET_NAME:
        problemas.append("Falta el nombre del bucket de Google Cloud (BUCKET_NAME).")

    # Datos mínimos de la base de datos.
    if not MYSQL_CONFIG.get("host"):
        problemas.append("Falta el host de la base de datos (DB_HOST).")
    if not MYSQL_CONFIG.get("user"):
        problemas.append("Falta el usuario de la base de datos (DB_USER).")

    if problemas:
        log.error("No se puede iniciar: la configuración está incompleta.")
        for p in problemas:
            log.error(f"   - {p}")
        log.info("Soluciónalo de UNA de estas formas:")
        log.info("   1) Rellena el bloque CONFIG_LOCAL al inicio de este script, o")
        log.info("   2) define esas variables de entorno en el sistema, o")
        log.info("   3) provéelas mediante el objeto Global de tu plataforma.")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  ORQUESTADOR PRINCIPAL  (encadena las 9 etapas)
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    log.etapa("INICIO DEL PROCESO DE GENERACIÓN DE FICHAS Y PROFORMAS")

    # Validación de configuración (credenciales, bucket, base de datos).
    validar_configuracion()

    # Validación rápida de plantillas.
    for plantilla in (TEMPLATE_DOCX, TEMPLATE_XLSX):
        if not plantilla.exists():
            log.error(f"No se encuentra la plantilla: {plantilla}")
            sys.exit(1)

    # Inicialización de servicios.
    db = BaseDatos(MYSQL_CONFIG)
    bucket = Bucket(GEMINI_CREDENTIALS_PATH, BUCKET_NAME)
    ia = MotoresIA()
    gen_ficha = GeneradorFicha(TEMPLATE_DOCX)
    gen_proforma = GeneradorProforma(TEMPLATE_XLSX)

    # Carpeta local temporal para los entregables antes de subirlos.
    salida_dir = Path(tempfile.mkdtemp(prefix="proformas_"))
    log.info(f"Directorio de trabajo temporal: {salida_dir}")

    # ── Etapa 1: data_table_1 ──────────────────────────────────────────────────
    log.etapa("ETAPA 1 · Lectura de necesidades en «en generacion»")
    data_table_1 = db.obtener_necesidades()
    if not data_table_1:
        log.aviso("No hay líneas para procesar. Fin del proceso.")
        return

    # Procesamiento línea por línea (cada necesidad es independiente).
    for n, necesidad in enumerate(data_table_1, start=1):
        log.etapa(f"NECESIDAD {n}/{len(data_table_1)} · {necesidad.codigo} (ID {necesidad.id})")
        try:
            # ── Etapa 2: documentos del bucket ─────────────────────────────────
            log.info("ETAPA 2 · Descargando documentos de contratación del bucket")
            blobs = bucket.listar_documentos(necesidad.codigo)
            if not blobs:
                log.aviso("   · Sin documentos en el bucket; se omite esta necesidad.")
                continue

            # ── Etapa 3: análisis con IA y control del límite de artículos ─────
            log.info("ETAPA 3 · Análisis de documentos con IA")
            analisis = ia.analizar_documentos(necesidad, bucket, blobs)
            necesidad.num_distintos = int(analisis.get("num_distintos", 0))

            if necesidad.num_distintos > LIMITE_ARTICULOS:
                # 3a-d) Ficha con aviso en rojo, sin proforma, etapa → finalizada.
                log.aviso(f"   · {necesidad.num_distintos} artículos (> {LIMITE_ARTICULOS}). "
                          "Se genera SOLO la ficha con aviso y se finaliza.")
                necesidad.supera_limite = True
                ruta_ficha = salida_dir / f"{necesidad.codigo}_Ficha_técnica_{necesidad.id}.docx"
                gen_ficha.construir(necesidad, ruta_ficha)
                bucket.subir(ruta_ficha, BUCKET_FOLDER_FICHAS, ruta_ficha.name)  # etapa 6
                db.finalizar(necesidad.codigo)                                # etapa 3c/9
                continue

            # ── Etapa 4: búsqueda del mejor proveedor por artículo ─────────────
            log.info("ETAPA 4 · Búsqueda de la mejor opción en proveedores")
            necesidad.articulos = [
                ia.buscar_mejor_opcion(necesidad, art)
                for art in analisis.get("articulos", [])
            ]
            if not necesidad.articulos:
                log.aviso("   · La IA no devolvió artículos; se omite esta necesidad.")
                continue

            # ── Etapa 5: ficha técnica .docx ───────────────────────────────────
            log.info("ETAPA 5 · Generación de la ficha técnica (.docx)")
            ruta_ficha = salida_dir / f"{necesidad.codigo}_Ficha_técnica_{necesidad.id}.docx"
            gen_ficha.construir(necesidad, ruta_ficha)

            # ── Etapa 6: subir la ficha al bucket ──────────────────────────────
            log.info("ETAPA 6 · Subida de la ficha al bucket")
            bucket.subir(ruta_ficha, BUCKET_FOLDER_FICHAS, ruta_ficha.name)

            # ── Etapa 7: proforma .xlsm ────────────────────────────────────────
            log.info("ETAPA 7 · Generación de la proforma (.xlsm)")
            ruta_prof = salida_dir / f"{necesidad.codigo}_Proforma_{necesidad.id}.xlsm"
            gen_proforma.construir(necesidad, ruta_prof)

            # ── Etapa 8: subir la proforma al bucket ───────────────────────────
            log.info("ETAPA 8 · Subida de la proforma al bucket")
            bucket.subir(ruta_prof, BUCKET_FOLDER_PROFORMAS, ruta_prof.name)

            # ── Etapa 9: actualizar etapa a «finalizada» ───────────────────────
            log.info("ETAPA 9 · Actualización de etapa en la base de datos")
            db.finalizar(necesidad.codigo)

            log.ok(f"Necesidad «{necesidad.codigo}» completada correctamente.")

        except Exception as exc:  # noqa: BLE001
            # Una falla en una necesidad NO detiene el lote completo.
            log.error(f"Error procesando «{necesidad.codigo}»: {exc}")
            traceback.print_exc()
            continue

    log.etapa("PROCESO FINALIZADO")


if __name__ == "__main__":
    main()
