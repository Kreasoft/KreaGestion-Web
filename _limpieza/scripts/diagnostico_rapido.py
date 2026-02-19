import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.db import connection
from ventas.models import Venta

print("DIAGNOSTICO RAPIDO: tipo_despacho")
print("=" * 60)

# 1. Verificar si el campo existe
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT COUNT(*) 
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ventas_venta' AND COLUMN_NAME = 'tipo_despacho'
    """)
    existe = cursor.fetchone()[0]
    
    if existe:
        print("\n1. Campo tipo_despacho: EXISTE en la tabla")
    else:
        print("\n1. Campo tipo_despacho: NO EXISTE - EJECUTAR MIGRACIONES")

# 2. Contar ventas
ventas_guia_total = Venta.objects.filter(tipo_documento='guia').count()
ventas_null = Venta.objects.filter(tipo_documento='guia', tipo_despacho__isnull=True).count()
ventas_con_valor = Venta.objects.filter(tipo_documento='guia', tipo_despacho__isnull=False).count()

print(f"\n2. Ventas de tipo guia:")
print(f"   Total: {ventas_guia_total}")
print(f"   Con tipo_despacho NULL: {ventas_null}")
print(f"   Con tipo_despacho definido: {ventas_con_valor}")

# 3. Mostrar últimas 5 guías
print(f"\n3. Ultimas 5 guias:")
for venta in Venta.objects.filter(tipo_documento='guia').order_by('-id')[:5]:
    print(f"   ID {venta.id}: tipo_despacho = {venta.tipo_despacho}")

# 4. Conclusión
print(f"\n4. CONCLUSION:")
if ventas_null == ventas_guia_total and ventas_guia_total > 0:
    print("   PROBLEMA: TODAS las guias tienen tipo_despacho en NULL")
    print("   El formulario NO esta guardando el valor seleccionado")
elif ventas_con_valor > 0:
    print("   OK: Algunas guias tienen tipo_despacho guardado")
else:
    print("   No hay guias para analizar")
