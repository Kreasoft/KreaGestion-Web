#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Otorgar permisos de creación en el esquema public (requiere superusuario)"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_NAME = 'gestioncloud'
DB_USER = 'kreasoft'
DB_HOST = 'localhost'
DB_PORT = 5432

# Intentar con diferentes usuarios superusuario
usuarios_super = [
    {'user': 'postgres', 'password': 'postgres'},
    {'user': 'postgres', 'password': ''},
]

print("=" * 60)
print("Otorgando permisos de CREACIÓN en esquema public...")
print("(Requiere conexión como superusuario)")
print("=" * 60)

for creds in usuarios_super:
    try:
        print(f"\nIntentando con usuario '{creds['user']}'...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=creds['user'],
            password=creds['password'],
            database=DB_NAME
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        print("   Conectado como superusuario!")
        
        # Otorgar permisos de creación en el esquema public
        print(f"\n1. Otorgando CREATE en esquema public a '{DB_USER}'...")
        cur.execute(f"GRANT CREATE ON SCHEMA public TO {DB_USER};")
        print("   OK")
        
        print(f"\n2. Otorgando USAGE en esquema public a '{DB_USER}'...")
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {DB_USER};")
        print("   OK")
        
        print(f"\n3. Otorgando ALL en esquema public a '{DB_USER}'...")
        cur.execute(f"GRANT ALL ON SCHEMA public TO {DB_USER};")
        print("   OK")
        
        # Asegurar que el usuario sea propietario del esquema (si es posible)
        print(f"\n4. Configurando privilegios por defecto...")
        cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {DB_USER};")
        cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {DB_USER};")
        print("   OK")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("Permisos otorgados exitosamente!")
        print("=" * 60)
        break
        
    except psycopg2.OperationalError as e:
        if "password" in str(e).lower() or "authentication" in str(e).lower():
            print(f"   Error de autenticación - necesita contraseña")
        else:
            print(f"   Error: {e}")
        continue
    except Exception as e:
        print(f"   Error: {e}")
        continue
else:
    print("\n" + "=" * 60)
    print("No se pudo otorgar permisos automáticamente.")
    print("Ejecuta manualmente como superusuario:")
    print("=" * 60)
    print(f"\npsql -U postgres -d {DB_NAME}")
    print(f"\nGRANT CREATE ON SCHEMA public TO {DB_USER};")
    print(f"GRANT USAGE ON SCHEMA public TO {DB_USER};")
    print(f"GRANT ALL ON SCHEMA public TO {DB_USER};")
    print(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {DB_USER};")
    print(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {DB_USER};")
    print("=" * 60)










