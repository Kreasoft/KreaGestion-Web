#!/usr/bin/env python
"""Script para crear la base de datos PostgreSQL si no existe"""
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configuración
DB_NAME = 'gestioncloud'
DB_USER = 'kreasoft'
DB_PASSWORD = '524302cl+'
DB_HOST = 'localhost'
DB_PORT = '5432'

try:
    print("=" * 50)
    print("Verificando conexión a PostgreSQL...")
    print("=" * 50)
    
    # Conectar a la base de datos 'postgres' (siempre existe)
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database='postgres'
    )
    
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    # Verificar si la base de datos existe
    cur.execute(
        sql.SQL("SELECT 1 FROM pg_database WHERE datname = {}").format(
            sql.Literal(DB_NAME)
        )
    )
    
    exists = cur.fetchone()
    
    if exists:
        print(f"La base de datos '{DB_NAME}' ya existe.")
    else:
        print(f"Creando la base de datos '{DB_NAME}'...")
        cur.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(DB_NAME),
                sql.Identifier(DB_USER)
            )
        )
        print(f"Base de datos '{DB_NAME}' creada exitosamente!")
    
    # Otorgar privilegios
    print(f"Otorgando privilegios al usuario '{DB_USER}'...")
    cur.execute(
        sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
            sql.Identifier(DB_NAME),
            sql.Identifier(DB_USER)
        )
    )
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 50)
    print("Configuración completada!")
    print("=" * 50)
    print("\nAhora puedes ejecutar las migraciones:")
    print("python manage.py migrate")
    
except psycopg2.OperationalError as e:
    print(f"\nERROR: No se pudo conectar a PostgreSQL")
    print(f"Detalle: {e}")
    print("\nVerifica que:")
    print("1. PostgreSQL esté ejecutándose")
    print("2. Las credenciales sean correctas")
    print("3. El usuario 'kreasoft' exista y tenga permisos")
except Exception as e:
    print(f"\nERROR: {e}")





