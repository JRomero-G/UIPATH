from fastapi import FastAPI
from src.Database.Routes.usuarios_routes import router as usuarios_router
from src.Database.Routes.auth_routes import router as auth_router
from src.Database.Routes.recomendaciones_usuario_routes import router as recomendaciones_usuario_router
from src.Database.Routes.infima_routes import router as infimas_router
from src.Database.Routes.contraindicaciones_routes import router as contraindicaciones_router
from src.Database.Routes.bucket_url_routes import router as bucket_url_router
from src.Database.Routes.evaluacion_router import router as evaluacion_router
from src.Database.Routes.logs_eventos_routes import router as logs_eventos_router


app = FastAPI()

app.include_router(auth_router)
app.include_router(usuarios_router)
app.include_router(recomendaciones_usuario_router)
app.include_router(infimas_router)
app.include_router(contraindicaciones_router)
app.include_router(bucket_url_router)
app.include_router(evaluacion_router)
app.include_router(logs_eventos_router)
