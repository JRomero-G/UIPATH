"""

PROPOSITO:
----------
Flujpo de accion en el proceso que realiza un administrador cuando:
1. Ve la lista de infimas disponibles (sin asignar) en su tabla
2. Selecciona varias ínfimas marcando checkboxes
3. Las asigna a un empleado especifico
4. Verifica que esas infimas ya no aparezcan como disponibles

CASOS DE USO:
-------------
- Verificar que el sistema de asignacion funciona correctamente
- Probar que las validaciones de negocio se cumplen (usuario activo, infimas existentes)
- Confirmar que la tabla del admin se actualiza tras asignar
- Detectar conflictos de asignacion (ínfimas ya asignadas, usuarios inválidos) - En en la vista el administrador 
  este problema se manejaria mostrando solo infimas no asignadas
  

REQUISITOS PREVIOS:
-------------------
1. Base de datos con:
   - Un usuario empleado (es_admin=False, estado="activo")
   - Algunas ínfimas con etapa="ingresada" sin asignar - para realizar la prueba cambie 3 infimas al azar

ESTRUCTURA DE LA PRUEBA:
-------------------------
PASO 1: Cargar infimas disponibles (controlador: obtener_infimas_disponibles_admin)
PASO 2: Simular selección de checkboxes (toma las primeras N ínfimas) - en la vista solo se tomaran las seleccionadas (check)
PASO 3: Asignar al empleado (controlador: asignar_infimas_recomendadas_a_usuario) - asignar mas de una infima a un usuario una vez
PASO 4: Verificar actualización de la tabla (recargar disponibles y comparar)

VALIDACIONES QUE SE PRUEBAN:
-----------------------------
1 - Existe al menos una ínfima disponible para asignar
2 - El usuario empleado existe y está activo
3 - Las ínfimas existen en la base de datos
4 - Las ínfimas no están previamente asignadas
5 - La tabla del admin se actualiza correctamente (ínfimas removidas) - actualizado automaticamente luego de una asignacion

"""

import sys
import os
# Apunta a la carpeta 'src' para que Python encuentre el paquete 'Database'
# Esto es necesario porque el script se ejecuta desde Database/ pero necesita
# importar módulos que están en src/Database/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Database.database import SessionLocal
from Database.Controllers.infima_controller import obtener_infimas_disponibles_admin
from Database.Controllers.recomendaciones_usuario_controller import asignar_infimas_recomendadas_a_usuario


# =============================================================================
# PARÁMETROS DE CONFIGURACIÓN
# =============================================================================
"""
USUARIO_EMPLEADO_ID:
- Debe ser el ID de un usuario con:
  * es_admin = False (no es administrador)
  * estado = "activo" (cuenta activa)

CANTIDAD_A_SELECCIONAR:
- Cuántas ínfimas quieres asignar en esta prueba
- Simula marcar N checkboxes en la interfaz del admin
- Si hay menos disponibles, se asignarán solo las que existan (esto para la prueba solamente, desde el frontend no habria que hacer esto)
"""

USUARIO_EMPLEADO_ID = 3       # ID de un empleado (es_admin=False, estado="activo")
CANTIDAD_A_SELECCIONAR = 3    # Cuántas ínfimas quieres asignar (simula checkboxes)


#INICIO DE LA PRUAB

print("=== TEST: ASIGNAR ÍNFIMAS A UN USUARIO ===\n")


# SessionLocal() crea una conexión nueva a la BD que se usará durante toda la prueba
db = SessionLocal()

