import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta

print("ANALISIS DETALLADO: Cuando se guarda vs cuando NO")
print("=" * 70)

# Analizar las últimas 15 guías
guias = Venta.objects.filter(tipo_documento='guia').order_by('-id')[:15]

print("\nUltimas 15 guias (mas reciente primero):")
print("-" * 70)

for venta in guias:
    tiene_valor = venta.tipo_despacho is not None
    simbolo = "✓" if tiene_valor else "✗"
    
    print(f"\n{simbolo} ID {venta.id} | Numero: {venta.numero_venta}")
    print(f"  tipo_despacho: {venta.tipo_despacho or 'NULL'}")
    print(f"  tipo_documento_planeado: {venta.tipo_documento_planeado if hasattr(venta, 'tipo_documento_planeado') else 'N/A'}")
    print(f"  Estado: {venta.estado}")
    print(f"  Facturado: {venta.facturado}")
    print(f"  Fecha: {venta.fecha}")
    
    # Verificar si tiene DTE asociado
    try:
        dte = venta.dte
        print(f"  DTE: Folio {dte.folio}, tipo_traslado={dte.tipo_traslado}")
    except:
        print(f"  DTE: No tiene")

print("\n" + "=" * 70)
print("PATRON DETECTADO:")
print("=" * 70)

# Contar por estado
con_valor_confirmada = Venta.objects.filter(
    tipo_documento='guia',
    tipo_despacho__isnull=False,
    estado='confirmada'
).count()

sin_valor_confirmada = Venta.objects.filter(
    tipo_documento='guia',
    tipo_despacho__isnull=True,
    estado='confirmada'
).count()

con_valor_borrador = Venta.objects.filter(
    tipo_documento='guia',
    tipo_despacho__isnull=False,
    estado='borrador'
).count()

sin_valor_borrador = Venta.objects.filter(
    tipo_documento='guia',
    tipo_despacho__isnull=True,
    estado='borrador'
).count()

print(f"\nGuias CONFIRMADAS:")
print(f"  Con tipo_despacho: {con_valor_confirmada}")
print(f"  Sin tipo_despacho: {sin_valor_confirmada}")

print(f"\nGuias BORRADOR:")
print(f"  Con tipo_despacho: {con_valor_borrador}")
print(f"  Sin tipo_despacho: {sin_valor_borrador}")

# Hipótesis
print(f"\n" + "=" * 70)
print("HIPOTESIS:")
print("=" * 70)

if sin_valor_borrador > con_valor_borrador:
    print("\nLas guias en BORRADOR tienden a NO tener tipo_despacho")
    print("Posible causa: El flujo de cierre directo no esta copiando el campo")
elif sin_valor_confirmada > con_valor_confirmada:
    print("\nLas guias CONFIRMADAS tienden a NO tener tipo_despacho")
    print("Posible causa: El flujo normal no esta guardando el campo")
else:
    print("\nNo hay patron claro. Revisar logs del servidor.")
