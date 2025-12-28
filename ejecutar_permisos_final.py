#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Otorgar permisos de creación en el esquema public como superusuario"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_NAME = 'gestioncloud'
DB_USER = 'kreasoft'
POSTGRES_PASSWORD = '524302cl+'
DB_HOST = 'localhost'
DB_PORT = 5432

print("=" * 60)
print("Otorgando permisos de CREACIÓN en esquema public...")
print("=" * 60)

try:
    # Conectar como superusuario postgres
    print(f"\n1. Conectando como superusuario 'postgres'...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user='postgres',
        password=POSTGRES_PASSWORD,
        database=DB_NAME
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    print("   OK - Conectado como superusuario")
    
    # Otorgar permisos de creación en el esquema public
    print(f"\n2. Otorgando CREATE en esquema public a '{DB_USER}'...")
    cur.execute(f"GRANT CREATE ON SCHEMA public TO {DB_USER};")
    print("   OK")
    
    print(f"\n3. Otorgando USAGE en esquema public a '{DB_USER}'...")
    cur.execute(f"GRANT USAGE ON SCHEMA public TO {DB_USER};")
    print("   OK")
    
    print(f"\n4. Otorgando ALL en esquema public a '{DB_USER}'...")
    cur.execute(f"GRANT ALL ON SCHEMA public TO {DB_USER};")
    print("   OK")
    
    print(f"\n5. Configurando privilegios por defecto para tablas...")
    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {DB_USER};")
    print("   OK")
    
    print(f"\n6. Configurando privilegios por defecto para secuencias...")
    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {DB_USER};")
    print("   OK")
    
    # Verificar permisos
    print(f"\n7. Verificando permisos...")
    cur.execute("""
        SELECT grantee, privilege_type 
        FROM information_schema.role_schema_grants 
        WHERE schema_name = 'public' AND grantee = %s
    """, (DB_USER,))
    permisos = cur.fetchall()
    if permisos:
        print("   Permisos otorgados:")
        for permiso in permisos:
            print(f"     - {permiso[1]}")
    else:
        print("   (No se encontraron permisos en information_schema)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("Permisos otorgados exitosamente!")
    print("=" * 60)
    print("\nAhora puedes ejecutar las migraciones:")
    print("python manage.py migrate")
    
except psycopg2.OperationalError as e:
    print(f"\nERROR de conexión: {e}")
    print("\nVerifica que:")
    print("1. PostgreSQL esté ejecutándose")
    print("2. La contraseña del usuario 'postgres' sea correcta")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()













