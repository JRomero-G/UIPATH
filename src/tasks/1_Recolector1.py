import json
import os
import tempfile
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configuración de cabeceras para simular un navegador real (inspirado en el script adjunto)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-EC,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.compraspublicas.gob.ec/",
}

def main():
    """
    Función principal que accede a la URL usando requests, interactúa simulando la selección de registros,
    extrae la tabla y guarda los datos en un archivo JSON temporal.
    """
    url = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/NCO/FrmNCOListado.cpe"
    
    # Crear sesión reutilizable
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Acceder a la URL inicial y obtener el HTML
    html_content = load_page(session, url)
    
    # Simular la selección de 100 registros parseando el form y enviando request modificado
    html_content = select_records(session, url, html_content, 100)
    
    # Extraer los datos de la tabla usando BeautifulSoup
    data = extract_table_data(html_content, url)
    
    # Guardar los datos en un archivo JSON temporal
    save_to_json(data)

def load_page(session, url):
    """
    Accede a la URL usando requests y retorna el HTML content.
    Agrega un timeout y una pequeña pausa si es necesario.
    """
    print("Accediendo a la página...")
    try:
        response = session.get(url, timeout=60)  # Timeout de 60s para manejar cargas lentas
        response.raise_for_status()
        print("Página cargada exitosamente.")
        time.sleep(5)  # Pausa opcional para simular carga, ajusta si necesario
        return response.text
    except Exception as e:
        print(f"Error al cargar la página: {e}")
        raise

def select_records(session, base_url, html_content, num_records):
    """
    Parsea el HTML para encontrar el form y el select cerca de "Mostrar registros".
    Modifica los parámetros para seleccionar el número deseado y envía una nueva request.
    Retorna el nuevo HTML content después de "seleccionar".
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Encontrar el elemento con "Mostrar registros"
    mostrar_elem = soup.find(string=lambda t: 'Mostrar registros' in str(t))
    if not mostrar_elem:
        print("No se encontró 'Mostrar registros'.")
        return html_content  # Retorna el original si falla
    
    # Encontrar el form padre
    form = mostrar_elem.find_parent('form')
    if not form:
        print("No se encontró form asociado.")
        return html_content
    
    action = urljoin(base_url, form.get('action', ''))
    method = form.get('method', 'get').lower()
    
    # Recopilar parámetros del form
    params = {}
    for input_tag in form.find_all(['input', 'select']):
        name = input_tag.get('name')
        if not name:
            continue
        if input_tag.name == 'input':
            params[name] = input_tag.get('value', '')
        elif input_tag.name == 'select':
            # Buscar si es el select de registros (por proximidad o attrs)
            if 'registros' in name.lower() or 'pagesize' in name.lower() or 'ps' in name.lower():
                # Verificar si 100 es una opción disponible
                options = {opt.get('value'): opt.text for opt in input_tag.find_all('option')}
                if str(num_records) in options:
                    params[name] = str(num_records)
                    print(f"Seleccionados {num_records} registros vía parámetro '{name}'.")
                else:
                    print(f"{num_records} no es una opción disponible. Usando default.")
                    selected = input_tag.find('option', selected=True)
                    params[name] = selected.get('value') if selected else ''
            else:
                selected = input_tag.find('option', selected=True)
                params[name] = selected.get('value') if selected else ''
    
    # Enviar la request modificada
    try:
        if method == 'post':
            response = session.post(action, data=params, timeout=60)
        else:
            response = session.get(action, params=params, timeout=60)
        response.raise_for_status()
        time.sleep(5)  # Pausa para simular actualización de tabla
        return response.text
    except Exception as e:
        print(f"Error al simular selección: {e}")
        return html_content  # Retorna original si falla

def extract_table_data(html_content, base_url):
    """
    Extrae los headers y rows de la tabla principal usando BeautifulSoup.
    Maneja variaciones en nombres de columnas.
    Retorna una lista de diccionarios, cada uno representando un registro.
    """
    data = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Encontrar la tabla (asumiendo class 'tabla' o id 'tablaRegistros', ajusta si necesario)
    table = soup.find('table', attrs={'class': lambda c: c and 'tabla' in c} or {'id': 'tablaRegistros'})
    if not table:
        # Búsqueda alternativa por headers
        tables = soup.find_all('table')
        for t in tables:
            headers = [th.text.strip().lower() for th in t.find_all('th')]
            if any(h in headers for h in ['tipo de necesidad', 'código de necesidad']):
                table = t
                break
        if not table:
            print("No se encontró la tabla.")
            return data
    
    # Extraer headers
    headers = [th.text.strip().lower() for th in table.find_all('th')]
    normalized_headers = normalize_column_names(headers)
    
    # Extraer rows (tr en tbody o directo)
    tbody = table.find('tbody') if table.find('tbody') else table
    rows = tbody.find_all('tr')[:100]  # Limitar a 100
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) == len(normalized_headers):
            record = {normalized_headers[i]: cells[i].text.strip() for i in range(len(cells))}
            # Extraer URL si hay <a> en la celda
            for i, header in enumerate(normalized_headers):
                if 'url' in header.lower():
                    a_tag = cells[i].find('a')
                    if a_tag and a_tag.get('href'):
                        record[header] = urljoin(base_url, a_tag['href'])
            data.append(record)
    
    print(f"Extraídos {len(data)} registros.")
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