import os
from google.cloud import storage
from vertexai.generative_models import GenerativeModel, Part
import vertexai

# 1. CONFIGURACIÓN DE CREDENCIALES
# Sustituye 'tu-archivo-credenciales.json' por la ruta de tu JSON
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "tu-archivo-credenciales.json"

PROJECT_ID = "tu-proyecto-id"
LOCATION = "us-central1" # O la región que prefieras
BUCKET_NAME = "nombre-de-tu-bucket"

# Inicializar Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-1.5-flash") # Flash es más rápido y económico para lotes

def analizar_documentos_en_bucket():
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    
    # Listar todos los archivos en el bucket
    blobs = bucket.list_blobs()
    
    # --- ESPACIO PARA TU PROMPT ---
    PROMPT_USUARIO = "Analiza este documento y extrae los puntos clave en formato de lista."
    # ------------------------------

    print(f"Iniciando análisis de archivos en: gs://{BUCKET_NAME}\n")

    for blob in blobs:
        # Filtrar solo archivos PDF (puedes añadir .docx, .txt, etc.)
        if blob.name.lower().endswith('.pdf'):
            print(f"--- Analizando: {blob.name} ---")
            
            # Crear la referencia del archivo en GCS para el modelo
            document_part = Part.from_uri(
                uri=f"gs://{BUCKET_NAME}/{blob.name}",
                mime_type="application/pdf"
            )
            
            try:
                # Generar respuesta
                response = model.generate_content([document_part, PROMPT_USUARIO])
                
                print(f"Resultado para {blob.name}:")
                print(response.text)
                print("-" * 30)
                
            except Exception as e:
                print(f"Error procesando {blob.name}: {e}")

if __name__ == "__main__":
    analizar_documentos_en_bucket()