import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ================= CONFIGURACIÓN DE LA BASE =================
USER = "Jason"
PASSWORD = "Admin02%"
HOST = "35.225.240.246"  # IP pública de tu instancia
PORT = "3306"
DATABASE = "gestorex"

# Usando mysql-connector-python como driver
DATABASE_URL = f"mysql+mysqlconnector://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"

# ================= BASE DE DATOS =================
class Base(DeclarativeBase):
    pass

# ================= MOTOR y SESIÓN =================
engine = create_engine(DATABASE_URL, echo=True, future=True)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ================= PRUEBA DE CONEXIÓN =================
try:
    with engine.connect() as conn:
        print("✅ Conexión SQLAlchemy exitosa")
except Exception as e:
    print(f"❌ Error SQLAlchemy: {e}")

# ================= FUNCION GET_DB =================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
