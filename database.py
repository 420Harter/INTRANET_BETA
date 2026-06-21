import pyodbc

# Configuración de la cadena de conexión a SQL Server
# Reemplazamos SERVER por el nombre de tu computadora: INTRANET
CONNECTION_STRING = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=INTRANET;"
    "Database=INTRANET;"
    "Trusted_Connection=yes;"  # Autenticación de Windows
)

def get_db_connection():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        # Esto permite acceder a las columnas por nombre (ej. row.COD_ALU) en lugar de solo por índice
        conn.cursor().execute("SET NOCOUNT ON;") 
        return conn
    except Exception as e:
        print(f"Error crítico al conectar a SQL Server: {e}")
        return None