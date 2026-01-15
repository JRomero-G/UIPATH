import json
import pandas as pd
import mysql.connector
from mysql.connector import Error

def clean(x):
    # Limpia valores: None → 'SIN DEFINIR', quita espacios raros y convierte a string
    if x is None or pd.isna(x):
        return "SIN DEFINIR"
    return str(x).replace("\u00a0", " ").replace("\n", " ").strip() or "SIN DEFINIR"


def insert_to_mysql(json_data_str):
    
    # Recibe un string JSON con lista de registros (como los extraídos del portal de compras públicas)
    # e inserta/actualiza en la base de datos usando el procedimiento upsert_infimas.

    try:
        data = json.loads(json_data_str)
        if not data or not isinstance(data, list):
            return "JSON inválido o vacío → no se insertó nada"
        
        df = pd.DataFrame(data)
        
        # Mapeo de nombres de columnas que vienen del portal → nombres esperados en tu procedimiento
        column_mapping = {
            # Nombres comunes que aparecen en la web
            "tipo_necesidad": "tipo_necesidad",
            "Tipo de Necesidad": "tipo_necesidad",
            "codigo_necesidad": "codigo_necesidad",
            "Código Necesidad de Contratación": "codigo_necesidad",
            "Código Necesidad": "codigo_necesidad",
            "fecha_publicacion": "fecha_publicacion",
            "Fecha de Publicación": "fecha_publicacion",
            "provincia_canton": "provincia_canton",
            "Provincia - Cantón": "provincia_canton",
            "Provincia / Cantón": "provincia_canton",
            "descripcion_objeto_compra": "descripcion_objeto_compra",
            "Descripción del Objeto de compra": "descripcion_objeto_compra",
            "estado_necesidad": "estado_necesidad",
            "Estado de la Necesidad": "estado_necesidad",
            "fecha_limite_proformas": "fecha_limite_proformas",
            "Fecha límite para la entrega de proformas": "fecha_limite_proformas",
            "entidad_contratante": "entidad_contratante",
            "Entidad Contratante": "entidad_contratante",
            "entidad_contratante_url": "entidad_contratante_url",
            "direccion_entrega": "direccion_entrega",
            "Dirección de Entrega": "direccion_entrega",
            "contacto": "contacto",
            "Contacto": "contacto",
        }
        
        # Renombramos las columnas que existan
        df = df.rename(columns=column_mapping)
        
        # Nos aseguramos que todas las columnas esperadas existan (si no → NaN)
        expected_cols = [
            'tipo_necesidad', 'codigo_necesidad', 'fecha_publicacion', 'provincia_canton',
            'descripcion_objeto_compra', 'estado_necesidad', 'fecha_limite_proformas',
            'entidad_contratante', 'entidad_contratante_url', 'direccion_entrega', 'contacto'
        ]
        
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        
        # Conexión a MySQL
        conn = mysql.connector.connect(
            host="localhost",     # Recordar cambiar al usar la BD en Cloud
            user="root",
            password="",           # ← pon tu contraseña aquí si tienes # Admin123% para cloud
            database="gestorex",
            autocommit=True
        )
        
        cursor = conn.cursor()
        
        sql = """
            CALL upsert_infimas(
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
        """
        
        total = 0
        for _, row in df.iterrows():
            params = (
                clean(row['tipo_necesidad']),
                clean(row['codigo_necesidad']),
                clean(row['fecha_publicacion']),
                clean(row['provincia_canton']),
                clean(row['descripcion_objeto_compra']),
                clean(row['estado_necesidad']),
                clean(row['fecha_limite_proformas']),
                clean(row['entidad_contratante']),
                clean(row['entidad_contratante_url']),
                clean(row['direccion_entrega']),
                clean(row['contacto'])
            )
            cursor.execute(sql, params)
            total += 1
        
        cursor.close()
        conn.close()
        
        return f"{total} registros procesados correctamente"
    
    except json.JSONDecodeError:
        return "Error: el JSON no es válido"
    except Error as e:
        return f"Error en MySQL: {e}"
    except Exception as e:
        return f"Error inesperado: {e}"


# ────────────────────────────────────────────────
# Ejemplo de uso (puedes pegar aquí el JSON que copies del portal)
# ────────────────────────────────────────────────

if __name__ == "__main__":
    # Pega aquí el JSON que copies de la página (o de varias páginas concatenadas)
    ejemplo_json = '''[
      {
        "tipo_necesidad": "Ínfimas Cuantías",
        "codigo_necesidad": "NIC-0968564660001-2026-00006",
        "fecha_publicacion": "2026-01-12 19:14:00",
        "provincia_canton": "GUAYAS - GUAYAQUIL",
        "descripcion_objeto_compra": "SERVICIO DE MANTENIMIENTO PREVENTIVO PARA LA IMPRESORA...",
        "estado_necesidad": "En Curso",
        "fecha_limite_proformas": "2026-01-13 19:15:00",
        "entidad_contratante": "GOBIERNO AUTONOMO DESCENTRALIZADO PARROQUIAL RURAL DE JUAN GOMEZ RENDON PROGRESO",
        "entidad_contratante_url": "https://www.compraspublicas.gob.ec/NCO/NCORegistroDetalle.cpe?...",
        "direccion_entrega": "AV. PEDRO PABLO VITERI S/N ATRAS DE LA ESCUELA JUANA TOLA",
        "contacto": "Funcionario Encargado: ING. PAMELA REYES RODRIGUEZ Email: jp-jgrp@live.com"
      }
      // ... más registros
    ]'''  # ?????
    
    resultado = insert_to_mysql(ejemplo_json)
    print(resultado)