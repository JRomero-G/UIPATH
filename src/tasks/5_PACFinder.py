import mysql.connector
import pandas as pd
import time
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =====================================================
# 1. CONFIGURACIÓN BASE (SE CONSERVA COMO PEDISTE)
# =====================================================
MYSQL_CONFIG = {
    "host": "35.225.240.246",
    "user": "root",
    "password": "Admin123%",
    "database": "gestorex",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-EC,es;q=0.9",
}

URL_PAC = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/PC/buscarPACe.cpe#"

# =====================================================
# 2. CONEXIÓN Y CARGA DE INFIMAS
# =====================================================
def cargar_infimas():
    """
    Obtiene filas de la tabla infimas donde PAC >= 0
    y construye la estructura solicitada en memoria.
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            codigo_necesidad,
            descripcion_objeto_compra,
            entidad_contratante
        FROM infimas
        WHERE PAC >= 0
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows)
    df["V_Total"] = 0.0  # columna requerida
    return df


# =====================================================
# 3. DRIVER SELENIUM (HEADLESS + HEADERS)
# =====================================================
def crear_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    return webdriver.Chrome(options=options)


# =====================================================
# 4. SELECCIÓN DE ENTIDAD CONTRATANTE
# =====================================================
def seleccionar_entidad(driver, entidad):
    """
    Ejecuta el flujo:
    - botonBuscarEntidad()
    - escribe entidad
    - itera opciones hasta encontrar resultados
    """
    driver.find_element(By.ID, "botonBuscarEntidad").click()

    WebDriverWait(driver, 20).until(
        EC.number_of_windows_to_be(2)
    )

    driver.switch_to.window(driver.window_handles[1])

    input_txt = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.NAME, "txtEmpresa"))
    )
    input_txt.clear()
    input_txt.send_keys(entidad)

    driver.find_element(By.ID, "botonBuscar").click()
    time.sleep(2)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tr")[1:]

    for fila in filas:
        fila.click()
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[0])

        driver.find_element(By.ID, "botonBuscar").click()
        time.sleep(3)

        if hay_resultados(driver):
            return True

        # volver a intentar con siguiente opción
        driver.switch_to.window(driver.window_handles[1])

    driver.switch_to.window(driver.window_handles[0])
    return False


# =====================================================
# 5. VALIDACIÓN DE RESULTADOS
# =====================================================
def hay_resultados(driver):
    filas = driver.find_elements(By.CSS_SELECTOR, "table tr")
    return len(filas) > 1


# =====================================================
# 6. BUSCAR COINCIDENCIA Y EXTRAER V.TOTAL
# =====================================================
def obtener_v_total(driver, descripcion_objeto):
    filas = driver.find_elements(By.CSS_SELECTOR, "table tr")[1:]

    for fila in filas:
        cols = fila.find_elements(By.TAG_NAME, "td")
        if not cols:
            continue

        descripcion_web = cols[1].text.lower()
        if descripcion_objeto.lower() in descripcion_web:
            valor = cols[-1].text
            valor = re.sub(r"[^\d.,]", "", valor).replace(".", "").replace(",", ".")
            return float(valor)

    return 0.0


# =====================================================
# 7. ACTUALIZACIÓN EN BASE DE DATOS
# =====================================================
def actualizar_bd(df):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    for _, row in df.iterrows():
        if row["V_Total"] > 0:
            cursor.execute("""
                UPDATE infimas
                SET PAC = %s,
                    etapa = 'seleccionada'
                WHERE codigo_necesidad = %s
            """, (row["V_Total"], row["codigo_necesidad"]))

    conn.commit()
    cursor.close()
    conn.close()


# =====================================================
# 8. MAIN
# =====================================================
def main():
    infimas = cargar_infimas()
    driver = crear_driver()
    driver.get(URL_PAC)

    for i, row in infimas.iterrows():
        if seleccionar_entidad(driver, row["entidad_contratante"]):
            v_total = obtener_v_total(
                driver,
                row["descripcion_objeto_compra"]
            )
            infimas.at[i, "V_Total"] = v_total

    driver.quit()
    actualizar_bd(infimas)


if __name__ == "__main__":
    main()