try:

    # =========================================================================
    # PASO 1: CARGAR ÍNFIMAS DISPONIBLES: Esta es la misma consulta que se ejecuta cuando el admin abre su panel.
    #Las ínfimas que aparecen aquí son las que tendrán checkboxes disponibles
    #para ser asignadas a empleados
    # =========================================================================
   
    print("--- PASO 1: Cargando ínfimas disponibles para el admin ---")

    disponibles = obtener_infimas_disponibles_admin(db)

    # VALIDACIÓN: Si no hay ínfimas disponibles, no hay nada que asignar
    if not disponibles:
        print(" x  No hay ínfimas disponibles para asignar.")
        print("    Verifica que existan ínfimas con etapa='ingresada' y sin asignar.")
        print("    Puedes ejecutar el script de carga masiva para agregar ínfimas.")
        sys.exit()

    # Mostrar resumen de ínfimas encontradas
    print(f" Se encontraron {len(disponibles)} ínfimas disponibles:")
    print(f"\n   {'ID':<6} {'Código':<25} {'Entidad':<35} {'Etapa'}")
    print(f"   {'-'*6} {'-'*25} {'-'*35} {'-'*10}")
    
    # Muestra solo las primeras 5 para no saturar la consola
    for inf in disponibles[:5]:
        print(f"   {inf.id_infima:<6} {inf.codigo_necesidad:<25} {str(inf.entidad_contratante)[:33]:<35} {inf.etapa}")
    
    if len(disponibles) > 5:
        print(f"   ... y {len(disponibles) - 5} más")


    # =========================================================================
    # PASO 2: SIMULAR SELECCIÓN DE CHECKBOXES: Para la prueba esto es asi, Si hay 10 ínfimas disponibles 
    # y CANTIDAD_A_SELECCIONAR = 3: Se seleccionarán los IDs de las 3 primeras ínfimas [7, 10, 16]
    # =========================================================================

    print(f"\n--- PASO 2: Simulando selección de {CANTIDAD_A_SELECCIONAR} checkboxes ---")

    # Calcular cuántas se pueden seleccionar (mínimo entre lo pedido y lo disponible)
    cantidad_real = min(CANTIDAD_A_SELECCIONAR, len(disponibles))
    
    # Extraer los IDs de las primeras N ínfimas
    infimas_seleccionadas = [inf.id_infima for inf in disponibles[:cantidad_real]]

    print(f" IDs seleccionados: {infimas_seleccionadas}")


    # =========================================================================
    # PASO 3: ASIGNAR AL EMPLEADO: Ae valida que las infimas existan, se asignan solo las 
    # que no estan asignadas en la tabla de recomendaciones
    # =========================================================================
   
    print(f"\n--- PASO 3: Asignando al usuario ID={USUARIO_EMPLEADO_ID} ---")

    resultado = asignar_infimas_recomendadas_a_usuario(
        db,
        usuario_id=USUARIO_EMPLEADO_ID,
        lista_infimas=infimas_seleccionadas
    )

    # Evaluar el resultado y mostrar feedback apropiado
    if "error" in resultado:
        print(f" x Error al asignar:")
        print(f"   {resultado['error']}")

    elif "mensaje" in resultado:
        print(f"  {resultado['mensaje']}")
        print("\n   Esto significa que las ínfimas seleccionadas ya estaban asignadas")
        print("   a algún usuario (pueden ser el mismo u otro).")

    else:
        print(f"  Asignación exitosa:")
        print(f"   Usuario ID     : {resultado['usuario_id']}")
        print(f"   Total asignadas: {resultado['total_asignadas']}")
        print(f"   IDs asignados  : {resultado['infimas']}")


    # =========================================================================
    # PASO 4: VERIFICAR ACTUALIZACIÓN DE LA TABLA DEL ADMIN: Se actualiza la tabla del
    # administrador sin las infimas que asigno
    # =========================================================================
    """"
    EJEMPLO:
    
    Antes de asignar: disponibles = [7, 10, 16, 20, 25]  (5 ínfimas)
    Se asignan: [7, 10, 16]
    Después de asignar: disponibles = [20, 25]  (2 ínfimas) - lo que se le mostrara al administrador
    """
    print(f"\n--- PASO 4: Verificando que la tabla del admin se actualizó ---")

    # Recargar la lista de ínfimas disponibles
    disponibles_despues = obtener_infimas_disponibles_admin(db)
    ids_despues = [inf.id_infima for inf in disponibles_despues]

    # Verificar que ningún ID asignado siga apareciendo como disponible
    todas_removidas = all(id not in ids_despues for id in infimas_seleccionadas)

    if todas_removidas:
        print(f" Las ínfimas asignadas ya NO aparecen en la tabla del admin")
        print(f"   Antes: {len(disponibles)} disponibles -> Ahora: {len(disponibles_despues)} disponibles")
        print(f"\n   Detalle de la verificación:")
        for id_asignado in infimas_seleccionadas:
            print(f"   - Ínfima {id_asignado}:  removida correctamente")
    else:
        print(f" Algunas ínfimas aún aparecen como disponibles tras la asignación")


except Exception as e:
    """
    Si ocurre cualquier excepción no manejada (error de conexión a BD,
    error de sintaxis SQL, etc.), se captura aquí y se muestra información
    detallada para debugging.
    """
    print(" Error inesperado:")
    print(f"   Tipo   : {type(e).__name__}")
    print(f"   Mensaje: {str(e)}")
    print("\n   Stack trace completo:")
    
    import traceback
    traceback.print_exc()

finally:
    """
    SIEMPRE se ejecuta, haya tenido éxito o error.
    
    db.close():
    - Cierra la conexión a la base de datos
    - Libera recursos
    - Si hubo un commit exitoso, los cambios ya están persistidos
    - Si hubo un rollback, los cambios ya fueron descartados
    
    NOTA: Si quisieras que esta prueba NO modifique la BD, cambiarías
    db.close() por db.rollback() para deshacer todos los cambios.
    """
    db.close()
    print("\n=== SESIÓN CERRADA ===")
    print("\nLA PRUEBA HA FINALIZADO.")