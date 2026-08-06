import mysql.connector
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import platform
import time
import tempfile
import os
import sys
import subprocess
import unicodedata
from datetime import datetime, date, time as dtime
from pathlib import Path

#raíz del proyecto al path de Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from Config import Global

# ---------------------------------------------------------------------------
# Configuración de la purga de necesidades vencidas
# ---------------------------------------------------------------------------
DB_PURGA = "gestorex"                     # Base de datos donde vive la tabla infimas
TABLA_PURGA = "infimas"
TZ_SESION_MYSQL = "-05:00"                # Hora de Ecuador (America/Guayaquil)
TAM_LOTE = 500                            # Valores por sentencia IN (...)
PROFUNDIDAD_MAX_CASCADA = 6               # Niveles de tablas hijas a recorrer

# Etapas que NUNCA se borran (comparación sin acentos ni mayúsculas)
ETAPAS_PROTEGIDAS = {"en generacion", "finalizada"}

FORMATOS_CON_HORA = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
)
FORMATOS_SOLO_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def get_driver():
    chrome_options = Options()

    # Configuración común
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,720")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    if platform.system() == "Linux":
        # Configuración para Linux (Render/GitHub Actions)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-software-rasterizer")

        temp_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={temp_dir}")

        service = Service(
            "/usr/bin/chromedriver",
            service_args=['--verbose', '--log-path=/tmp/chromedriver.log']
        )

        driver = webdriver.Chrome(service=service, options=chrome_options)

    else:
        # Configuración para Windows (desarrollo local)
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        # Opcional: minimizar ventana en Windows
        try:
            driver.minimize_window()
        except:
            pass

    driver.set_page_load_timeout(180)
    return driver


def main():
    url = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/NCO/FrmNCOListado.cpe"

    print("\n[INFO] Iniciando driver...")
    driver = get_driver()

    html_content = ""
    try:
        print("Cargando página...")
        driver.get(url)

        # Esperamos que la tabla exista (al menos una fila)
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
        )
        print("Tabla inicial detectada.")

        # Intentamos activar el dropdown de cantidad de registros
        print("Buscando dropdown de cantidad de registros...")
        dropdown_found = False
        try:
            # Selectores más robustos: por name, o por clase común en DataTables
            select = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        'select[name="table_id_length"], select[name$="_length"], .dataTables_length select',
                    )
                )
            )
            print("Dropdown encontrado → intentando cambiar a 100...")

            driver.execute_script(
                """
                var sel = arguments[0];
                if (sel) {
                    sel.value = '100';
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                }
            """,
                select,
            )

            print("→ Ejecutado cambio a 100 registros.")

            # Esperamos que la tabla se recargue con más filas
            WebDriverWait(driver, 30).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "tbody tr")) > 20
            )
            print("Tabla actualizada con más filas → éxito.")

            dropdown_found = True

        except Exception as e:
            print(f"No se pudo cambiar la cantidad de registros: {e}")
            print("Continuando con el valor por defecto (~10 filas).")

        time.sleep(3)  # margen para render completo

        html_content = driver.page_source

        temp_file = os.path.join(tempfile.gettempdir(), "debug_pagina_final.html")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML guardado en: {temp_file}")

    except Exception as e:
        print(f"Error general durante carga: {e}")
        try:
            driver.save_screenshot("error_carga.png")
            print("Screenshot guardado: error_carga.png")
        except:
            pass
        if "driver" in locals():
            html_content = driver.page_source

    finally:
        driver.quit()

    data = extract_table_data(html_content, url)

    if data:
        print(f"\nExtraídos {len(data)} registros.")
        save_to_db(data)
    else:
        print(
            "No se extrajeron datos. Abre debug_pagina_final.html y verifica <tbody>."
        )

    # Limpieza de necesidades cuya fecha límite de proformas ya venció.
    # Se ejecuta siempre, haya o no registros nuevos.
    eliminar_proformas_vencidas()

    if not data:
        sys.exit(1)


