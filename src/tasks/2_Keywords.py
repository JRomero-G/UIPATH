"""
Script de clasificación de compras públicas (infimas) usando Gemini 2.5 Flash
Conecta a MySQL, obtiene datos, clasifica con IA y actualiza estados

ACTUALIZACIÓN: Migrado de gemini-2.0-flash (descontinuado) a gemini-2.5-flash
Modelo actualizado: gemini-2.5-flash - Mejor precio/rendimiento con capacidades de pensamiento
Región: us-central1 (soportada)

ALTERNATIVAS DISPONIBLES:
- gemini-2.5-pro: Para casos que requieran máximo razonamiento (más costoso)
- gemini-3.1-pro-preview: Modelo experimental más avanzado (preview, puede tener limitaciones)
"""

import os
import re
import json
import tempfile
import datetime
import pandas as pd
import mysql.connector
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel
import sys
from pathlib import Path

#raíz del proyecto al path de Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from Config import Global

# =========================
# 1. CONFIGURACIÓN
# =========================

MYSQL_CONFIG = {
    "host": Global.DB_HOST,
    "user": Global.DB_USER,
    "password": Global.DB_PASSWORD,
    "database": Global.DATABASE,
}

# Modelo actualizado - Gemini 2.5 Flash
# Este modelo ofrece:
# - Mejor rendimiento que 2.0 Flash
# - Capacidades de "pensamiento" (thinking) para mayor precisión
# - Disponibilidad en us-central1
# - Precio competitivo
GEMINI_MODEL = "gemini-2.5-flash"

# ALTERNATIVAS:
# GEMINI_MODEL = "gemini-2.5-pro"  # Para máxima precisión (más costoso)
# GEMINI_MODEL = "gemini-3.1-pro-preview"  # Experimental (puede tener limitaciones regionales)

def obtener_ruta_credenciales():
    """
    Retorna una ruta válida al archivo de credenciales.
    - En Render: crea archivo temporal desde JSON
    - En local: usa archivo físico
    """

    # PRODUCCIÓN (Render)
    credentials_json = Global.RENDER_CRENDENTIALS_JSON

    if credentials_json:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as temp:
            temp.write(credentials_json)
            return temp.name

    # LOCAL
    if Global.CREDENTIALS_GEMINI:
        return Global.CREDENTIALS_GEMINI

    raise Exception("No se encontraron credenciales de Gemini")


# =========================
# 2. INICIALIZACIÓN DE VERTEX AI
# =========================

def inicializar_vertex_ai():
    """Inicializa VertexAI con las credenciales de servicio"""

    ruta_credenciales = obtener_ruta_credenciales()

    #Crear credenciales
    credentials = service_account.Credentials.from_service_account_file(
        ruta_credenciales
    )
    
    # Obtener project_id del archivo de credenciales
    with open(ruta_credenciales, 'r') as f:
        creds_data = json.load(f)
        project_id = creds_data.get("project_id")
        
    if not project_id:
        raise Exception("No se encontró project_id en las credenciales")
            
    vertexai.init(
        project=project_id,
        credentials=credentials,
        location="us-central1"  # Región soportada para Gemini 2.5
    )
    
    return GenerativeModel(GEMINI_MODEL)

# =========================
# 3. UTILIDADES
# =========================

def safe_value(val, default="SIN_VALOR"):
    """Convierte valores de manera segura a string"""
    if pd.isna(val) or val is None:
        return default
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, datetime.date):
        return val.strftime("%Y-%m-%d")
    return str(val)

def limpiar_texto(texto):
    """Limpia y normaliza texto"""
    if not texto:
        return ""
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

def dividir_dict(data, size=40):
    """Divide un diccionario en bloques de tamaño específico"""
    items = list(data.items())
    for i in range(0, len(items), size):
        yield dict(items[i : i + size])

# =========================
# 4. FUNCIONES BASE DE DATOS
# =========================

def obtener_infimas():
    """Obtiene registros de infimas con etapa 'ingresada'"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM infimas
        WHERE etapa = 'ingresada'
    """)
    datos = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(datos)

    if not df.empty and "descripcion_objeto_compra" in df.columns:
        df["descripcion_objeto_compra"] = df["descripcion_objeto_compra"].apply(
            lambda x: limpiar_texto(str(x))
        )
    return df

def obtener_palabras_clave():
    """Obtiene palabras clave de la base de datos"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT palabra_clave FROM palabras_clave")
    filas = cursor.fetchall()
    cursor.close()
    conn.close()

    palabras = [limpiar_texto(fila[0]) for fila in filas if fila[0]]
    return palabras

def actualizar_etapa(df, resultados):
    """Actualiza la etapa de los registros según resultados de clasificación"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    for idx, row in df.iterrows():
        if idx not in resultados:
            continue

        # Lógica: SI se encontró palabra clave -> NO seleccionada
        # NO se encontró palabra clave -> PRESELECCIONADA
        etapa = "no seleccionada" if resultados[idx] is True else "preseleccionada"

        cursor.execute(
            """
            UPDATE infimas
            SET etapa = %s,
                actualizado_en = NOW()
            WHERE id_infima = %s
        """,
            (etapa, row["id_infima"]),
        )

    conn.commit()
    cursor.close()
    conn.close()

