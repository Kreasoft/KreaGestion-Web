#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Crear la base de datos gestioncloud"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Intentar primero con usuario postgres (superusuario)
usuarios_intento = [
    {'user': 'postgres', 'password': 'postgres'},
    {'user': 'postgres', 'password': ''},
    {'user': 'kreasoft', 'password': '524302cl+'},
]

DB_NAME = 'gestioncloud'
DB_HOST = 'localhost'
DB_PORT = 5432

print("=" * 60)
print("Intentando crear la base de datos...")
print("=" * 60)

for intento, creds in enumerate(usuarios_intento, 1):
    try:
        print(f"\nIntento {intento}: Usuario '{creds['user']}'...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=creds['user'],
            password=creds['password'],
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Verificar si existe
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_NAME,)
        )
        exists = cur.fetchone()
        
        if exists:
            print(f"   La base de datos '{DB_NAME}' ya existe.")
        else:
            print(f"   Creando base de datos '{DB_NAME}'...")
            cur.execute(
                f"CREATE DATABASE {DB_NAME} OWNER kreasoft"
            )
            print(f"   Base de datos '{DB_NAME}' creada exitosamente!")
        
        # Otorgar privilegios
        print(f"   Otorgando privilegios...")
        cur.execute(
            f"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO kreasoft"
        )
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("Base de datos creada exitosamente!")
        print("=" * 60)
        break
        
    except psycopg2.OperationalError as e:
        print(f"   Error: {e}")
        if "password" in str(e).lower() or "authentication" in str(e).lower():
            print("   (Necesita contraseña o permisos)")
        continue
    except Exception as e:
        print(f"   Error: {e}")
        continue
else:
    print("\n" + "=" * 60)
    print("No se pudo crear la base de datos automáticamente.")
    print("Necesitas ejecutar manualmente:")
    print("=" * 60)
    print("\npsql -U postgres")
    print(f"\nCREATE DATABASE {DB_NAME} OWNER kreasoft;")
    print(f"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO kreasoft;")













