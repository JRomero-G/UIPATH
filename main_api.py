from fastapi import FastAPI
from src.Database.Routes.usuarios_routes import router as usuarios_router
from src.Database.Routes.auth_routes import router as auth_router
from src.Database.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth_router)
app.include_router(usuarios_router)
