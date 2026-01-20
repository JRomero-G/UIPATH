# registrar_usuario_test_corregido.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from src.Database.database import SessionLocal
from src.Database.Controllers.usuarios_controller import registrar_usuario, UsuarioCreate
from src.Database.Auth.Hashing import hash_password, safe_truncate_password

# Verifica primero la contraseña
print("=== VERIFICANDO CONTRASEÑA ===")
password = "Empleado123456"
print(f"Contraseña original: {password}")
print(f"Longitud en bytes: {len(password.encode('utf-8'))}")

password_segura = safe_truncate_password(password)
print(f"Contraseña segura: {password_segura}")
print(f"Longitud segura en bytes: {len(password_segura.encode('utf-8'))}")

# Crear usuario administrador de prueba
usuario_data = UsuarioCreate(
    usuario="empleado",
    nombre="Empleado de Prueba",
    password=password,  # Usará la contraseña original, será truncada internamente
    correo="emp@test.com",
    telefono="88888888",
    es_admin=False
)

print("\n=== INTENTANDO REGISTRO ===")

# Crear sesión de base de datos
db = SessionLocal()

try:
    nuevo_usuario = registrar_usuario(db, usuario_data)
    print("✅ Usuario registrado correctamente:")
    print(f"ID: {nuevo_usuario.id_usuario}")
    print(f"Usuario: {nuevo_usuario.usuario}")
    print(f"Nombre: {nuevo_usuario.nombre}")
    print(f"¿Es admin?: {nuevo_usuario.es_admin}")
    
except Exception as e:
    print("❌ Error al registrar usuario:")
    print(f"Tipo: {type(e).__name__}")
    print(f"Mensaje: {str(e)}")
    
    # Información adicional para debugging
    import traceback
    traceback.print_exc()
    
finally:
    db.close()
    print("\n=== SESIÓN CERRADA ===")