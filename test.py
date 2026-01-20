from sqlalchemy import create_engine

# Usa exactamente tu DATABASE_URL
DATABASE_URL = (
    "mysql+pymysql://root:Admin123%25@35.225.240.246:3306/gestorex?charset=utf8mb4"
)

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        print("¡Conexión exitosa! Todo bien.")
        result = connection.execute("SELECT 1")
        print("Resultado:", result.fetchone())
except Exception as e:
    print("Error al conectar:", e)
