import mysql.connector

try:
    # Instalar: https://dev.mysql.com/downloads/file/?id=545740 
    # Instalar primero: pip install mysql-connector-python
    # Solo asi me funciono la coneccion
    connection = mysql.connector.connect(
        host="35.225.240.246",
        port=3306,
        user="Jason",
        password="Admin02%",  
        database="gestorex"  
    )
    
    print(" Conexión exitosa")
    cursor = connection.cursor()
    cursor.execute("SELECT DATABASE()")
    db = cursor.fetchone()
    print(f"Base de datos actual MySQL: {db[0]}")
    connection.close()
    
except mysql.connector.Error as err:
    print(f" Error: {err}")
   