def extract_table_data(html_content, base_url):
    data = []
    if not html_content:
        return data

    soup = BeautifulSoup(html_content, "html.parser")

    target_text = "Código Necesidad de Contratación"
    table = None
    for tbl in soup.find_all("table"):
        if tbl.find("th", string=lambda s: s and target_text in s.strip()):
            table = tbl
            print("Tabla localizada.")
            break

    if not table:
        print("No se encontró tabla con el encabezado.")
        return data

    headers = [th.get_text(strip=True) for th in table.find_all("th")]

    column_mapping = {
        "Tipo de Necesidad": "tipo_necesidad",
        "Código Necesidad de Contratación": "codigo_necesidad",
        "Fecha de Publicación": "fecha_publicacion",
        "Provincia - Cantón": "provincia_canton",
        "Descripción del Objeto de compra": "descripcion_objeto_compra",
        "Estado de la Necesidad": "estado_necesidad",
        "Fecha límite para la entrega de proformas": "fecha_limite_proformas",
        "Entidad Contratante": "entidad_contratante",
        "Dirección de Entrega": "direccion_entrega",
        "Contacto": "contacto",
    }

    normalized_headers = [
        column_mapping.get(
            h.strip(), h.strip().replace(" ", "_").replace("-", "_").lower()
        )
        for h in headers
    ]

    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else []

    print(f"Filas detectadas: {len(rows)}")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        record = {}
        has_data = False

        for i, cell in enumerate(cells):
            if i >= len(normalized_headers):
                break
            header = normalized_headers[i]
            text = cell.get_text(strip=True)

            a_tag = cell.find("a", href=True)
            link = urljoin(base_url, a_tag["href"]) if a_tag else None

            if link:
                if "codigo_necesidad" in header:
                    record[header] = link
                    record["codigo_texto"] = text
                    has_data = True
                elif "entidad_contratante" in header:
                    record["entidad_contratante_url"] = link  # URL capturada aquí
                    record[header] = text
                    has_data = True
            else:
                record[header] = text
                if text:
                    has_data = True

        if has_data and record.get("codigo_necesidad"):
            data.append(record)

    return data


def save_to_db(data):
    try:
        conn = mysql.connector.connect(
            host=Global.DB_HOST,
            user=Global.DB_USER,
            password=Global.DB_PASSWORD,
            database=Global.DATABASE,
            connect_timeout=35,
        )
        cur = conn.cursor()

        # Códigos de necesidad (NIC) ya registrados en la BD, para filtrar duplicados.
        cur.execute("SELECT codigo_necesidad FROM infimas")
        codigos_existentes = {row[0] for row in cur.fetchall() if row[0] is not None}
        print(f"Códigos de necesidad ya registrados en BD: {len(codigos_existentes)}")

        inserted = 0
        omitidos = 0
        for registro in data:
            # NIC tal como se guarda en la columna codigo_necesidad (texto visible),
            # no la URL: si la celda trae enlace el NIC está en 'codigo_texto', y si
            # no trae enlace queda en 'codigo_necesidad'.
            nic = registro.get("codigo_texto") or registro.get("codigo_necesidad")

            # Solo subir los que NO están en la BD (ni se hayan insertado en este lote).
            if nic in codigos_existentes:
                omitidos += 1
                continue

            params = (
                registro.get("tipo_necesidad", None),
                registro.get("codigo_necesidad") or registro.get("codigo_texto", None),
                registro.get("fecha_publicacion", None),
                registro.get("provincia_canton", None),
                registro.get("descripcion_objeto_compra", None),
                registro.get("estado_necesidad", None),
                registro.get("fecha_limite_proformas", None),
                registro.get("entidad_contratante", None),
                registro.get("entidad_contratante_url", None),
                registro.get("direccion_entrega", None),
                registro.get("contacto", None),
            )

            try:
                cur.callproc("upsert_infimas", params)
                inserted += 1
                codigos_existentes.add(nic)  # evita duplicados dentro del mismo lote
            except mysql.connector.Error as err:
                print(
                    f"Error en upsert_infimas para {nic or 'N/A'}: {err}"
                )

        conn.commit()
        print(
            f"Registros nuevos insertados: {inserted}. "
            f"Omitidos por ya existir en BD: {omitidos}."
        )

    except Exception as e:
        print(f"Error en BD: {e}")
    finally:
        if "cur" in locals():
            cur.close()
        if "conn" in locals() and conn.is_connected():
            conn.close()


