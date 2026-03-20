import requests
from packaging import version
from src.Config.version import CURRENT_VERSION
from Config import Global 
import os
import sys



def verificar_actualizacion():
    try:
        response = requests.get(f"{Global.BACKEND_URL}/version", timeout=5)
        data = response.json()

        server_version = data.get("version")
        url = data.get("url")

        if version.parse(server_version) > version.parse(CURRENT_VERSION):
            return {
                "update": True,
                "version": server_version,
                "url": url
            }

        return {"update": False}

    except Exception as e:
        print("Error verificando actualización:", e)
        return {"update": False}
    

def descargar_actualizacion(url):
    try:
        response = requests.get(url, stream=True)
        ruta = os.path.join(os.path.dirname(sys.executable), "update.exe")

        with open(ruta, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        print("Descarga completa:", ruta)

    except Exception as e:
        print("Error descargando actualización:", e)