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
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "gestorex",
}

MODEL_ID = "llama-3.3-70b-versatile"
API_KEY = "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"

TEMAS = """
Kit de alimentos, contratación de servicio,contratación del servicio, servicio de producción audiovisual, servicio de consultaría,servicio, 
servicios de todo tipo, medicamentos, seguros, pólizas, arrendamiento,
combustibles hidrocarburos y sus derivados, compuestos químicos de uso industrial,
alimentos de todo tipo, material de oficina, alquileres, hosting, internet, fiscalización,
mantenimiento, logística de eventos, adecuaciones, monitoreos, mano de obra, recarga de gas, servicio de instalación
"""

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
            WHERE id = %s
        """,
            (etapa, row["id"]),
        )

    conn.commit()
    cursor.close()
    conn.close()


# =========================
# 5. CLASIFICACIÓN IA
# =========================


def clasificar_descripcion_lote(batch_data):
    prompt = f"""
    Eres un analista de compras públicas.
    Analiza si en las siguientes descripciones se mencionan estas palabras:
    {TEMAS}

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
        resultados = clasificar_descripcion_lote(bloque)
        resultados_finales.update(resultados)

    # Actualiza la etapa según resultado invertido
    actualizar_etapa(df, resultados_finales)

    print("Proceso finalizado correctamente.")


# =========================
# 7. EJECUCIÓN
# =========================

if __name__ == "__main__":
    main()