# ---------------------------------------------------------------------------
# Utilitarios de la purga
# ---------------------------------------------------------------------------
def _normalizar_texto(valor):
    """Minúsculas, sin acentos y sin espacios sobrantes."""
    if valor is None:
        return ""
    s = unicodedata.normalize("NFKD", str(valor))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def _parsear_fecha_limite(valor):
    """Convierte el valor de fecha_limite_proformas en datetime.

    Acepta DATETIME/DATE nativos de MySQL y también texto en los formatos
    más comunes del portal. Si el valor no trae hora, se asume 23:59:59
    para no borrar antes de tiempo. Devuelve None si no se puede interpretar.
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime.combine(valor, dtime(23, 59, 59))

    texto = str(valor).strip().replace("T", " ")
    if not texto:
        return None

    for fmt in FORMATOS_CON_HORA:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue

    for fmt in FORMATOS_SOLO_FECHA:
        try:
            return datetime.combine(
                datetime.strptime(texto, fmt).date(), dtime(23, 59, 59)
            )
        except ValueError:
            continue

    return None


def _lotes(valores, tam=TAM_LOTE):
    """Parte una lista en bloques para no reventar la sentencia IN (...)."""
    valores = list(valores)
    for i in range(0, len(valores), tam):
        yield valores[i:i + tam]


def _valores_referenciados(cur, tabla, col_destino, col_filtro, valores):
    """Devuelve los valores distintos de `col_destino` en las filas de `tabla`
    cuya `col_filtro` esté dentro de `valores`."""
    encontrados = set()
    for lote in _lotes(valores):
        marcadores = ",".join(["%s"] * len(lote))
        cur.execute(
            f"SELECT DISTINCT `{col_destino}` FROM `{tabla}` "
            f"WHERE `{col_filtro}` IN ({marcadores})",
            lote,
        )
        encontrados.update(r[0] for r in cur.fetchall() if r[0] is not None)
    return list(encontrados)


def _contar_por_valores(cur, tabla, columna, valores):
    total = 0
    for lote in _lotes(valores):
        marcadores = ",".join(["%s"] * len(lote))
        cur.execute(
            f"SELECT COUNT(*) FROM `{tabla}` WHERE `{columna}` IN ({marcadores})",
            lote,
        )
        total += cur.fetchone()[0] or 0
    return total


def _borrar_por_valores(cur, tabla, columna, valores):
    total = 0
    for lote in _lotes(valores):
        marcadores = ",".join(["%s"] * len(lote))
        cur.execute(
            f"DELETE FROM `{tabla}` WHERE `{columna}` IN ({marcadores})",
            lote,
        )
        if cur.rowcount and cur.rowcount > 0:
            total += cur.rowcount
    return total


def _mapa_hijas(cur, esquema):
    """Construye {tabla_padre: [(tabla_hija, col_hija, col_referenciada, regla), ...]}
    leyendo las claves foráneas declaradas en el esquema.

    Las FK compuestas (más de una columna) se descartan con aviso, y las que ya
    tienen ON DELETE CASCADE se ignoran porque MySQL las resuelve solo.
    """
    cur.execute(
        """
        SELECT k.CONSTRAINT_NAME, k.TABLE_NAME, k.COLUMN_NAME,
               k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME,
               k.ORDINAL_POSITION, r.DELETE_RULE
        FROM information_schema.KEY_COLUMN_USAGE k
        JOIN information_schema.REFERENTIAL_CONSTRAINTS r
          ON r.CONSTRAINT_SCHEMA = k.CONSTRAINT_SCHEMA
         AND r.CONSTRAINT_NAME = k.CONSTRAINT_NAME
        WHERE k.TABLE_SCHEMA = %s
          AND k.REFERENCED_TABLE_SCHEMA = %s
          AND k.REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY k.TABLE_NAME, k.CONSTRAINT_NAME, k.ORDINAL_POSITION
        """,
        (esquema, esquema),
    )
    filas = cur.fetchall()

    # Detectar constraints compuestas para excluirlas.
    conteo = {}
    for f in filas:
        conteo[(f[1], f[0])] = conteo.get((f[1], f[0]), 0) + 1

    mapa = {}
    compuestas = set()
    for nombre, t_hija, c_hija, t_padre, c_padre, _pos, regla in filas:
        if conteo[(t_hija, nombre)] > 1:
            compuestas.add(f"{t_hija}.{nombre}")
            continue
        if (regla or "").upper() == "CASCADE":
            continue  # el motor ya la resuelve
        mapa.setdefault(t_padre, []).append((t_hija, c_hija, c_padre, regla))

    if compuestas:
        print(
            "[PURGA] Aviso: FK compuestas no soportadas por la cascada manual → "
            + ", ".join(sorted(compuestas))
        )

    return mapa


def _eliminar_descendientes(cur, tabla, columna, valores, mapa, ruta, nivel, reporte):
    """Elimina recursivamente las filas de las tablas hijas que dependen de
    `tabla`.`columna` IN `valores`. NO borra las filas de `tabla`.
    """
    if not valores or nivel > PROFUNDIDAD_MAX_CASCADA:
        return

    for t_hija, c_hija, c_padre, _regla in mapa.get(tabla, []):
        if t_hija in ruta:
            continue  # corta ciclos (incluye auto-referencias)

        # Valores de la columna que la hija realmente referencia.
        if c_padre.lower() == columna.lower():
            vals_ref = valores
        else:
            vals_ref = _valores_referenciados(cur, tabla, c_padre, columna, valores)

        if not vals_ref:
            continue

        # Primero los nietos, después la hija.
        _eliminar_descendientes(
            cur, t_hija, c_hija, vals_ref, mapa,
            ruta + (t_hija,), nivel + 1, reporte,
        )

        borradas = _borrar_por_valores(cur, t_hija, c_hija, vals_ref)
        if borradas:
            reporte[t_hija] = reporte.get(t_hija, 0) + borradas


def eliminar_proformas_vencidas(simular=False, cascada=True):
    """Borra de gestorex.infimas las filas cuya fecha_limite_proformas ya pasó.

    - Compara con precisión de hora:minuto:segundo contra la hora actual.
    - NO toca las filas cuya columna 'etapa' sea 'en generacion' o 'finalizada'
      (comparación sin acentos ni distinción de mayúsculas).
    - Con cascada=True elimina antes las filas dependientes de cualquier tabla
      hija (y nieta) detectada por claves foráneas, para no chocar con las
      restricciones de integridad referencial.
    - Con simular=True solo reporta, no elimina.

    Todo el borrado ocurre dentro de una sola transacción: si algo falla,
    se revierte completo.

    Devuelve la cantidad de filas eliminadas de infimas.
    """
    conn = None
    cur = None
    try:
        conn = mysql.connector.connect(
            host=Global.DB_HOST,
            user=Global.DB_USER,
            password=Global.DB_PASSWORD,
            database=DB_PURGA,
            connect_timeout=35,
        )
        conn.autocommit = False
        cur = conn.cursor()

        # Fijamos la zona horaria de la sesión a la de Ecuador para que NOW()
        # coincida con las fechas publicadas por el portal, sin importar si el
        # script corre en Render/Cloud Run (UTC) o en local.
        try:
            cur.execute("SET time_zone = %s", (TZ_SESION_MYSQL,))
        except mysql.connector.Error as err:
            print(f"[PURGA] Aviso: no se pudo fijar la zona horaria ({err}).")

        cur.execute("SELECT NOW()")
        ahora = cur.fetchone()[0]
        print(
            f"\n[PURGA] Hora de referencia: {ahora:%Y-%m-%d %H:%M:%S} "
            f"(UTC{TZ_SESION_MYSQL})"
        )

        # Metadatos de la tabla: identificador único y columnas disponibles.
        cur.execute(
            """
            SELECT COLUMN_NAME, COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """,
            (DB_PURGA, TABLA_PURGA),
        )
        columnas = cur.fetchall()

        if not columnas:
            print(f"[PURGA] No se encontró la tabla {DB_PURGA}.{TABLA_PURGA}.")
            return 0

        nombres = {c[0].lower() for c in columnas}

        if "fecha_limite_proformas" not in nombres:
            print("[PURGA] La tabla no tiene la columna 'fecha_limite_proformas'.")
            return 0

        claves = [c[0] for c in columnas if c[1] == "PRI"]
        if len(claves) == 1:
            col_id = claves[0]
        elif "codigo_necesidad" in nombres:
            col_id = "codigo_necesidad"
            print("[PURGA] Sin PK simple → se usa 'codigo_necesidad' como identificador.")
        else:
            print("[PURGA] No hay identificador único utilizable. Purga cancelada.")
            return 0

        tiene_etapa = "etapa" in nombres
        if not tiene_etapa:
            print("[PURGA] Aviso: no existe la columna 'etapa'; no se aplica esa exclusión.")

        campos = f"`{col_id}`, `fecha_limite_proformas`"
        if tiene_etapa:
            campos += ", `etapa`"

        cur.execute(f"SELECT {campos} FROM `{TABLA_PURGA}`")
        filas = cur.fetchall()

        a_borrar = []
        protegidas = 0
        sin_fecha = 0

        for fila in filas:
            ident = fila[0]
            limite_raw = fila[1]
            etapa = fila[2] if tiene_etapa else None

            # Etapas protegidas: no se tocan bajo ninguna circunstancia.
            if _normalizar_texto(etapa) in ETAPAS_PROTEGIDAS:
                protegidas += 1
                continue

            limite = _parsear_fecha_limite(limite_raw)
            if limite is None:
                sin_fecha += 1
                continue

            # Solo si la fecha límite ya fue alcanzada y superada.
            if limite <= ahora:
                a_borrar.append(ident)

        print(
            f"[PURGA] Revisadas: {len(filas)} | protegidas por etapa: {protegidas} | "
            f"sin fecha válida: {sin_fecha} | vencidas: {len(a_borrar)}"
        )

        if not a_borrar:
            print("[PURGA] No hay filas vencidas para eliminar.")
            return 0

        # Mapa de dependencias (tablas hijas por FK).
        mapa = _mapa_hijas(cur, DB_PURGA) if cascada else {}
        hijas_directas = mapa.get(TABLA_PURGA, [])
        if cascada:
            if hijas_directas:
                print(
                    "[PURGA] Tablas hijas detectadas: "
                    + ", ".join(sorted({h[0] for h in hijas_directas}))
                )
            else:
                print("[PURGA] Sin tablas hijas pendientes (o ya usan ON DELETE CASCADE).")

        if simular:
            for t_hija, c_hija, c_padre, _r in hijas_directas:
                if c_padre.lower() == col_id.lower():
                    vals = a_borrar
                else:
                    vals = _valores_referenciados(
                        cur, TABLA_PURGA, c_padre, col_id, a_borrar
                    )
                if vals:
                    n = _contar_por_valores(cur, t_hija, c_hija, vals)
                    print(f"[PURGA]   → {t_hija}: {n} filas dependientes (nivel 1)")
            print("[PURGA] Modo simulación: no se eliminó ninguna fila.")
            conn.rollback()
            return 0

        # Borrado en cascada: primero los descendientes, al final el padre.
        reporte = {}
        if cascada:
            _eliminar_descendientes(
                cur, TABLA_PURGA, col_id, a_borrar, mapa,
                (TABLA_PURGA,), 1, reporte,
            )
            for tabla_hija in sorted(reporte):
                print(f"[PURGA]   → {tabla_hija}: {reporte[tabla_hija]} filas eliminadas")

        eliminadas = _borrar_por_valores(cur, TABLA_PURGA, col_id, a_borrar)
        conn.commit()

        print(f"[PURGA] Filas eliminadas en {TABLA_PURGA}: {eliminadas}")
        return eliminadas

    except Exception as e:
        print(f"[PURGA] Error durante la purga: {e}")
        if conn is not None:
            try:
                conn.rollback()
                print("[PURGA] Transacción revertida; no se borró nada.")
            except Exception:
                pass
        return 0

    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()