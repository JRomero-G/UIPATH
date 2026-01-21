import re
import json
import datetime
import pandas as pd
import mysql.connector
from openai import OpenAI

# =========================
# 1. CONFIGURACIÓN
# =========================

MYSQL_CONFIG = {
    "host": "35.225.240.246",
    "user": "root",
    "password": "Admin123%",
    "database": "gestorex",
}

MODEL_ID = "llama-3.3-70b-versatile"
API_KEY = "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"

# =========================
# 2. CLIENTE OPENAI / GROQ
# =========================

client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")

# =========================
# 3. UTILIDADES
# =========================


def safe_value(val, default="SIN_VALOR"):
    if pd.isna(val) or val is None:
        return default
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, datetime.date):
        return val.strftime("%Y-%m-%d")
    return str(val)


def limpiar_texto(texto):
    if not texto:
        return ""
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def dividir_dict(data, size=40):
    items = list(data.items())
    for i in range(0, len(items), size):
        yield dict(items[i : i + size])


# =========================
# 4. FUNCIONES BASE DE DATOS
# =========================


def obtener_infimas():
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
    """Trae todas las palabras o frases de la tabla palabras_clave"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT palabra_clave FROM palabras_clave")
    filas = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convertir a lista de cadenas y limpiar
    palabras = [limpiar_texto(fila[0]) for fila in filas if fila[0]]
    return palabras


def actualizar_etapa(df, resultados):
    """Actualiza la columna etapa según el resultado invertido: SI -> 'no seleccionada', NO -> 'preseleccionada'"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    for idx, row in df.iterrows():
        if resultados.get(idx) is None:
            continue

        # Invertir resultado
        etapa = "preseleccionada" if resultados[idx] is False else "no seleccionada"

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
# 5. CLASIFICACIÓN IA
# =========================


def clasificar_descripcion_lote(batch_data, palabras_clave):
    """Clasifica un lote de descripciones usando palabras clave de la BD"""
    prompt = f"""
    Eres un analista de compras públicas.
    Analiza si en las siguientes descripciones se mencionan estas palabras o frases clave:
    {", ".join(palabras_clave)}

    Responde ESTRICTAMENTE con un objeto JSON donde la clave es el número de fila y el valor es "SI" o "NO".
    Datos:
    {json.dumps(batch_data, ensure_ascii=False)}
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        resultados = json.loads(response.choices[0].message.content)

        resultado_final = {}
        for k, v in resultados.items():
            try:
                idx = int(k)
                resultado_final[idx] = v.upper() == "SI"
            except ValueError:
                print(f"Clave inválida devuelta por la IA: {k}")
        return resultado_final

    except Exception as e:
        print(f"Error al preparar la solicitud: {e}")
        return {}


# =========================
# 6. ORQUESTADOR PRINCIPAL
# =========================


def main():
    df = obtener_infimas()
    if df.empty:
        print("No hay datos en la tabla infimas con etapa 'ingresada'.")
        return

    palabras_clave = obtener_palabras_clave()
    if not palabras_clave:
        print("No hay palabras clave en la tabla palabras_clave.")
        return

    data = {
        idx: str(row["descripcion_objeto_compra"]).strip()
        for idx, row in df.iterrows()
        if row.get("descripcion_objeto_compra")
    }

    if not data:
        print("No hay descripciones válidas para analizar.")
        return

    resultados_finales = {}
    print(f"Procesando {len(data)} registros...")

    for bloque in dividir_dict(data, size=40):
        resultados = clasificar_descripcion_lote(bloque, palabras_clave)
        resultados_finales.update(resultados)

    # Actualiza la etapa según resultado invertido
    actualizar_etapa(df, resultados_finales)
    print("Proceso finalizado correctamente.")


# =========================
# 7. EJECUCIÓN
# =========================

if __name__ == "__main__":
    main()
