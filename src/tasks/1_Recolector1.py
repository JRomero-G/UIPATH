import json
import os
import tempfile
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def main():
    """
    Función principal que configura el navegador, accede a la URL, interactúa con la página,
    extrae la tabla y guarda los datos en un archivo JSON temporal.
    """
    # Configurar el webdriver para Chrome (asegúrate de tener ChromeDriver instalado y en PATH)
    driver = setup_driver()
    
    try:
        # Acceder a la URL y esperar a que cargue
        load_page(driver, "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/NCO/FrmNCOListado.cpe")
        
        # Encontrar y seleccionar 100 registros en el cuadro de selección
        select_records(driver, 100)
        
        # Extraer los datos de la tabla
        data = extract_table_data(driver)
        
        # Guardar los datos en un archivo JSON temporal
        save_to_json(data)
        
    finally:
        # Cerrar el navegador
        driver.quit()

def setup_driver():
    """
    Configura y retorna el webdriver para Chrome.
    Nota: Requiere que ChromeDriver esté instalado y disponible en el PATH del sistema.
    Puedes descargar ChromeDriver desde https://chromedriver.chromium.org/downloads
    """
    # Opciones para Chrome (puedes agregar más como headless si no quieres ver la ventana)
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # Descomenta para modo sin interfaz
    driver = webdriver.Chrome(options=options)
    return driver

def load_page(driver, url):
    """
    Accede a la URL y espera al menos 40 segundos para que la página cargue completamente.
    Usa time.sleep para un retraso fijo, pero podría mejorarse con WebDriverWait para elementos específicos.
    """
    driver.get(url)
    print("Esperando a que la página cargue...")
    time.sleep(40)  # Espera mínima de 40 segundos como se indica

def select_records(driver, num_records):
    """
    Encuentra el cuadro de selección entre "Mostrar registros" y selecciona el valor deseado (ej: 100).
    Asume que el select está en un elemento con texto contiguo o cerca de "Mostrar registros".
    """
    # Esperar a que el elemento de selección esté presente (ajusta el XPath si es necesario)
    try:
        # Buscar el label o div que contiene "Mostrar registros" y encontrar el select dentro o cerca
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Mostrar registros')]"))
        )
        
        # Encontrar el select (asumiendo que es el único o el primero cerca del texto)
        # Ajusta el XPath basado en inspección: por ejemplo, si el select tiene name='pageSize' o similar
        select_element = driver.find_element(By.XPATH, "//select[contains(@id, 'pageSize') or contains(@name, 'registros')]")  # Ajusta según inspección real
        
        # Si no encuentra por ID/name, buscar el select más cercano al texto
        if not select_element:
            select_element = driver.find_element(By.XPATH, "//*[contains(text(), 'Mostrar registros')]/following-sibling::select | //*[contains(text(), 'Mostrar registros')]/select")
        
        select = Select(select_element)
        select.select_by_value(str(num_records))  # Selecciona el option con value='100'
        
        print(f"Seleccionados {num_records} registros.")
        
        # Esperar a que la tabla se actualice después de cambiar el select
        time.sleep(5)  # Ajusta si es necesario, o usa WebDriverWait para la tabla
        
    except Exception as e:
        print(f"Error al seleccionar registros: {e}")
        raise

def extract_table_data(driver):
    """
    Extrae los headers y rows de la tabla principal.
    Asume que la tabla es la primera <table> después del select, o con un ID/class específico.
    Maneja variaciones en nombres de columnas.
    Retorna una lista de diccionarios, cada uno representando un registro.
    """
    data = []
    
    try:
        # Esperar a que la tabla esté presente
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        
        # Encontrar la tabla (ajusta XPath si hay múltiples tablas)
        table = driver.find_element(By.XPATH, "//table[contains(@class, 'tabla') or @id='tablaRegistros']")  # Ajusta según inspección
        
        # Extraer headers (th)
        headers = [th.text.strip().lower() for th in table.find_elements(By.TAG_NAME, "th")]
        # Normalizar headers para manejar variaciones (ej: 'tipo de necesidad' o similar)
        normalized_headers = normalize_column_names(headers)
        
        # Extraer rows (tr), saltando la primera si es header
        rows = table.find_elements(By.TAG_NAME, "tr")[1:101]  # Hasta 100 registros
        
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) == len(normalized_headers):
                record = {normalized_headers[i]: cells[i].text.strip() for i in range(len(cells))}
                # Extraer URL si está en un <a> dentro de la celda (ej: URL de Entidad Contratante)
                for i, header in enumerate(normalized_headers):
                    if 'url' in header.lower():
                        a_tag = cells[i].find_element(By.TAG_NAME, "a") if cells[i].find_elements(By.TAG_NAME, "a") else None
                        if a_tag:
                            record[header] = a_tag.get_attribute("href")
                data.append(record)
        
        print(f"Extraídos {len(data)} registros.")
        
    except Exception as e:
        print(f"Error al extraer tabla: {e}")
        raise
    
    return data

def normalize_column_names(headers):
    """
    Normaliza nombres de columnas para manejar variaciones (ej: 'tipo de necesidad' -> 'tipo_necesidad').
    Esto ayuda si la página cambia nombres ligeramente para anti-bots.
    """
    mapping = {
        'tipo de necesidad': 'tipo_necesidad',
        'código de necesidad de contratación': 'codigo_necesidad',
        'fecha de publicación': 'fecha_publicacion',
        'provincia-cantón': 'provincia_canton',
        'descripción del objeto de compra': 'descripcion_objeto_compra',
        'estado de la necesidad': 'estado_necesidad',
        'fecha límite para la entrega de proformas': 'fecha_limite_proformas',
        'entidad contratante': 'entidad_contratante',
        'url de entidad contratante': 'entidad_contratante_url',
        'dirección de entrega': 'direccion_entrega',
        'contacto': 'contacto',
        # Agrega más variaciones si se conocen (ej: 'provincia canton' sin guión)
    }
    return [mapping.get(h.lower(), h.lower().replace(' ', '_')) for h in headers]

def save_to_json(data):
    """
    Guarda la lista de datos en un archivo JSON en una carpeta temporal de Windows.
    Usa tempfile para obtener un directorio temporal.
    """
    temp_dir = tempfile.gettempdir()  # Carpeta temporal en Windows (ej: C:\Users\Usuario\AppData\Local\Temp)
    file_path = os.path.join(temp_dir, "compras_publicas_data.json")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"Datos guardados en: {file_path}")

if __name__ == "__main__":
    main()