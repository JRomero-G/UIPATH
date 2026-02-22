import sys
import os

#Apuntar a la carpeta src para encontrar Database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),"..")))
from Database.Controllers.recomendaciones_usuario_controller import obtener_infimas_recomendadas_asignadas_del_usuario
from Database.database import SessionLocal

# Valores que necesitamos
USUARIO_EMPLEADO_ID = 3 #id del usuario que asignamos las infimas

print(f" ======= Test para cargar las infimas asignadas al usuario : {USUARIO_EMPLEADO_ID} Iniciadas =====================")

db = SessionLocal()

try:
    # === Paso 1: Obtener infimas del suario =====
    print(f" ======= Paso 1: Obtener infimas selecionadas del usuario con ID: {USUARIO_EMPLEADO_ID} =============")

    infimas = obtener_infimas_recomendadas_asignadas_del_usuario(
        db,
        usuario_id=USUARIO_EMPLEADO_ID
    )

    if not infimas:
        print("Advertencia: Este usuario no tiene infimas asignadas.")
        print(f"Verifica que el usuario con ID={USUARIO_EMPLEADO_ID} exista y tenga infimas asignadas")
        print("Asigna primero infimas y luego realiza nuevamente este test")

    print(f" Se encontraron {len(infimas)} infimas para este usuario: \n")

    #Paso 2: Ver las infimas asignadas
    print("========= Paso 2: Ver las infimas asinadas ================")
    print(f" {'#':<4} {'ID':<6} {'Codigo de Necesidad':<25} {'Entidad Contratante':<30} {'Etapa':<25} {'Fecha de publicacion':<17} {'Fecha de Limite Proformas':<17}")
    print(f" {'-'*4} {'-'*6} {'-'*25} {'-'*30} {'-'*25} {'-'*17} {'-'*17}")

    for i, inf in enumerate(infimas,start=1):
        fecha = str(inf.fecha_publicacion) if inf.fecha_publicacion else "Sin Fecha de Publiacion"
        fecha_final = str(inf.fecha_limite_proformas) if inf.fecha_limite_proformas else "Sin Fecha Limite Establecida"
        entidad = str(inf.entidad_contratante)[:30] if inf.entidad_contratante else "Sin entidad registrada"
        print(f"{i:<4} {inf.id_infima:<6} {inf.codigo_necesidad:<25} {entidad:<30} {inf.etapa:<20} {fecha} {fecha_final}\n")

    # paso 3: Resumen
    print("========== Paso 3: Resumen ==============")
    print(f" Usuario ID: {USUARIO_EMPLEADO_ID}")
    print(f" Infimas asignadas: {len(infimas)}")
    print(f" IDs retornados   : {[inf.id_infima for inf in infimas]}")
    

except Exception as e:
    print(" x Error al ejecutar el test")
    print(f" Tipo: {type(e).__name__}")
    print(f" Mensaje: {str(e)}")

    import traceback
    traceback.print_exc()

finally:
    db.close()
    print("\n ========= Sesion Cerrada =========")