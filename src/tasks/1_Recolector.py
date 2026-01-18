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
import time
import tempfile
import os


def main():
    url = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/NCO/FrmNCOListado.cpe"

    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")  # descomenta si quieres invisible total
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=800,600")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    try:
        driver.minimize_window()
        print("→ Ventana minimizada de inmediato")
    except Exception as e:
        print(f"No se pudo minimizar: {e}")

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
        print("Ejemplos (primeros 3):")
        for reg in data[:3]:
            print(reg)
        save_to_db(data)
    else:
        print(
            "No se extrajeron datos. Abre debug_pagina_final.html y verifica <tbody>."
        )


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
            host="35.225.240.246",
            user="root",
            password="Admin123%",
            database="gestorex",
            connect_timeout=10,
        )
        cur = conn.cursor()

        inserted = 0
        for registro in data:
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
            except mysql.connector.Error as err:
                print(
                    f"Error en upsert_infimas para {registro.get('codigo_necesidad', 'N/A')}: {err}"
                )

        conn.commit()
        print(f"Guardados/actualizados {inserted} registros vía procedimiento.")

    except Exception as e:
        print(f"Error en BD: {e}")
    finally:
        if "cur" in locals():
            cur.close()
        if "conn" in locals() and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()
