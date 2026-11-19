import pyodbc
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=DESKTOP-UDE1MCF\\SQLEXPRESS;"
    "DATABASE=ars_hacaton;"
    "TrustServerCertificate=yes;"
    "Trusted_Connection=yes;"
)

def db_conn():
    return pyodbc.connect(CONNECTION_STRING)