#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verificar conexión y crear base de datos"""
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_USER = 'kreasoft'
DB_PASSWORD = '524302cl+'
DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'gestioncloud'

print("=" * 60)
print("Verificando PostgreSQL...")
print("=" * 60)

# Paso 1: Verificar conexión con usuario
try:
    print(f"\n1. Probando conexión con usuario '{DB_USER}'...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database='postgres'
    )
    print("   OK - Credenciales correctas")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    # Paso 2: Verificar si la base de datos existe
    print(f"\n2. Verificando si existe la base de datos '{DB_NAME}'...")
    cur.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (DB_NAME,)
    )
    exists = cur.fetchone()
    
    if exists:
        print(f"   OK - La base de datos '{DB_NAME}' existe")
        cur.close()
        conn.close()
        
        # Paso 3: Probar conexión a la base de datos
        print(f"\n3. Probando conexión a '{DB_NAME}'...")
        conn2 = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cur2 = conn2.cursor()
        cur2.execute("SELECT version();")
        version = cur2.fetchone()
        print(f"   OK - Conexión exitosa!")
        print(f"   Versión: {version[0][:50]}...")
        cur2.close()
        conn2.close()
        
        print("\n" + "=" * 60)
        print("Todo está configurado correctamente!")
        print("Puedes ejecutar: python manage.py migrate")
        print("=" * 60)
        
    else:
        print(f"   ERROR - La base de datos '{DB_NAME}' NO existe")
        print("\n" + "=" * 60)
        print("INSTRUCCIONES PARA CREAR LA BASE DE DATOS:")
        print("=" * 60)
        print("\nEjecuta estos comandos como superusuario (postgres):")
        print("\npsql -U postgres")
        print("\nLuego ejecuta:")
        print(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};")
        print(f"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER};")
        print("\nO usa el archivo: crear_bd_manual.sql")
        print("=" * 60)
        
    cur.close()
    conn.close()
    
except psycopg2.OperationalError as e:
    print(f"   ERROR - {e}")
    print("\nVerifica:")
    print("1. PostgreSQL está ejecutándose")
    print("2. Las credenciales son correctas")
    print("3. El usuario tiene permisos")
    sys.exit(1)
except Exception as e:
    print(f"   ERROR - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)














