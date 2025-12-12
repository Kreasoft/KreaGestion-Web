#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Otorgar permisos en el esquema public"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_NAME = 'gestioncloud'
DB_USER = 'kreasoft'
DB_PASSWORD = '524302cl+'
DB_HOST = 'localhost'
DB_PORT = 5432

print("=" * 60)
print("Otorgando permisos en el esquema public...")
print("=" * 60)

try:
    # Conectar a la base de datos gestioncloud
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    print(f"\n1. Otorgando permisos en el esquema public...")
    cur.execute(f"GRANT ALL ON SCHEMA public TO {DB_USER};")
    print("   OK - Permisos en esquema public otorgados")
    
    print(f"\n2. Configurando privilegios por defecto...")
    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {DB_USER};")
    cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {DB_USER};")
    print("   OK - Privilegios por defecto configurados")
    
    print(f"\n3. Otorgando permisos en todas las tablas existentes...")
    cur.execute("""
        DO $$ 
        DECLARE 
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') 
            LOOP
                EXECUTE 'GRANT ALL PRIVILEGES ON TABLE public.' || quote_ident(r.tablename) || ' TO ' || quote_ident(%s);
            END LOOP;
        END $$;
    """, (DB_USER,))
    print("   OK - Permisos en tablas otorgados")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("Permisos otorgados exitosamente!")
    print("=" * 60)
    
except psycopg2.OperationalError as e:
    print(f"\nERROR: No se pudo conectar - {e}")
    print("\nNecesitas ejecutar estos comandos como superusuario:")
    print(f"\npsql -U postgres -d {DB_NAME}")
    print(f"\nGRANT ALL ON SCHEMA public TO {DB_USER};")
    print(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {DB_USER};")
    print(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {DB_USER};")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()





