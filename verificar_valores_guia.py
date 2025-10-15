import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico

guias = DocumentoTributarioElectronico.objects.filter(tipo_dte='52').order_by('-id')

print("=" * 60)
print("VERIFICACIÓN DE VALORES EN GUÍAS")
print("=" * 60)

if guias.exists():
    for guia in guias[:3]:
        print(f"\nGuía Folio: {guia.folio}")
        print(f"  Fecha: {guia.fecha_emision}")
        print(f"  Monto Neto: ${guia.monto_neto}")
        print(f"  Monto IVA: ${guia.monto_iva}")
        print(f"  Monto Total: ${guia.monto_total}")
        print(f"  Receptor: {guia.razon_social_receptor}")
else:
    print("\nNo hay guías generadas")

print("\n" + "=" * 60)