# =========================
# 5. CLASIFICACIÓN CON IA
# =========================

def clasificar_descripcion_lote(batch_data, palabras_clave, model):
    """
    Clasifica un lote de descripciones usando Gemini 2.5 Flash
    
    Gemini 2.5 Flash incluye capacidades de pensamiento que mejoran
    la precisión en tareas de clasificación complejas.
    """
    prompt = f"""
Eres un analista experto de compras públicas especializado en clasificación de contenido.

TAREA:
Analiza si en las siguientes descripciones se mencionan estas palabras o frases clave:
{", ".join(palabras_clave)}

INSTRUCCIONES:
1. Lee cuidadosamente cada descripción
2. Busca coincidencias exactas o variaciones semánticas de las palabras/frases clave
3. Si encuentras AL MENOS UNA palabra o frase clave en la descripción, responde "SI"
4. Si NO encuentras NINGUNA palabra o frase clave, responde "NO"
5. Sé preciso: las palabras deben estar realmente presentes o tener clara relación semántica

FORMATO DE RESPUESTA:
Responde ESTRICTAMENTE con un objeto JSON donde:
- La clave es el número de fila
- El valor es "SI" (se encontró al menos una palabra clave) o "NO" (no se encontró ninguna)

DATOS A ANALIZAR:
{json.dumps(batch_data, ensure_ascii=False, indent=2)}

RESPONDE SOLO CON EL JSON, SIN TEXTO ADICIONAL.
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Limpiar markdown si viene con ```json```
        if response_text.startswith("```"):
            response_text = re.sub(r"```json\n?|```\n?", "", response_text).strip()
        
        resultado_json = json.loads(response_text)
        
        # Convertir "SI"/"NO" a True/False
        resultado_bool = {}
        for idx, valor in resultado_json.items():
            idx_int = int(idx)
            resultado_bool[idx_int] = (valor.upper() == "SI")
        
        return resultado_bool
        
    except Exception as e:
        print(f"Error al clasificar lote: {e}")
        # Retornar todos como False (preseleccionados) en caso de error
        return {int(idx): False for idx in batch_data.keys()}

# =========================
# 6. ORQUESTADOR PRINCIPAL
# =========================

def main():
    """Función principal que orquesta todo el proceso"""
    print("=" * 60)
    print("CLASIFICADOR DE COMPRAS PÚBLICAS")
    print(f"Modelo: {GEMINI_MODEL}")
    print("=" * 60)
    
    # Inicializar modelo Gemini
    print(f"\n1. Inicializando modelo {GEMINI_MODEL}...")
    try:
        model = inicializar_vertex_ai()
        print("   ✓ Modelo inicializado correctamente")
    except Exception as e:
        print(f"   ✗ Error al inicializar modelo: {e}")
        return
    
    # Obtener datos
    print("\n2. Obteniendo registros de la base de datos...")
    df = obtener_infimas()
    if df.empty:
        print("   ⚠ No hay datos en la tabla infimas con etapa 'ingresada'.")
        return
    print(f"   ✓ {len(df)} registros encontrados")

    # Obtener palabras clave
    print("\n3. Obteniendo palabras clave...")
    palabras_clave = obtener_palabras_clave()
    if not palabras_clave:
        print("   ⚠ No hay palabras clave en la tabla palabras_clave.")
        return
    print(f"   ✓ {len(palabras_clave)} palabras clave cargadas")

    # Preparar datos
    data = {
        idx: str(row["descripcion_objeto_compra"]).strip()
        for idx, row in df.iterrows()
        if row.get("descripcion_objeto_compra")
    }

    if not data:
        print("   ⚠ No hay descripciones válidas para analizar.")
        return

    # Clasificar por lotes
    print(f"\n4. Clasificando {len(data)} registros en lotes de 40...")
    resultados_finales = {}
    total_lotes = (len(data) + 39) // 40  # Ceiling division
    lote_actual = 0
    
    for bloque in dividir_dict(data, size=40):
        lote_actual += 1
        print(f"   Procesando lote {lote_actual}/{total_lotes}...")
        resultados = clasificar_descripcion_lote(bloque, palabras_clave, model)
        resultados_finales.update(resultados)

    # Actualizar base de datos
    print("\n5. Actualizando estados en la base de datos...")
    actualizar_etapa(df, resultados_finales)
    
    # Resumen
    preseleccionadas = sum(1 for v in resultados_finales.values() if not v)
    no_seleccionadas = sum(1 for v in resultados_finales.values() if v)
    
    print("\n" + "=" * 60)
    print("PROCESO FINALIZADO CORRECTAMENTE")
    print("=" * 60)
    print(f"Registros procesados:     {len(resultados_finales)}")
    print(f"Preseleccionadas:         {preseleccionadas}")
    print(f"No seleccionadas:         {no_seleccionadas}")
    print("=" * 60)

# =========================
# 7. EJECUCIÓN
# =========================

if __name__ == "__main__":
    main()