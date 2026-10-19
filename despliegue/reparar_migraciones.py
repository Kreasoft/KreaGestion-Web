#!/usr/bin/env python
"""
Script de un solo paso para resolver el conflicto de migraciones en Producción.
Elimina los archivos residuales, limpia django_migrations y aplica migrate.
Uso:
    python despliegue/reparar_migraciones.py
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Archivos residuales a eliminar
ARCHIVOS_RESIDUALES = [
    BASE_DIR / 'ventas' / 'migrations' / '0054_merge_20260924_1833.py',
    BASE_DIR / 'clientes' / 'migrations' / '0010_merge_20260911_0848.py',
    BASE_DIR / 'pedidos' / 'migrations' / '0022_remove_ordendespacho_solicitud_id_and_more.py',
]

print("==================================================")
print("  REPARADOR DE MIGRACIONES - PRODUCCIÓN")
print("==================================================")

# Paso 1: Eliminar archivos residuales
eliminados = 0
for f in ARCHIVOS_RESIDUALES:
    if f.exists():
        try:
            f.unlink()
            print(f"[OK] Archivo residual eliminado: {f.name}")
            eliminados += 1
        except Exception as e:
            print(f"[!] No se pudo eliminar {f.name}: {e}")
    else:
        print(f"[-] No presente (correcto): {f.name}")

# Paso 2: Inicializar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from django.db import connection
from django.core.management import call_command

# Paso 3: Blindaje de la base de datos y limpieza de registros huérfanos
print("\nPreparando base de datos...")
with connection.cursor() as cursor:
    # Asegurar que existan tablas/columnas si la migración intenta borrarlas
    try:
        cursor.execute("ALTER TABLE pedidos_ordendespacho ADD COLUMN IF NOT EXISTS solicitud_id integer;")
    except Exception:
        pass
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS pedidos_despachoreferencia (id serial primary key);")
    except Exception:
        pass

    # Limpiar entradas de migraciones residuales de django_migrations
    cursor.execute("""
        DELETE FROM django_migrations WHERE app = 'pedidos' AND name IN (
            '0018_alter_ordendespacho_tipo_traslado_and_more',
            '0019_merge_20260911_0848',
            '0021_merge_20260914_1942',
            '0022_remove_ordendespacho_solicitud_id_and_more'
        );
    """)
    cursor.execute("DELETE FROM django_migrations WHERE app = 'clientes' AND name = '0010_merge_20260911_0848';")
    cursor.execute("DELETE FROM django_migrations WHERE app = 'ventas' AND name = '0054_merge_20260924_1833';")
    print("[OK] Registros huérfanos de django_migrations limpiados.")

# Paso 4: Ejecutar migraciones
print("\nAplicando migraciones oficiales...")
try:
    call_command('migrate', interactive=False)
    print("\n==================================================")
    print("  ¡ÉXITO! Migraciones aplicadas correctamente.")
    print("==================================================")
except Exception as e:
    print(f"\n[!] Error al migrar: {e}")
    print("Intentando sincronizar con --fake...")
    try:
        call_command('migrate', fake=True, interactive=False)
        print("\n==================================================")
        print("  ¡ÉXITO! Migraciones sincronizadas con --fake.")
        print("==================================================")
    except Exception as e2:
        print(f"\n[ERROR CRÍTICO]: {e2}")
        sys.exit(1)
