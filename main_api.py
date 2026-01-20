from fastapi import FastAPI
from src.Database.Routes.usuarios_routes import router as usuarios_router
from src.Database.Routes.auth_routes import router as auth_router
from src.Database.database import Base, engine, get_db
from sqlalchemy.orm import Session
from fastapi import Depends

Base.metadata.create_all(bind=engine)

app = FastAPI()

# Endpoint de prueba
@app.get("/test-db")
def test_db(db: Session = Depends(get_db)):
    result = db.execute("SELECT DATABASE()").fetchone()
    return {"database": result[0]}

app.include_router(auth_router)
app.include_router(usuarios_router)
